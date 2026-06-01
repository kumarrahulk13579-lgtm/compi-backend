import json
import llm_client

SYSTEM_PROMPT = """You are a tool analyzer. Given a user message and the currently active tools, decide if the active tools are enough or if new tools are needed.

Output JSON only:
{
  "tools_sufficient": true/false,
  "new_tool_descriptions": ["description1", "description2"]
}

Rules:
- If active tools can handle the request, set tools_sufficient=true and new_tool_descriptions=[]
- If new tools are needed, set tools_sufficient=false and list short descriptions of what each needed tool should do
- Each description should be one sentence describing the tool's capability (used for semantic search)
- Be specific — "search the web for real-time information" not just "search"
- List only tools that are actually missing, not ones already active"""


def run(message: str, active_tools: list[str]) -> dict:
    user_content = f"Message: {message}\nActive tools: {active_tools if active_tools else 'none'}"

    response = llm_client.call_haiku([
        {"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{user_content}"}
    ])

    try:
        result = json.loads(response["content"])
        return {
            "tools_sufficient": result.get("tools_sufficient", False),
            "new_tool_descriptions": result.get("new_tool_descriptions", []),
            "usage": response["usage"],
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "tools_sufficient": False,
            "new_tool_descriptions": [message],
            "usage": response["usage"],
        }
