from __future__ import annotations

import anthropic
from anthropic.types import Message, MessageParam, ToolParam

from ..config import settings
from ..logging_setup import get_logger

log = get_logger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def call_with_tools(
    *,
    model: str,
    system: str,
    messages: list[MessageParam],
    tools: list[ToolParam],
    tool_choice: dict | None = None,
    max_tokens: int = 8192,
    effort: str = "high",
) -> Message:
    client = get_client()
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": messages,
        "tools": tools,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort},
    }
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    response = await client.messages.create(**kwargs)
    log.info(
        "anthropic_call_complete",
        model=model,
        stop_reason=response.stop_reason,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_read=response.usage.cache_read_input_tokens,
        cache_creation=response.usage.cache_creation_input_tokens,
    )
    return response


async def call_text(
    *,
    model: str,
    system: str,
    user_message: str,
    max_tokens: int = 4096,
    effort: str = "medium",
) -> str:
    client = get_client()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user_message}],
        output_config={"effort": effort},
    )
    log.info(
        "anthropic_text_call_complete",
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_read=response.usage.cache_read_input_tokens,
    )
    return next((b.text for b in response.content if b.type == "text"), "")


def extract_tool_use(response: Message, tool_name: str) -> dict | None:
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return dict(block.input) if isinstance(block.input, dict) else block.input
    return None
