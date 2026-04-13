"""Gemini provider implementations for Friday AI.

Two variants:
- GeminiProvider: uses the Gemini REST API via httpx (no SDK).
- GeminiCLIProvider: shells out to the `gemini` CLI tool.
"""

from __future__ import annotations

import json
import re
import subprocess

import httpx

from .base import BaseProvider, ProviderResponse, ToolCall

_TOOL_CALL_RE = re.compile(
    r"TOOL_CALL:\s*(\{.*?\})", re.DOTALL
)

_GEMINI_API_BASE = (
    "https://generativelanguage.googleapis.com/v1beta/models"
)


def _openai_tools_to_gemini(tools: list[dict]) -> list[dict]:
    """Convert OpenAI-compatible tool schemas to Gemini functionDeclarations."""
    declarations: list[dict] = []
    for tool in tools:
        fn = tool.get("function", {})
        declarations.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            }
        )
    return declarations


def _history_to_gemini(history: list[dict]) -> list[dict]:
    """Convert OpenAI-style history to Gemini contents format."""
    contents: list[dict] = []
    for msg in history:
        role = msg.get("role", "user")
        # Gemini uses "model" instead of "assistant"
        if role == "assistant":
            role = "model"
        contents.append(
            {
                "role": role,
                "parts": [{"text": msg.get("content", "")}],
            }
        )
    return contents


class GeminiProvider(BaseProvider):
    """Provider backed by the Gemini REST API (no SDK, pure httpx)."""

    name: str = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
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
        """POST to Gemini generateContent endpoint and return a ProviderResponse."""
        url = f"{_GEMINI_API_BASE}/{self.model}:generateContent?key={self.api_key}"

        contents = _history_to_gemini(history)
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload: dict = {"contents": contents}

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        if tools:
            payload["tools"] = [
                {"functionDeclarations": _openai_tools_to_gemini(tools)}
            ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)

        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return ProviderResponse(content="", provider_name=self.name)

        parts = candidates[0].get("content", {}).get("parts", [])

        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for part in parts:
            if "text" in part:
                content_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    )
                )

        return ProviderResponse(
            content="\n".join(content_parts),
            tool_calls=tool_calls,
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        """Return True if the Gemini API responds with a valid model list."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
            return resp.status_code == 200
        except Exception:
            return False

    def supports_tools(self) -> bool:
        """Gemini REST API supports structured function calling."""
        return True


class GeminiCLIProvider(BaseProvider):
    """Provider that shells out to the `gemini` CLI binary."""

    name: str = "gemini-cli"

    def _build_prompt(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> str:
        """Build a compact prompt for CLI — skip system prompt, minimal tools."""
        parts: list[str] = []

        # Only include last 3 history messages to keep prompt short
        for msg in history[-3:]:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")[:500]
            parts.append(f"[{role}]: {content}")

        if tools:
            # Compact tool list — just names and descriptions, no schemas
            tool_lines = []
            for t in tools:
                fn = t.get("function", {})
                params = ", ".join(fn.get("parameters", {}).get("required", []))
                tool_lines.append(f"  {fn.get('name', '')}({params}): {fn.get('description', '')[:80]}")
            parts.append(
                "Tools (use TOOL_CALL: {\"name\": \"...\", \"args\": {...}} to call):\n"
                + "\n".join(tool_lines)
            )

        parts.append(prompt)
        return "\n\n".join(parts)

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        """Shell out to `gemini -p <prompt>` and parse the response."""
        full_prompt = self._build_prompt(prompt, tools, history, system_prompt)

        try:
            result = subprocess.run(
                ["gemini", "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Gemini CLI timed out")
        except FileNotFoundError:
            raise RuntimeError("Gemini CLI not found")
        output = result.stdout.strip()

        tool_calls: list[ToolCall] = []
        for match in _TOOL_CALL_RE.finditer(output):
            try:
                data = json.loads(match.group(1))
                tool_calls.append(
                    ToolCall(
                        name=data.get("name", ""),
                        arguments=data.get("args", {}),
                    )
                )
            except json.JSONDecodeError:
                pass

        # Strip TOOL_CALL lines from visible content
        clean_content = _TOOL_CALL_RE.sub("", output).strip()

        return ProviderResponse(
            content=clean_content,
            tool_calls=tool_calls,
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        """Return True if `gemini` binary is on PATH."""
        import shutil

        return shutil.which("gemini") is not None

    def supports_tools(self) -> bool:
        """CLI variant uses prompt-based tool calling."""
        return True
