import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_client
from db.models.conversation import Conversation
from db.models.message import Message
from models import SessionLocal

HISTORY_TRIGGER = 1500   # summarize when total history exceeds this
HISTORY_BUDGET = 750     # keep recent messages within this after summarization
MIN_EXCHANGES = 5        # always keep at least this many user/assistant exchanges

SUMMARIZE_SYSTEM_PROMPT = """Summarize this conversation history concisely.
Capture key facts, decisions, and context needed to continue the conversation.
Output plain text only, no headings."""


def _count_tokens(text: str) -> int:
    return len(text) // 4


def _select_recent(messages: list) -> list:
    """
    Returns recent messages to keep.
    Keeps whichever is more: last MIN_EXCHANGES exchanges OR messages within HISTORY_BUDGET tokens.
    Always keeps complete messages, never cuts mid-message.
    """
    # Minimum: last MIN_EXCHANGES exchanges = MIN_EXCHANGES * 2 messages
    min_messages = MIN_EXCHANGES * 2

    # Walk newest to oldest, keep within token budget
    budget_kept = []
    budget = HISTORY_BUDGET
    for msg in reversed(messages):
        tokens = _count_tokens(msg.content)
        if budget - tokens < 0 and budget_kept:
            break
        budget -= tokens
        budget_kept.insert(0, msg)

    # Take whichever gives more messages
    if len(messages) <= min_messages:
        return messages

    min_kept = messages[-min_messages:]

    return min_kept if len(min_kept) > len(budget_kept) else budget_kept


def load_history(conversation_id: int, db) -> tuple[list, int]:
    """
    Returns (formatted_messages, total_token_count) for LLM prompt.
    Prepends summary if exists.
    """
    conversation = db.query(Conversation).filter_by(id=conversation_id).first()
    all_messages = db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()

    recent = _select_recent(all_messages)
    formatted = [{"role": m.role, "content": m.content} for m in recent]
    token_count = sum(_count_tokens(m.content) for m in all_messages)

    if conversation and conversation.summary:
        formatted.insert(0, {"role": "user", "content": f"[Conversation summary so far: {conversation.summary}]"})
        formatted.insert(1, {"role": "assistant", "content": "Understood, I have the context from our earlier conversation."})

    return formatted, token_count


def summarize_and_save(conversation_id: int):
    """
    Summarizes old messages beyond the kept window and saves to conversation.summary.
    Only runs when total history exceeds HISTORY_TRIGGER tokens.
    """
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter_by(id=conversation_id).first()
        if not conversation:
            return

        all_messages = db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()

        total_tokens = sum(_count_tokens(m.content) for m in all_messages)
        if total_tokens <= HISTORY_TRIGGER:
            return  # not enough history to summarize yet

        recent = _select_recent(all_messages)
        recent_ids = {m.id for m in recent}
        old_messages = [m for m in all_messages if m.id not in recent_ids]

        if not old_messages:
            return

        lines = []
        if conversation.summary:
            lines.append(f"Previous summary: {conversation.summary}\n\n")
        for m in old_messages:
            lines.append(f"{m.role.upper()}: {m.content}\n")

        response = llm_client.call_haiku([
            {"role": "user", "content": f"{SUMMARIZE_SYSTEM_PROMPT}\n\n{''.join(lines)}"}
        ])

        conversation.summary = response["content"]
        db.commit()
    finally:
        db.close()
