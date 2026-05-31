import json
import llm_client

SYSTEM_PROMPT = """You are a request analyzer. Given a user message and conversation token count, output JSON only.

Determine:
1. complexity:
   - "simple" if Claude can answer from its training data or conversation history alone (greetings, explanations, follow-ups)
   - "medium" if it needs tools but no multi-step planning (search web, analyze a file, calculate)
   - "complex" if it needs a multi-step plan with multiple distinct tasks (research + analyze + write report)
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
