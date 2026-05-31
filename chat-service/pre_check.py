import json
import llm_client

SYSTEM_PROMPT = """You are a request analyzer. Given a user message and conversation token count, output JSON only.

Determine:
1. complexity:
   - "simple" if Claude can answer entirely on its own using training data or conversation history — no external data, no actions, no tools needed
   - "medium" if Claude cannot answer alone and needs a tool or external data to complete the request — anything requiring real-time data, external systems, user files, or actions in the world, but achievable in one step
   - "complex" if completing the request requires multiple distinct steps or tools that depend on each other — plan first, then execute each part separately
2. needs_summary: true if token_count > 3000, else false

Output format (JSON only, no extra text):
{"complexity": "simple|medium|complex", "needs_summary": true|false}"""


def run(message: str, token_count: int) -> dict:
    response = llm_client.call_haiku([
        {"role": "user", "content": f"{SYSTEM_PROMPT}\n\nMessage: {message}\nToken count: {token_count}"}
    ])

    try:
        result = json.loads(response["content"])
        return {
            "complexity": result.get("complexity", "simple"),
            "needs_summary": result.get("needs_summary", False),
            "usage": response["usage"],
        }
    except (json.JSONDecodeError, KeyError):
        return {"complexity": "simple", "needs_summary": False, "usage": response["usage"]}
