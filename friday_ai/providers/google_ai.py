"""Google AI mode provider.

Uses the AI Mode API to get Google AI-powered responses with sources.
Falls back to opening Google in the browser if the API is unavailable.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.parse

import httpx

from .base import BaseProvider, ProviderResponse


class GoogleAIProvider(BaseProvider):
    """Provider that uses Google AI Mode API for search-augmented responses."""

    name: str = "google_ai"

    def __init__(self, api_url: str = "https://app.aimodeapi.com/api/dee84882-e909-411a-88ed-71bacb36e6ec"):
        self.api_url = api_url

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.api_url,
                    json={"query": prompt},
                    headers={"Content-Type": "application/json"},
                )

            if resp.status_code != 200:
                return self._fallback_browser(prompt)

            data = resp.json()
            response_data = data.get("response", {}).get("data", {})
            body = response_data.get("response_body", "")
            sources = response_data.get("sources", [])

            if not body:
                return self._fallback_browser(prompt)

            # Clean up markdown — remove base64 images
            body = re.sub(r'!\[.*?\]\(data:image.*?\)', '', body)
            body = re.sub(r'\n{3,}', '\n\n', body).strip()

            # Append sources
            if sources:
                body += "\n\n**Sources:**"
                for s in sources[:5]:
                    title = s.get("title", "")
                    url = s.get("url", "").split("#")[0]  # Remove fragment
                    if title and url:
                        body += f"\n- [{title}]({url})"

            return ProviderResponse(
                content=body,
                provider_name=self.name,
            )

        except (httpx.TimeoutException, httpx.ConnectError):
            return self._fallback_browser(prompt)
        except Exception as e:
            return ProviderResponse(
                content=f"Google AI error: {e}",
                provider_name=self.name,
            )

    def _fallback_browser(self, prompt: str) -> ProviderResponse:
        """Fall back to opening Google AI mode in the browser."""
        query = urllib.parse.quote_plus(prompt)
        url = f"https://www.google.com/search?q={query}&udm=50"
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ProviderResponse(
            content=f"Opened Google AI mode in browser for: {prompt}",
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    self.api_url,
                    json={"query": "test"},
                    headers={"Content-Type": "application/json"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def supports_tools(self) -> bool:
        return False
