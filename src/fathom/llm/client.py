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

    response = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    content = response.choices[0].message.content or "{}"
    return json.loads(content)
