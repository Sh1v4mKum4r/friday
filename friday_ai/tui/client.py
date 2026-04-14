"""Async HTTP client for the Friday API."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx


class FridayTUIClient:
    """Wraps all Friday API endpoints with async methods."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 65535,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is not None:
            self._http = http_client
            self._owns_client = False
        else:
            self._http = httpx.AsyncClient(
                base_url=f"http://{host}:{port}",
                timeout=120.0,
            )
            self._owns_client = True

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._http.aclose()

    async def _get(self, path: str) -> dict[str, Any] | None:
        try:
            r = await self._http.get(path)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    async def _post(self, path: str, **kwargs: Any) -> dict[str, Any] | None:
        try:
            r = await self._http.post(path, **kwargs)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    # --- Chat ---

    async def chat(self, message: str, force_provider: str | None = None, race: bool = False) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"message": message}
        if force_provider:
            payload["force_provider"] = force_provider
        if race:
            payload["race"] = True
        return await self._post("/chat", json=payload)

    async def chat_stream(self, message: str, force_provider: str | None = None) -> AsyncIterator[dict[str, Any]]:
        payload: dict[str, Any] = {"message": message}
        if force_provider:
            payload["force_provider"] = force_provider
        try:
            async with self._http.stream("POST", "/chat/stream", json=payload) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
        except httpx.HTTPError:
            yield {"token": "", "done": True, "error": "stream connection failed"}

    # --- Health ---
    async def health(self) -> dict[str, Any] | None:
        return await self._get("/health")

    # --- Classification ---
    async def classify(self, message: str) -> dict[str, Any] | None:
        return await self._post("/classify", json={"message": message})

    # --- Context ---
    async def context(self) -> dict[str, Any] | None:
        return await self._get("/context")

    # --- Session ---
    async def session_save(self) -> dict[str, Any] | None:
        return await self._post("/session/save")

    async def session_load(self) -> dict[str, Any] | None:
        return await self._post("/session/load")

    # --- Memory ---
    async def memory_list(self) -> dict[str, Any] | None:
        return await self._post("/memory/list")

    async def memory_forget(self, keyword: str) -> dict[str, Any] | None:
        return await self._post("/memory/forget", params={"keyword": keyword})

    async def memory_clear(self) -> dict[str, Any] | None:
        return await self._post("/memory/clear")

    # --- Tools ---
    async def reload(self) -> dict[str, Any] | None:
        return await self._post("/reload")

    # --- MCP ---
    async def mcp_status(self) -> dict[str, Any] | None:
        return await self._get("/mcp/status")

    async def mcp_reconnect(self) -> dict[str, Any] | None:
        return await self._post("/mcp/reconnect")
