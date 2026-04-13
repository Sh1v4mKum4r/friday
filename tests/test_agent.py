"""Tests for friday_ai/agent.py — TDD.

Covers:
1. Simple chat (no tools) — mock router returns plain text
2. Tool call loop — mock router returns tool_call first, then plain text on second call.
   Verify tool_loader.execute was called with correct args.
3. Context dump contains expected sections
4. Bootstrap completion triggers delete_bootstrap
5. Max tool rounds exceeded returns partial result
6. save_session / load_session round-trip
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from friday_ai.agent import Agent, MAX_TOOL_ROUNDS
from friday_ai.providers.base import ProviderResponse, ToolCall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_router(responses: list[ProviderResponse]) -> MagicMock:
    """Create a mock ProviderRouter that returns *responses* in sequence."""
    router = MagicMock()
    router.route = AsyncMock(side_effect=responses)
    return router


def make_tool_loader(execute_return: str = "tool result") -> MagicMock:
    """Create a mock ToolLoader."""
    loader = MagicMock()
    loader.get_tools_description = MagicMock(return_value="- test_tool(): A test tool")
    loader.get_tool_schemas = MagicMock(return_value=[])
    loader.execute = MagicMock(return_value=execute_return)
    return loader


def setup_config_dir(config_dir: Path) -> None:
    """Write minimal SOUL.md and USER.md to *config_dir*."""
    (config_dir / "SOUL.md").write_text("You are Friday, a helpful assistant.")
    (config_dir / "USER.md").write_text("The user is a developer.")


# ---------------------------------------------------------------------------
# 1. Simple chat (no tools)
# ---------------------------------------------------------------------------


class TestSimpleChat:
    @pytest.mark.asyncio
    async def test_simple_chat_returns_provider_response(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                plain_response = ProviderResponse(
                    content="Hello! How can I help you?",
                    provider_name="mock",
                )
                router = make_router([plain_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                result = await agent.chat("Hello Friday")

                assert isinstance(result, ProviderResponse)
                assert result.content == "Hello! How can I help you?"

    @pytest.mark.asyncio
    async def test_simple_chat_appends_to_history(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                plain_response = ProviderResponse(
                    content="Sure, I can help!",
                    provider_name="mock",
                )
                router = make_router([plain_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Help me with something")

                # history should contain the user message and assistant response
                roles = [m["role"] for m in agent.history]
                assert "user" in roles
                assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_simple_chat_calls_router_once(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                plain_response = ProviderResponse(
                    content="Done.",
                    provider_name="mock",
                )
                router = make_router([plain_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("What is 2+2?")

                router.route.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_passes_system_prompt_to_router(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                plain_response = ProviderResponse(content="OK", provider_name="mock")
                router = make_router([plain_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Tell me something")

                _, kwargs = router.route.call_args
                system_prompt = kwargs.get("system_prompt", "")
                # The system prompt must reference the soul content
                assert "Friday" in system_prompt

    @pytest.mark.asyncio
    async def test_chat_passes_force_provider(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                plain_response = ProviderResponse(content="OK", provider_name="claude")
                router = make_router([plain_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Hello", force_provider="claude")

                _, kwargs = router.route.call_args
                assert kwargs.get("force_provider") == "claude"

    @pytest.mark.asyncio
    async def test_chat_user_message_content_in_history(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                plain_response = ProviderResponse(content="Pong!", provider_name="mock")
                router = make_router([plain_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Ping!")

                user_msgs = [m for m in agent.history if m["role"] == "user"]
                assert any("Ping!" in m["content"] for m in user_msgs)


# ---------------------------------------------------------------------------
# 2. Tool call loop
# ---------------------------------------------------------------------------


class TestToolCallLoop:
    @pytest.mark.asyncio
    async def test_tool_call_executes_tool(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                tool_response = ProviderResponse(
                    content="",
                    tool_calls=[ToolCall(name="say_hello", arguments={"target": "Friday"})],
                    provider_name="mock",
                )
                final_response = ProviderResponse(
                    content="I greeted Friday.",
                    provider_name="mock",
                )
                router = make_router([tool_response, final_response])
                tool_loader = make_tool_loader(execute_return="Hello, Friday!")

                agent = Agent(router, tool_loader, config_dir, data_dir)
                result = await agent.chat("Greet Friday")

                tool_loader.execute.assert_called_once_with("say_hello", {"target": "Friday"})

    @pytest.mark.asyncio
    async def test_tool_call_returns_final_text_response(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                tool_response = ProviderResponse(
                    content="",
                    tool_calls=[ToolCall(name="add_numbers", arguments={"a": 1, "b": 2})],
                    provider_name="mock",
                )
                final_response = ProviderResponse(
                    content="The result is 3.",
                    provider_name="mock",
                )
                router = make_router([tool_response, final_response])
                tool_loader = make_tool_loader(execute_return="3")

                agent = Agent(router, tool_loader, config_dir, data_dir)
                result = await agent.chat("What is 1 + 2?")

                assert result.content == "The result is 3."

    @pytest.mark.asyncio
    async def test_tool_call_router_called_twice(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                tool_response = ProviderResponse(
                    content="",
                    tool_calls=[ToolCall(name="search", arguments={"query": "AI"})],
                    provider_name="mock",
                )
                final_response = ProviderResponse(
                    content="Here is what I found.",
                    provider_name="mock",
                )
                router = make_router([tool_response, final_response])
                tool_loader = make_tool_loader(execute_return="search results")

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Search for AI news")

                assert router.route.await_count == 2

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_executed_in_order(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                tool_response = ProviderResponse(
                    content="",
                    tool_calls=[
                        ToolCall(name="tool_a", arguments={"x": "1"}),
                        ToolCall(name="tool_b", arguments={"y": "2"}),
                    ],
                    provider_name="mock",
                )
                final_response = ProviderResponse(
                    content="Done with both tools.",
                    provider_name="mock",
                )
                router = make_router([tool_response, final_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Run both tools")

                assert tool_loader.execute.call_count == 2
                calls = tool_loader.execute.call_args_list
                assert calls[0][0] == ("tool_a", {"x": "1"})
                assert calls[1][0] == ("tool_b", {"y": "2"})

    @pytest.mark.asyncio
    async def test_tool_result_included_in_follow_up(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                tool_response = ProviderResponse(
                    content="",
                    tool_calls=[ToolCall(name="get_time", arguments={})],
                    provider_name="mock",
                )
                final_response = ProviderResponse(
                    content="The time is 3:00 PM.",
                    provider_name="mock",
                )
                router = make_router([tool_response, final_response])
                tool_loader = make_tool_loader(execute_return="15:00:00")

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("What time is it?")

                # Second call should include the tool result in the prompt
                second_call_args = router.route.call_args_list[1]
                prompt_arg = second_call_args[1].get("prompt", second_call_args[0][0] if second_call_args[0] else "")
                assert "15:00:00" in prompt_arg or "get_time" in prompt_arg


# ---------------------------------------------------------------------------
# 3. Max tool rounds exceeded
# ---------------------------------------------------------------------------


class TestMaxToolRounds:
    @pytest.mark.asyncio
    async def test_max_tool_rounds_constant_is_five(self):
        assert MAX_TOOL_ROUNDS == 5

    @pytest.mark.asyncio
    async def test_max_rounds_exceeded_returns_last_partial_result(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                # Always return a tool call — never terminates naturally
                tool_call = ToolCall(name="infinite_tool", arguments={})
                tool_response = ProviderResponse(
                    content="still calling tools",
                    tool_calls=[tool_call],
                    provider_name="mock",
                )
                # Provide enough responses for MAX_TOOL_ROUNDS calls
                responses = [tool_response] * (MAX_TOOL_ROUNDS + 1)
                router = make_router(responses)
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                result = await agent.chat("Keep calling tools forever")

                # Must return something (not raise), and router should not be
                # called more than MAX_TOOL_ROUNDS times
                assert isinstance(result, ProviderResponse)
                assert router.route.await_count <= MAX_TOOL_ROUNDS


# ---------------------------------------------------------------------------
# 4. Bootstrap completion
# ---------------------------------------------------------------------------


class TestBootstrapCompletion:
    @pytest.mark.asyncio
    async def test_bootstrap_deleted_when_completion_phrase_in_response(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)
                # Write BOOTSTRAP.md so identity.bootstrap is non-None
                (config_dir / "BOOTSTRAP.md").write_text("First run instructions.")

                response = ProviderResponse(
                    content="Setup complete! Bootstrap is complete.",
                    provider_name="mock",
                )
                router = make_router([response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Start setup")

                # BOOTSTRAP.md must be deleted after the phrase is detected
                assert not (config_dir / "BOOTSTRAP.md").exists()

    @pytest.mark.asyncio
    async def test_bootstrap_not_deleted_without_completion_phrase(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)
                (config_dir / "BOOTSTRAP.md").write_text("First run instructions.")

                response = ProviderResponse(
                    content="I'm still learning about you.",
                    provider_name="mock",
                )
                router = make_router([response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Tell me about yourself")

                assert (config_dir / "BOOTSTRAP.md").exists()


# ---------------------------------------------------------------------------
# 5. Context dump
# ---------------------------------------------------------------------------


class TestContextDump:
    @pytest.mark.asyncio
    async def test_context_dump_returns_string(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                dump = agent.get_context_dump()

                assert isinstance(dump, str)

    @pytest.mark.asyncio
    async def test_context_dump_contains_system_prompt_section(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                dump = agent.get_context_dump()

                assert "system" in dump.lower() or "prompt" in dump.lower()

    @pytest.mark.asyncio
    async def test_context_dump_contains_history_section(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                dump = agent.get_context_dump()

                assert "history" in dump.lower()

    @pytest.mark.asyncio
    async def test_context_dump_includes_recent_messages(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                plain_response = ProviderResponse(content="I can help!", provider_name="mock")
                router = make_router([plain_response])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                await agent.chat("Do something unique XYZ123")

                dump = agent.get_context_dump()
                assert "XYZ123" in dump

    @pytest.mark.asyncio
    async def test_context_dump_limits_history_to_last_10(self):
        """get_context_dump shows at most the last 10 history messages."""
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                # Manually inject 15 messages into history
                for i in range(15):
                    agent.history.append({"role": "user", "content": f"Message {i}"})

                dump = agent.get_context_dump()
                # Only the last 10 should appear
                assert "Message 14" in dump
                assert "Message 4" not in dump  # the 5th from beginning, not in last 10

    @pytest.mark.asyncio
    async def test_context_dump_system_prompt_truncated_at_2000_chars(self):
        """System prompt section shows at most 2000 characters."""
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                # Write a very long SOUL.md
                (config_dir / "SOUL.md").write_text("X" * 5000)
                (config_dir / "USER.md").write_text("")

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                dump = agent.get_context_dump()

                # Should not contain 5000 Xs
                assert "X" * 2001 not in dump


# ---------------------------------------------------------------------------
# 6. Session persistence
# ---------------------------------------------------------------------------


class TestSessionPersistence:
    @pytest.mark.asyncio
    async def test_save_session_writes_file(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                agent.history = [{"role": "user", "content": "Hello"}]
                agent.save_session()

                session_files = list((data_dir / "history").glob("session-*.json"))
                assert len(session_files) == 1

    @pytest.mark.asyncio
    async def test_load_session_restores_history(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                agent.history = [{"role": "user", "content": "Saved message"}]
                agent.save_session()

                # New agent instance, loads the session
                agent2 = Agent(router, tool_loader, config_dir, data_dir)
                success = agent2.load_session()

                assert success is True
                assert any(
                    m["content"] == "Saved message" for m in agent2.history
                )

    @pytest.mark.asyncio
    async def test_load_session_returns_false_when_no_session(self):
        with tempfile.TemporaryDirectory() as config_tmp:
            with tempfile.TemporaryDirectory() as data_tmp:
                config_dir = Path(config_tmp)
                data_dir = Path(data_tmp)
                setup_config_dir(config_dir)

                router = make_router([])
                tool_loader = make_tool_loader()

                agent = Agent(router, tool_loader, config_dir, data_dir)
                result = agent.load_session()

                assert result is False
