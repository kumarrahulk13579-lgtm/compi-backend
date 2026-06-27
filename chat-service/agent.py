import json
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models.message import Message
from db.models.conversation import Conversation
from models import SessionLocal
import pre_check
import tool_check
import tool_registry
import executor
import planner as planner_mod
import session as session_store
import tracer as tracer_mod
import summarizer
import memory as memory_store
import spend

SYSTEM_PROMPT = "You are a helpful assistant."



def _save_messages(conversation_id: int, user_content: str, assistant_content: str):
    db = SessionLocal()
    try:
        db.add(Message(conversation_id=conversation_id, role="user", content=user_content))
        db.add(Message(conversation_id=conversation_id, role="assistant", content=assistant_content))
        db.commit()
    finally:
        db.close()


def _get_tools(message: str, active_tools: list, tracer) -> list:
    with tracer_mod.timed(tracer, "tool_check", input={"message": message, "active_tools": active_tools}) as t:
        check = tool_check.run(message, active_tools)
        t.set_output({"tools_sufficient": check["tools_sufficient"]}, cost_usd=check["usage"]["cost_usd"])

    if check["tools_sufficient"] and active_tools:
        found = tool_registry.get_by_names(active_tools)
        return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in found]

    queries = check["new_tool_descriptions"]
    if not queries:
        return []

    found = tool_registry.search_tools(queries)
    return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in found]


def run(message: str, conversation_id: int, user_id: int, is_registered: bool = False):
    """Main agent entry point. Yields SSE-formatted strings."""
    def emit(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    tracer = tracer_mod.new_trace(conversation_id=conversation_id, user_id=user_id, is_registered=is_registered)
    assistant_content_buffer = []

    db = SessionLocal()
    try:
        history, token_count = summarizer.load_history(conversation_id, db)
    finally:
        db.close()

    # 1. Pre-check
    with tracer_mod.timed(tracer, "pre_check", input={"message": message, "token_count": token_count}) as t:
        check = pre_check.run(message, token_count)
        t.set_output({"complexity": check["complexity"], "needs_summary": check["needs_summary"]}, cost_usd=check["usage"]["cost_usd"])

    complexity = check["complexity"]
    session = session_store.get(conversation_id)
    active_tools = session.get("fixed", {}).get("active_tools", [])

    # Load relevant long-term memories
    relevant_memory = memory_store.load_relevant(user_id, message)

    system_content = SYSTEM_PROMPT
    if relevant_memory:
        system_content += f"\n\n{relevant_memory}"

    # Build messages for LLM
    messages = [{"role": "system", "content": system_content}] + history

    # 2. Simple — direct LLM call
    if complexity == "simple":
        yield emit({"type": "status", "message": "Thinking..."})
        messages.append({"role": "user", "content": message})

        for event in executor.run(messages, tools=[], tracer=tracer):
            if event["type"] == "content":
                assistant_content_buffer.append(event["token"])
            yield emit(event)

    # 3. Medium — tool check → agentic loop
    elif complexity == "medium":
        yield emit({"type": "status", "message": "Thinking..."})

        tools = _get_tools(message, active_tools, tracer)
        tool_names = [t["name"] for t in tools]

        messages.append({"role": "user", "content": message})

        for event in executor.run(messages, tools=tools, tracer=tracer):
            if event["type"] == "content":
                assistant_content_buffer.append(event["token"])
            yield emit(event)

        session_store.update_fixed(conversation_id, {"active_tools": tool_names})

    # 4. Complex — planner + per-step execution + synthesizer
    elif complexity == "complex":
        yield emit({"type": "status", "message": "Planning your request..."})

        steps = planner_mod.generate_steps(message, tracer)
        plan_id, step_infos = planner_mod.create_plan(conversation_id, user_id, message, steps)

        all_tool_names = list(active_tools)
        step_results = []
        results_by_num = {}  # step_number -> result text, for dependency lookup

        limit_hit = False
        for i, (step_id, step_num, step_desc, deps) in enumerate(step_infos):
            # Re-check the cap between steps so a complex turn can't blow far past it.
            allowed, info = spend.check_allowed(user_id, is_registered)
            if not allowed:
                yield emit({"type": "limit_exceeded", "scope": info.get("scope"), "message": info.get("message")})
                limit_hit = True
                break

            yield emit({"type": "status", "message": f"Step {i + 1} of {len(step_infos)}: {step_desc}"})

            step_tools = _get_tools(step_desc, active_tools, tracer)
            all_tool_names.extend(t["name"] for t in step_tools if t["name"] not in all_tool_names)

            # Inject only the results this step declared a dependency on
            context_parts = [
                f"Result of step {d}:\n{results_by_num[d]}"
                for d in deps if d in results_by_num
            ]
            if context_parts:
                step_input = (
                    "Context from previous steps:\n\n"
                    + "\n\n".join(context_parts)
                    + f"\n\nNow do this step:\n{step_desc}"
                )
            else:
                step_input = step_desc

            step_messages = messages + [{"role": "user", "content": step_input}]
            step_content = []
            for event in executor.run(step_messages, tools=step_tools, tracer=tracer):
                if event["type"] == "content":
                    step_content.append(event["token"])

            step_result = "".join(step_content)
            step_results.append(step_result)
            results_by_num[step_num] = step_result
            planner_mod.complete_step(step_id, step_result)

        if not limit_hit:
            yield emit({"type": "status", "message": "Synthesizing results..."})

            for event in planner_mod.synthesize(message, [d for _, _, d, _ in step_infos], step_results, messages, tracer):
                if event["type"] == "content":
                    assistant_content_buffer.append(event["token"])
                yield emit(event)

            planner_mod.complete_plan(plan_id)
            session_store.update_fixed(conversation_id, {"active_tools": all_tool_names})

    yield emit({"type": "done"})

    # Save messages + summarize in background
    full_response = "".join(assistant_content_buffer)

    def _background(conversation_id, user_id, message, full_response):
        _save_messages(conversation_id, message, full_response)
        summarizer.summarize_and_save(conversation_id)
        memory_store.extract_and_save(user_id, message, full_response)

    threading.Thread(
        target=_background,
        args=(conversation_id, user_id, message, full_response),
        daemon=True,
    ).start()
