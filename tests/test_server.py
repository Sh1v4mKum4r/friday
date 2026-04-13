"""Tests for friday_ai/server.py — TDD.

Covers:
1. /health endpoint returns 200 with status "online"
2. /chat endpoint returns response from agent
3. /context endpoint returns context dump
4. /reload endpoint reloads tools and returns count
5. /memory/list, /memory/forget, /memory/clear endpoints
6. /session/save and /session/load endpoints
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import ASGITransport

from friday_ai.providers.base import ProviderResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_CONFIG_TOML = """\
[providers]
ollama_model = "qwen2.5:7b"
ollama_url = "http://localhost:11434"
gemini_api_key = ""
claude_api_key = ""
openai_api_key = ""

[server]
port = 65535
host = "127.0.0.1"

[behavior]
auto_escalate = true
max_workers = 4

[de]
override = ""

[voice]
enabled = false
"""


def _write_config(directory: Path) -> Path:
    """Write a minimal config.toml into *directory* and return its path."""
    config_path = directory / "config.toml"
    config_path.write_text(MINIMAL_CONFIG_TOML)
    return config_path


def _make_app(config_dir: Path, data_dir: Path, config_path: Path):
    """Create a FastAPI app with patched config/data dirs."""
    with (
        patch("friday_ai.server.get_config_dir", return_value=config_dir),
        patch("friday_ai.server.get_data_dir", return_value=data_dir),
        patch("friday_ai.server.ensure_dirs"),
    ):
        from friday_ai.server import create_app
        return create_app(config_path=config_path)


# ---------------------------------------------------------------------------
# 1. /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_status_online(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")

            data = response.json()
            assert data["status"] == "online"

    @pytest.mark.asyncio
    async def test_health_returns_providers_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")

            data = response.json()
            assert "providers" in data
            assert isinstance(data["providers"], list)
            # Ollama is always added first
            assert "ollama" in data["providers"]


# ---------------------------------------------------------------------------
# 2. /chat
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    @pytest.mark.asyncio
    async def test_chat_returns_200(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            # Mock the agent.chat method
            mock_response = ProviderResponse(
                content="Hello from Friday!", provider_name="ollama"
            )
            app.state.agent.chat = AsyncMock(return_value=mock_response)

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/chat", json={"message": "Hello Friday"}
                )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_returns_response_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            mock_response = ProviderResponse(
                content="Hello from Friday!", provider_name="ollama"
            )
            app.state.agent.chat = AsyncMock(return_value=mock_response)

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/chat", json={"message": "Hello Friday"}
                )

            data = response.json()
            assert data["response"] == "Hello from Friday!"
            assert data["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_chat_passes_message_to_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            mock_response = ProviderResponse(content="OK", provider_name="ollama")
            mock_chat = AsyncMock(return_value=mock_response)
            app.state.agent.chat = mock_chat

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/chat", json={"message": "Test message XYZ"})

            mock_chat.assert_awaited_once()
            call_kwargs = mock_chat.call_args
            # Message should be passed either as positional or keyword arg
            if call_kwargs.args:
                assert "Test message XYZ" in call_kwargs.args[0]
            else:
                assert call_kwargs.kwargs.get("message") == "Test message XYZ"

    @pytest.mark.asyncio
    async def test_chat_passes_force_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            mock_response = ProviderResponse(content="OK", provider_name="gemini")
            mock_chat = AsyncMock(return_value=mock_response)
            app.state.agent.chat = mock_chat

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post(
                    "/chat",
                    json={"message": "Hello", "force_provider": "gemini"},
                )

            mock_chat.assert_awaited_once()
            call_kwargs = mock_chat.call_args
            assert call_kwargs.kwargs.get("force_provider") == "gemini"


# ---------------------------------------------------------------------------
# 3. /context
# ---------------------------------------------------------------------------


class TestContextEndpoint:
    @pytest.mark.asyncio
    async def test_context_returns_200(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.get_context_dump = MagicMock(return_value="=== Context ===")

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/context")

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_context_returns_context_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.get_context_dump = MagicMock(
                return_value="=== System Prompt ==="
            )

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/context")

            data = response.json()
            assert "context" in data
            assert "=== System Prompt ===" in data["context"]


# ---------------------------------------------------------------------------
# 4. /reload
# ---------------------------------------------------------------------------


class TestReloadEndpoint:
    @pytest.mark.asyncio
    async def test_reload_returns_200(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            # Mock tool_loader.reload to return a list of tools
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            app.state.tool_loader.reload = MagicMock(return_value=[mock_tool])

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/reload")

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reload_returns_count_and_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)

            mock_tool1 = MagicMock()
            mock_tool1.name = "tool_alpha"
            mock_tool2 = MagicMock()
            mock_tool2.name = "tool_beta"
            app.state.tool_loader.reload = MagicMock(
                return_value=[mock_tool1, mock_tool2]
            )

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/reload")

            data = response.json()
            assert data["reloaded"] == 2
            assert "tool_alpha" in data["tools"]
            assert "tool_beta" in data["tools"]


# ---------------------------------------------------------------------------
# 5. /memory endpoints
# ---------------------------------------------------------------------------


class TestMemoryEndpoints:
    @pytest.mark.asyncio
    async def test_memory_list_returns_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.memory.list_memory = MagicMock(
                return_value=["fact one", "fact two"]
            )

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/memory/list")

            assert response.status_code == 200
            data = response.json()
            assert data["entries"] == ["fact one", "fact two"]

    @pytest.mark.asyncio
    async def test_memory_forget_removes_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.memory.forget_memory = MagicMock()

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/memory/forget?keyword=python")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["forgot"] == "python"
            app.state.agent.memory.forget_memory.assert_called_once_with("python")

    @pytest.mark.asyncio
    async def test_memory_clear_clears_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.memory.clear_memory = MagicMock()

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/memory/clear")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cleared"
            app.state.agent.memory.clear_memory.assert_called_once()


# ---------------------------------------------------------------------------
# 6. /session endpoints
# ---------------------------------------------------------------------------


class TestSessionEndpoints:
    @pytest.mark.asyncio
    async def test_session_save_returns_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.save_session = MagicMock()

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/session/save")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "saved"
            app.state.agent.save_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_load_returns_loaded_when_session_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.load_session = MagicMock(return_value=True)

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/session/load")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_session_load_returns_no_session_found_when_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_dir = tmp_path / "config"
            data_dir = tmp_path / "data"
            config_dir.mkdir()
            data_dir.mkdir()

            config_path = _write_config(config_dir)

            app = _make_app(config_dir, data_dir, config_path)
            app.state.agent.load_session = MagicMock(return_value=False)

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/session/load")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "no session found"
