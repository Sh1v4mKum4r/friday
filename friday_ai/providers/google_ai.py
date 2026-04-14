"""Google AI mode provider.

Opens Google AI mode (google.com/search?q=...&udm=50) in the browser
for the query. Returns a message telling the user to check the browser.
"""

from __future__ import annotations

import subprocess
import urllib.parse

from .base import BaseProvider, ProviderResponse


class GoogleAIProvider(BaseProvider):
    """Provider that opens Google AI mode in the default browser."""

    name: str = "google_ai"

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        query = urllib.parse.quote_plus(prompt)
        url = f"https://www.google.com/search?q={query}&udm=50"

        try:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return ProviderResponse(
                content=f"Opened Google AI mode for: {prompt}",
                provider_name=self.name,
            )
        except Exception as e:
            return ProviderResponse(
                content=f"Error opening browser: {e}",
                provider_name=self.name,
            )

    async def is_available(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return False
