"""Ollama provider implementation for Friday AI.

Communicates with a local Ollama instance via its HTTP chat API.
Uses httpx.AsyncClient for all network I/O.
"""

from __future__ import annotations

import httpx

from .base import BaseProvider, ProviderResponse, ToolCall


class OllamaProvider(BaseProvider):
    """Provider backed by a locally-running Ollama server."""

    name: str = "ollama"

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        """POST to Ollama's /api/chat endpoint and return a ProviderResponse.

        The message list is constructed as:
            [system_message (if any)] + history + [user message]
        """
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )

        data = response.json()
        message = data.get("message", {})

        content: str = message.get("content", "")

        raw_tool_calls: list[dict] = message.get("tool_calls", []) or []
        tool_calls: list[ToolCall] = [
            ToolCall(
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments", {}),
            )
            for tc in raw_tool_calls
        ]

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        """Return True if Ollama responds with HTTP 200 on /api/tags."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    def supports_tools(self) -> bool:
        """Ollama supports structured tool/function calling."""
        return True
