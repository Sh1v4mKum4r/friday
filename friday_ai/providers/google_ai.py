"""Google AI mode provider.

Tries multiple Google AI search backends in order:
1. SerpAPI (google_ai_mode engine) — if SERPAPI_KEY is set
2. AI Mode API (free, community) — no key needed
3. Browser fallback — opens Google AI mode in browser
"""

from __future__ import annotations

import os
import re
import subprocess
import urllib.parse

import httpx

from .base import BaseProvider, ProviderResponse


class GoogleAIProvider(BaseProvider):
    """Provider that uses Google AI search for live, sourced answers."""

    name: str = "google_ai"

    def __init__(
        self,
        aimodeapi_url: str = "https://app.aimodeapi.com/api/dee84882-e909-411a-88ed-71bacb36e6ec",
        serpapi_key: str = "",
    ):
        self.aimodeapi_url = aimodeapi_url
        self.serpapi_key = serpapi_key or os.environ.get("SERPAPI_KEY", "")

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        # Try SerpAPI first (if key available)
        if self.serpapi_key:
            result = await self._try_serpapi(prompt)
            if result:
                return result

        # Try AI Mode API (free, no key)
        result = await self._try_aimodeapi(prompt)
        if result:
            return result

        # Fallback: open browser
        return self._fallback_browser(prompt)

    async def _try_serpapi(self, prompt: str) -> ProviderResponse | None:
        """Try SerpAPI google_ai_mode engine."""
        try:
            params = {
                "engine": "google_ai_mode",
                "q": prompt,
                "api_key": self.serpapi_key,
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get("https://serpapi.com/search", params=params)

            if resp.status_code != 200:
                return None

            data = resp.json()

            # Extract AI mode response
            ai_response = data.get("ai_mode_response", {})
            text = ai_response.get("text", "")

            # Also try snippets if no AI response
            if not text:
                snippets = data.get("organic_results", [])
                if snippets:
                    parts = []
                    for s in snippets[:3]:
                        title = s.get("title", "")
                        snippet = s.get("snippet", "")
                        link = s.get("link", "")
                        parts.append(f"**{title}**\n{snippet}\n{link}")
                    text = "\n\n".join(parts)

            if not text:
                return None

            # Clean up
            text = re.sub(r'\n{3,}', '\n\n', text).strip()

            # Add sources if available
            sources = ai_response.get("sources", [])
            if sources:
                text += "\n\n**Sources:**"
                for s in sources[:5]:
                    title = s.get("title", "")
                    url = s.get("link", s.get("url", ""))
                    if title and url:
                        text += f"\n- [{title}]({url})"

            return ProviderResponse(content=text, provider_name="google_ai (serpapi)")

        except Exception:
            return None

    async def _try_aimodeapi(self, prompt: str) -> ProviderResponse | None:
        """Try the free AI Mode API."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.aimodeapi_url,
                    json={"query": prompt},
                    headers={"Content-Type": "application/json"},
                )

            if resp.status_code != 200:
                return None

            data = resp.json()
            response_data = data.get("response", {}).get("data", {})
            body = response_data.get("response_body", "")
            sources = response_data.get("sources", [])

            if not body:
                return None

            # Clean up — remove base64 images
            body = re.sub(r'!\[.*?\]\(data:image.*?\)', '', body)
            body = re.sub(r'\n{3,}', '\n\n', body).strip()

            # Append sources
            if sources:
                body += "\n\n**Sources:**"
                for s in sources[:5]:
                    title = s.get("title", "")
                    url = s.get("url", "").split("#")[0]
                    if title and url:
                        body += f"\n- [{title}]({url})"

            return ProviderResponse(content=body, provider_name="google_ai")

        except Exception:
            return None

    def _fallback_browser(self, prompt: str) -> ProviderResponse:
        """Open Google AI mode in the browser."""
        query = urllib.parse.quote_plus(prompt)
        url = f"https://www.google.com/search?q={query}&udm=50"
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ProviderResponse(
            content=f"Opened Google AI mode in browser for: {prompt}",
            provider_name="google_ai (browser)",
        )

    async def is_available(self) -> bool:
        """Check if any Google AI backend is reachable."""
        if self.serpapi_key:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        "https://serpapi.com/search",
                        params={"engine": "google_ai_mode", "q": "test", "api_key": self.serpapi_key},
                    )
                    if resp.status_code == 200:
                        return True
            except Exception:
                pass

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    self.aimodeapi_url,
                    json={"query": "test"},
                    headers={"Content-Type": "application/json"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def supports_tools(self) -> bool:
        return False
