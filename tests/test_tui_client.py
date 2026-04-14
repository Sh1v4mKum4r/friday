"""Tests for TUI API client."""

import json

import httpx
import pytest

from friday_ai.tui.client import FridayTUIClient


@pytest.fixture
def mock_transport():
    """Create a mock transport that returns predefined responses."""
    responses = {}

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            path = request.url.path
            method = request.method

            key = f"{method} {path}"
            if key in responses:
                data = responses[key]
                return httpx.Response(200, json=data)
            return httpx.Response(404, json={"error": "not found"})

    transport = MockTransport()
    transport.responses = responses
    return transport


@pytest.fixture
def client(mock_transport):
    """Create a client with mock transport."""
    http = httpx.AsyncClient(transport=mock_transport, base_url="http://test:65535")
    return FridayTUIClient(http_client=http)


class TestFridayTUIClient:
    @pytest.mark.asyncio
    async def test_chat(self, client, mock_transport):
        mock_transport.responses["POST /chat"] = {
            "response": "Hello!",
            "provider": "ollama",
        }
        result = await client.chat("Hi")
        assert result["response"] == "Hello!"
        assert result["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_health(self, client, mock_transport):
        mock_transport.responses["GET /health"] = {
            "status": "online",
            "providers": ["ollama", "claude"],
        }
        result = await client.health()
        assert result["status"] == "online"
        assert "ollama" in result["providers"]

    @pytest.mark.asyncio
    async def test_classify(self, client, mock_transport):
        mock_transport.responses["POST /classify"] = {
            "message": "hello",
            "intent": "chat",
        }
        result = await client.classify("hello")
        assert result["intent"] == "chat"

    @pytest.mark.asyncio
    async def test_memory_list(self, client, mock_transport):
        mock_transport.responses["POST /memory/list"] = {
            "entries": ["user likes dark themes", "user uses arch"],
        }
        result = await client.memory_list()
        assert len(result["entries"]) == 2

    @pytest.mark.asyncio
    async def test_mcp_status(self, client, mock_transport):
        mock_transport.responses["GET /mcp/status"] = {
            "servers": ["dev", "files"],
            "tools": [{"name": "git_status", "server": "dev"}],
        }
        result = await client.mcp_status()
        assert "dev" in result["servers"]

    @pytest.mark.asyncio
    async def test_session_save(self, client, mock_transport):
        mock_transport.responses["POST /session/save"] = {"status": "saved"}
        result = await client.session_save()
        assert result["status"] == "saved"

    @pytest.mark.asyncio
    async def test_session_load(self, client, mock_transport):
        mock_transport.responses["POST /session/load"] = {"status": "loaded"}
        result = await client.session_load()
        assert result["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_reload(self, client, mock_transport):
        mock_transport.responses["POST /reload"] = {
            "reloaded": 21,
            "tools": ["run_shell", "file_read"],
        }
        result = await client.reload()
        assert result["reloaded"] == 21

    @pytest.mark.asyncio
    async def test_mcp_reconnect(self, client, mock_transport):
        mock_transport.responses["POST /mcp/reconnect"] = {
            "connected": ["dev", "files"],
        }
        result = await client.mcp_reconnect()
        assert "dev" in result["connected"]

    @pytest.mark.asyncio
    async def test_context(self, client, mock_transport):
        mock_transport.responses["GET /context"] = {"context": "system prompt..."}
        result = await client.context()
        assert "context" in result

    @pytest.mark.asyncio
    async def test_memory_forget(self, client, mock_transport):
        mock_transport.responses["POST /memory/forget"] = {
            "status": "ok",
            "forgot": "dark themes",
        }
        result = await client.memory_forget("dark themes")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_memory_clear(self, client, mock_transport):
        mock_transport.responses["POST /memory/clear"] = {"status": "cleared"}
        result = await client.memory_clear()
        assert result["status"] == "cleared"

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, mock_transport):
        """Client should handle connection failures gracefully."""
        http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(500)),
            base_url="http://test:65535",
        )
        client = FridayTUIClient(http_client=http)
        result = await client.health()
        assert result is None
