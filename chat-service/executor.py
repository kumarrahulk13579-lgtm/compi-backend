import json
import os
import llm_client
import tool_registry

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
MAX_ITERATIONS = 10


def _assistant_msg(content: str, tool_calls: list) -> dict:
    if PROVIDER == "anthropic":
        blocks = []
        if content:
            blocks.append({"type": "text", "text": content})
        for tc in tool_calls:
            blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["params"]})
        return {"role": "assistant", "content": blocks}
    else:
        return {
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["params"])}}
                for tc in tool_calls
            ],
        }


def _tool_result_msgs(tool_calls: list, results: list) -> list:
    if PROVIDER == "anthropic":
        return [{
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tc["id"], "content": json.dumps(result)}
                for tc, result in zip(tool_calls, results)
            ],
        }]
    else:
        return [
            {"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)}
            for tc, result in zip(tool_calls, results)
        ]


def run(messages: list, tools: list, tracer=None):
    """Agentic loop. Yields SSE-style event dicts. Streams LLM tokens to user."""
    formatted_tools = llm_client.format_tools(tools) if tools else None

    for _ in range(MAX_ITERATIONS):
        content_buffer = []
        tool_calls = []

        for event in llm_client.stream(messages, formatted_tools):
            if event["type"] == "content":
                content_buffer.append(event["token"])
                yield event
            elif event["type"] == "tool_call":
                tool_calls.append(event)
            elif event["type"] == "usage":
                if tracer:
                    tracer.log("llm_call", output={"tool_calls": len(tool_calls)}, cost_usd=event.get("cost_usd"))
                yield event

        if not tool_calls:
            break

        full_content = "".join(content_buffer)
        messages.append(_assistant_msg(full_content, tool_calls))

        results = []
        for tc in tool_calls:
            yield {"type": "status", "message": f"Using {tc['name']}..."}
            handler = tool_registry.get_handler(tc["name"])
            if handler:
                result = handler(tc["params"], {})
            else:
                result = {"error": f"Tool '{tc['name']}' not found"}
            results.append(result)
            if tracer:
                tracer.log(f"tool:{tc['name']}", input=tc["params"], output=result)

        messages.extend(_tool_result_msgs(tool_calls, results))
