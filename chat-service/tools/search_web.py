import os

DEFINITION = {
    "name": "search_web",
    "description": "Search the internet for current news, facts, prices, documentation, or any up-to-date information not in the model's training data. Use whenever the request needs real-time or external information.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query, e.g. 'current AWS EC2 t3.micro price'"
            }
        },
        "required": ["query"]
    },
    "state_schema": {},
    "response_types": ["text"],
}

TAVILY_URL = "https://api.tavily.com/search"
MAX_RESULTS = 5
SNIPPET_LIMIT = 500  # cap each result's content to keep token usage down


def handler(params: dict, state: dict) -> dict:
    import httpx

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "Web search is not configured (TAVILY_API_KEY missing)."}

    query = params.get("query", "").strip()
    if not query:
        return {"error": "No search query provided."}

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": MAX_RESULTS,
        "include_answer": True,
    }

    try:
        resp = httpx.post(TAVILY_URL, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"Search failed ({e.response.status_code})."}
    except Exception as e:
        return {"error": f"Search failed: {e}"}

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": (r.get("content", "") or "")[:SNIPPET_LIMIT],
        }
        for r in data.get("results", [])
    ]

    return {
        "answer": data.get("answer", ""),
        "results": results,
    }
