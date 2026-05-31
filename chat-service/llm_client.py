import os
from typing import Generator

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
MAIN_MODEL = os.getenv("MAIN_MODEL", "claude-sonnet-4-6")
HAIKU_MODEL = os.getenv("HAIKU_MODEL", "claude-haiku-4-5-20251001")

# Price per 1M tokens (input, output) in USD
PRICE_TABLE = {
    "gpt-4o":                        (2.50,  10.00),
    "gpt-4o-mini":                   (0.15,   0.60),
    "claude-sonnet-4-6":             (3.00,  15.00),
    "claude-haiku-4-5-20251001":     (0.80,   4.00),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICE_TABLE.get(model, (0, 0))
    return (input_tokens / 1_000_000 * prices[0]) + (output_tokens / 1_000_000 * prices[1])


def _get_anthropic():
    import anthropic
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _get_openai(azure=False):
    from openai import AzureOpenAI, OpenAI
    if azure:
        return AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _main_model():
    if PROVIDER == "azure":
        return os.getenv("AZURE_MAIN_MODEL", "gpt-4o")
    return MAIN_MODEL


def _haiku_model():
    if PROVIDER == "azure":
        return os.getenv("AZURE_HAIKU_MODEL", "gpt-4o-mini")
    return HAIKU_MODEL


def call(messages: list, tools: list = None, model: str = None) -> dict:
    model = model or _main_model()

    if PROVIDER == "anthropic":
        client = _get_anthropic()
        kwargs = {"model": model, "max_tokens": 4096, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        response = client.messages.create(**kwargs)
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        return {
            "content": response.content[0].text if response.content else "",
            "stop_reason": response.stop_reason,
            "tool_calls": [b for b in response.content if b.type == "tool_use"],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": model,
                "cost_usd": calculate_cost(model, input_tokens, output_tokens),
            },
        }

    else:
        client = _get_openai(azure=(PROVIDER == "azure"))
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        return {
            "content": choice.message.content or "",
            "stop_reason": choice.finish_reason,
            "tool_calls": choice.message.tool_calls or [],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": model,
                "cost_usd": calculate_cost(model, input_tokens, output_tokens),
            },
        }


def stream(messages: list, tools: list = None, model: str = None) -> Generator:
    model = model or _main_model()

    if PROVIDER == "anthropic":
        client = _get_anthropic()
        kwargs = {"model": model, "max_tokens": 4096, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        with client.messages.stream(**kwargs) as s:
            for text in s.text_stream:
                yield {"type": "content", "token": text}
            usage = s.get_final_message().usage
            yield {
                "type": "usage",
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "model": model,
                "cost_usd": calculate_cost(model, usage.input_tokens, usage.output_tokens),
            }

    else:
        client = _get_openai(azure=(PROVIDER == "azure"))
        kwargs = {"model": model, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
        if tools:
            kwargs["tools"] = tools
        for chunk in client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield {"type": "content", "token": delta.content}
            if chunk.usage:
                yield {
                    "type": "usage",
                    "input_tokens": chunk.usage.prompt_tokens,
                    "output_tokens": chunk.usage.completion_tokens,
                    "model": model,
                    "cost_usd": calculate_cost(model, chunk.usage.prompt_tokens, chunk.usage.completion_tokens),
                }


def call_haiku(messages: list) -> dict:
    return call(messages, model=_haiku_model())
