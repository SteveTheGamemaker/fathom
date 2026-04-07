from __future__ import annotations

import logging

from openai import AsyncOpenAI

from fathom.config import settings

log = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key or "not-set",
        )
    return _client


async def chat_json(
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.0,
) -> dict | list:
    """Send a chat completion request expecting a JSON response."""
    import json

    client = get_llm_client()
    model = model or settings.llm.model

    # Disable reasoning tokens to save compute — method depends on backend
    if "openai.com" in settings.llm.base_url:
        no_think = {"reasoning_effort": "none"}
    else:
        no_think = {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}

    response = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **no_think,
    )

    content = response.choices[0].message.content or "{}"
    # Strip markdown code fences that some models wrap around JSON
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(content)
