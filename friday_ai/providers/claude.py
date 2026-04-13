"""Claude (Anthropic) provider implementations for Friday AI.

Two variants:
- ClaudeProvider: uses the Anthropic Messages REST API via httpx (no SDK).
- ClaudeCLIProvider: shells out to the `claude` CLI tool.
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

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


def _openai_tools_to_claude(tools: list[dict]) -> list[dict]:
    """Convert OpenAI-compatible tool schemas to Anthropic input_schema format."""
    claude_tools: list[dict] = []
    for tool in tools:
        fn = tool.get("function", {})
        claude_tools.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {}),
            }
        )
    return claude_tools


class ClaudeProvider(BaseProvider):
    """Provider backed by the Anthropic Messages REST API (no SDK, pure httpx)."""

    name: str = "claude"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
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
        """POST to Anthropic /v1/messages and return a ProviderResponse."""
        messages = list(history)
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "max_tokens": 8096,
            "messages": messages,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = _openai_tools_to_claude(tools)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                _ANTHROPIC_API_URL,
                json=payload,
                headers=headers,
            )

        data = response.json()

        content_blocks = data.get("content", [])
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in content_blocks:
            block_type = block.get("type", "")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        return ProviderResponse(
            content="\n".join(text_parts),
            tool_calls=tool_calls,
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        """Return True if the Anthropic API responds (model list endpoint)."""
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers=headers,
                )
            return resp.status_code == 200
        except Exception:
            return False

    def supports_tools(self) -> bool:
        """Claude REST API supports structured tool/function calling."""
        return True


class ClaudeCLIProvider(BaseProvider):
    """Provider that shells out to the `claude` CLI binary."""

    name: str = "claude-cli"

    def _build_prompt(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> str:
        """Build a compact prompt for CLI — skip system prompt, minimal tools."""
        parts: list[str] = []

        for msg in history[-3:]:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")[:500]
            parts.append(f"[{role}]: {content}")

        if tools:
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
        """Shell out to `claude -p <prompt>` and parse the response."""
        full_prompt = self._build_prompt(prompt, tools, history, system_prompt)

        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return ProviderResponse(
                content="Claude CLI timed out.",
                provider_name=self.name,
            )
        except FileNotFoundError:
            return ProviderResponse(
                content="Claude CLI not found.",
                provider_name=self.name,
            )
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
        """Return True if `claude` binary is on PATH."""
        import shutil

        return shutil.which("claude") is not None

    def supports_tools(self) -> bool:
        """CLI variant uses prompt-based tool calling."""
        return True
