import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_client
from db.models.memory import Memory
from models import SessionLocal
from tool_registry import _get_embedding

EXTRACT_SYSTEM_PROMPT = """You are a memory extractor. Given a conversation exchange, extract important facts about the user worth remembering for future conversations.

Focus on:
- User preferences (likes, dislikes, style preferences)
- Personal context (name, location, profession, projects)
- Technical preferences (languages, tools, frameworks)
- Explicit instructions ("always respond in bullet points", "don't use emojis")

Rules:
- Only extract facts clearly stated by the user, not assumptions
- Each fact should be a short standalone sentence
- If nothing worth remembering, return empty list
- Output JSON only: {"facts": ["fact1", "fact2"]}"""


def extract_and_save(user_id: int, user_message: str, assistant_message: str):
    """Extract facts from conversation and save to memory. Called in background."""
    response = llm_client.call_haiku([
        {"role": "user", "content": f"{EXTRACT_SYSTEM_PROMPT}\n\nUSER: {user_message}\nASSISTANT: {assistant_message}"}
    ])

    try:
        result = json.loads(response["content"])
        facts = result.get("facts", [])
    except (json.JSONDecodeError, KeyError):
        return

    if not facts:
        return

    db = SessionLocal()
    try:
        for fact in facts:
            try:
                embedding = _get_embedding(fact)
            except Exception:
                embedding = None
            db.add(Memory(user_id=user_id, content=fact, embedding=embedding))
        db.commit()
    finally:
        db.close()


def load_relevant(user_id: int, message: str, limit: int = 5) -> str:
    """Search memories relevant to current message. Returns formatted string for prompt."""
    try:
        embedding = _get_embedding(message)
    except Exception:
        return ""

    db = SessionLocal()
    try:
        memories = (
            db.query(Memory)
            .filter(Memory.user_id == user_id, Memory.embedding != None)
            .order_by(Memory.embedding.cosine_distance(embedding))
            .limit(limit)
            .all()
        )
        if not memories:
            return ""
        facts = "\n".join(f"- {m.content}" for m in memories)
        return f"What you know about the user:\n{facts}"
    finally:
        db.close()
