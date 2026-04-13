"""OpenAI provider implementation for Friday AI.

Named openai_provider.py (not openai.py) to avoid shadowing the `openai` package.
Uses the OpenAI Chat Completions REST API via httpx (no SDK).
"""

from __future__ import annotations

import json

import httpx

from .base import BaseProvider, ProviderResponse, ToolCall

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(BaseProvider):
    """Provider backed by the OpenAI Chat Completions REST API (pure httpx)."""

    name: str = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
    ) -> None:
        self.api_key = api_key
        self.model = model

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        """POST to OpenAI /v1/chat/completions and return a ProviderResponse."""
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                _OPENAI_API_URL,
                json=payload,
                headers=headers,
            )

        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return ProviderResponse(content="", provider_name=self.name)

        message = choices[0].get("message", {})
        content: str = message.get("content") or ""

        raw_tool_calls: list[dict] = message.get("tool_calls") or []
        tool_calls: list[ToolCall] = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    name=fn.get("name", ""),
                    arguments=arguments,
                )
            )

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        """Return True if the OpenAI API responds with a valid model list."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers=headers,
                )
            return resp.status_code == 200
        except Exception:
            return False

    def supports_tools(self) -> bool:
        """OpenAI Chat Completions API supports structured tool/function calling."""
        return True
