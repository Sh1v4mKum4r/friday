"""Web search provider for Friday AI.

Uses the `googler` CLI tool to perform web searches.
Returns plain-text search results as the provider response content.
Does not support structured tool calling.
"""

from __future__ import annotations

import shutil
import subprocess

from .base import BaseProvider, ProviderResponse, ToolCall


class WebSearchProvider(BaseProvider):
    """Provider that runs web searches via the `googler` CLI tool."""

    name: str = "web_search"

    def __init__(self, num_results: int = 5) -> None:
        self.num_results = num_results

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        """Run `googler` with the given prompt as the search query."""
        result = subprocess.run(
            [
                "googler",
                "--noprompt",
                "-n", str(self.num_results),
                "-C",          # disable colour output for clean parsing
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()

        return ProviderResponse(
            content=output,
            tool_calls=[],
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        """Return True if `googler` binary is on PATH."""
        return shutil.which("googler") is not None

    def supports_tools(self) -> bool:
        """Web search provider does not support structured tool calling."""
        return False
