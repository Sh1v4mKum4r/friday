"""Tests for friday_ai/providers/base.py and friday_ai/providers/ollama.py — TDD.

Uses unittest.mock to patch httpx.AsyncClient so no real network calls are made.
"""
from __future__ import annotations

import json
from abc import ABC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from friday_ai.providers.base import BaseProvider, ProviderResponse, ToolCall
from friday_ai.providers.ollama import OllamaProvider


# ---------------------------------------------------------------------------
# 1. BaseProvider interface
# ---------------------------------------------------------------------------


class TestBaseProviderInterface:
    def test_base_provider_is_abstract(self):
        assert issubclass(BaseProvider, ABC)

    def test_cannot_instantiate_base_provider_directly(self):
        with pytest.raises(TypeError):
            BaseProvider()  # type: ignore[abstract]

    def test_send_message_is_abstract(self):
        assert getattr(BaseProvider.send_message, "__isabstractmethod__", False)

    def test_is_available_is_abstract(self):
        assert getattr(BaseProvider.is_available, "__isabstractmethod__", False)

    def test_supports_tools_is_abstract(self):
        assert getattr(BaseProvider.supports_tools, "__isabstractmethod__", False)

    def test_provider_response_has_content(self):
        resp = ProviderResponse(content="hello")
        assert resp.content == "hello"

    def test_provider_response_has_tool_calls_default_empty(self):
        resp = ProviderResponse(content="hello")
        assert resp.tool_calls == []

    def test_provider_response_has_provider_name_default_empty(self):
        resp = ProviderResponse(content="hello")
        assert resp.provider_name == ""

    def test_tool_call_has_name_and_arguments(self):
        tc = ToolCall(name="say_hello", arguments={"target": "world"})
        assert tc.name == "say_hello"
        assert tc.arguments == {"target": "world"}

    def test_concrete_subclass_can_be_instantiated(self):
        class ConcreteProvider(BaseProvider):
            name = "concrete"

            async def send_message(self, prompt, tools, history, system_prompt=""):
                return ProviderResponse(content="ok", provider_name=self.name)

            async def is_available(self):
                return True

            def supports_tools(self):
                return False

        p = ConcreteProvider()
        assert p.name == "concrete"
        assert p.supports_tools() is False


# ---------------------------------------------------------------------------
# 2. OllamaProvider — plain text response
# ---------------------------------------------------------------------------


class TestOllamaProviderPlainText:
    """send_message with a plain-text (no tool_calls) response from Ollama."""

    @pytest.mark.asyncio
    async def test_send_message_returns_provider_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Hello, Friday!",
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="Hi",
                tools=None,
                history=[],
                system_prompt="",
            )

        assert isinstance(result, ProviderResponse)

    @pytest.mark.asyncio
    async def test_send_message_content_matches_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Hello, Friday!",
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="Hi",
                tools=None,
                history=[],
                system_prompt="",
            )

        assert result.content == "Hello, Friday!"

    @pytest.mark.asyncio
    async def test_send_message_no_tool_calls_when_absent(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Plain response",
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="Hello",
                tools=None,
                history=[],
            )

        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_send_message_sets_provider_name(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Hi"}
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="Hello",
                tools=None,
                history=[],
            )

        assert result.provider_name == "ollama"

    @pytest.mark.asyncio
    async def test_send_message_includes_system_prompt_when_provided(self):
        """When a system_prompt is given, the POST body must include a system message."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "ok"}
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            await provider.send_message(
                prompt="Hello",
                tools=None,
                history=[],
                system_prompt="You are Friday.",
            )

        _, kwargs = mock_post.call_args
        body = kwargs.get("json", {})
        messages = body.get("messages", [])
        system_messages = [m for m in messages if m.get("role") == "system"]
        assert len(system_messages) == 1
        assert system_messages[0]["content"] == "You are Friday."

    @pytest.mark.asyncio
    async def test_send_message_posts_to_correct_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "ok"}
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider(base_url="http://localhost:11434")
            await provider.send_message(prompt="Hi", tools=None, history=[])

        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/chat"

    @pytest.mark.asyncio
    async def test_send_message_posts_stream_false(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "ok"}
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            await provider.send_message(prompt="Hi", tools=None, history=[])

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["stream"] is False

    @pytest.mark.asyncio
    async def test_send_message_includes_history_messages(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "ok"}
        }

        history = [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ]

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            await provider.send_message(prompt="new question", tools=None, history=history)

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_send_message_appends_user_prompt_last(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "ok"}
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            await provider.send_message(
                prompt="final question", tools=None, history=[]
            )

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "final question"


# ---------------------------------------------------------------------------
# 3. OllamaProvider — tool_calls response
# ---------------------------------------------------------------------------


class TestOllamaProviderToolCalls:
    """send_message when Ollama returns tool_calls in the message."""

    @pytest.mark.asyncio
    async def test_send_message_returns_tool_calls(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": {"city": "London"},
                        }
                    }
                ],
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="What's the weather in London?",
                tools=[{"type": "function", "function": {"name": "get_weather"}}],
                history=[],
            )

        assert len(result.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_send_message_tool_call_has_correct_name(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": {"city": "London"},
                        }
                    }
                ],
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="Weather?",
                tools=[],
                history=[],
            )

        assert result.tool_calls[0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_send_message_tool_call_has_correct_arguments(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": {"city": "London"},
                        }
                    }
                ],
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="Weather?",
                tools=[],
                history=[],
            )

        assert result.tool_calls[0].arguments == {"city": "London"}

    @pytest.mark.asyncio
    async def test_send_message_tool_call_items_are_tool_call_objects(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "foo", "arguments": {"x": 1}}},
                    {"function": {"name": "bar", "arguments": {"y": 2}}},
                ],
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="do stuff",
                tools=[],
                history=[],
            )

        assert all(isinstance(tc, ToolCall) for tc in result.tool_calls)

    @pytest.mark.asyncio
    async def test_send_message_multiple_tool_calls(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "foo", "arguments": {"x": 1}}},
                    {"function": {"name": "bar", "arguments": {"y": 2}}},
                ],
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.send_message(
                prompt="do stuff",
                tools=[],
                history=[],
            )

        assert len(result.tool_calls) == 2
        names = {tc.name for tc in result.tool_calls}
        assert names == {"foo", "bar"}

    @pytest.mark.asyncio
    async def test_send_message_passes_tools_to_api(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "ok"}
        }

        tools = [{"type": "function", "function": {"name": "my_tool"}}]

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            provider = OllamaProvider()
            await provider.send_message(prompt="use it", tools=tools, history=[])

        _, kwargs = mock_post.call_args
        assert kwargs["json"].get("tools") == tools


# ---------------------------------------------------------------------------
# 4. OllamaProvider — is_available
# ---------------------------------------------------------------------------


class TestOllamaProviderIsAvailable:
    @pytest.mark.asyncio
    async def test_is_available_returns_true_when_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            provider = OllamaProvider()
            result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_connection_error(self):
        import httpx

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            provider = OllamaProvider()
            result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_calls_correct_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            provider = OllamaProvider(base_url="http://localhost:11434")
            await provider.is_available()

        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:11434/api/tags"


# ---------------------------------------------------------------------------
# 5. OllamaProvider — supports_tools & misc
# ---------------------------------------------------------------------------


class TestOllamaProviderMisc:
    def test_supports_tools_returns_true(self):
        provider = OllamaProvider()
        assert provider.supports_tools() is True

    def test_name_is_ollama(self):
        provider = OllamaProvider()
        assert provider.name == "ollama"

    def test_default_model(self):
        provider = OllamaProvider()
        assert provider.model == "qwen2.5:7b"

    def test_custom_model(self):
        provider = OllamaProvider(model="llama3.2:3b")
        assert provider.model == "llama3.2:3b"

    def test_custom_base_url(self):
        provider = OllamaProvider(base_url="http://192.168.1.10:11434")
        assert provider.base_url == "http://192.168.1.10:11434"

    def test_is_subclass_of_base_provider(self):
        assert issubclass(OllamaProvider, BaseProvider)
