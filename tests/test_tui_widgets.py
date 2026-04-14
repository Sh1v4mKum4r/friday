"""Tests for TUI widgets."""

import pytest
from textual.app import App, ComposeResult

from friday_ai.tui.widgets.message import MessageWidget


class MessageTestApp(App):
    """Minimal app for testing widgets."""

    def __init__(self, widget):
        super().__init__()
        self._widget = widget

    def compose(self) -> ComposeResult:
        yield self._widget


class TestMessageWidget:
    @pytest.mark.asyncio
    async def test_user_message_renders(self):
        widget = MessageWidget(
            content="Hello Friday",
            role="user",
            timestamp="12:04",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            assert pilot.app.query_one(MessageWidget)
            assert widget.role == "user"
            assert widget.content == "Hello Friday"

    @pytest.mark.asyncio
    async def test_assistant_message_renders(self):
        widget = MessageWidget(
            content="Hello! How can I help?",
            role="assistant",
            provider="ollama",
            latency=0.84,
            timestamp="12:04",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.role == "assistant"
            assert msg.provider == "ollama"
            assert msg.latency == 0.84

    @pytest.mark.asyncio
    async def test_user_message_has_user_class(self):
        widget = MessageWidget(content="Hi", role="user", timestamp="12:00")
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.has_class("msg-user")

    @pytest.mark.asyncio
    async def test_assistant_message_has_assistant_class(self):
        widget = MessageWidget(
            content="Hi", role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.has_class("msg-assistant")

    @pytest.mark.asyncio
    async def test_message_with_code_block(self):
        content = "Here is code:\n```python\nprint('hello')\n```"
        widget = MessageWidget(
            content=content, role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.content == content

    @pytest.mark.asyncio
    async def test_append_token(self):
        widget = MessageWidget(
            content="", role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            msg.append_token("Hello")
            msg.append_token(" world")
            assert msg.content == "Hello world"


from friday_ai.tui.widgets.mode_bar import ModeBar
from friday_ai.tui.widgets.input_bar import InputBar


class TestModeBar:
    @pytest.mark.asyncio
    async def test_default_mode_is_chat(self):
        widget = ModeBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(ModeBar)
            assert bar.current_mode == "chat"

    @pytest.mark.asyncio
    async def test_cycle_mode(self):
        widget = ModeBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(ModeBar)
            bar.set_mode("command")
            assert bar.current_mode == "command"
            bar.set_mode("search")
            assert bar.current_mode == "search"
            bar.set_mode("chat")
            assert bar.current_mode == "chat"


class TestInputBar:
    @pytest.mark.asyncio
    async def test_renders(self):
        widget = InputBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(InputBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_placeholder_changes_with_mode(self):
        widget = InputBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(InputBar)
            bar.set_mode("chat")
            assert bar.placeholder == "Message Friday..."
            bar.set_mode("command")
            assert bar.placeholder == "! shell or /friday command..."
            bar.set_mode("search")
            assert bar.placeholder == "Search conversations..."

    @pytest.mark.asyncio
    async def test_thinking_state(self):
        widget = InputBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(InputBar)
            bar.set_thinking(True)
            assert bar.is_thinking is True
            bar.set_thinking(False)
            assert bar.is_thinking is False


from friday_ai.tui.widgets.sidebar import Sidebar


class TestSidebar:
    @pytest.mark.asyncio
    async def test_renders_empty(self):
        widget = Sidebar()
        async with MessageTestApp(widget).run_test() as pilot:
            sidebar = pilot.app.query_one(Sidebar)
            assert sidebar is not None

    @pytest.mark.asyncio
    async def test_load_sessions(self):
        sessions = [
            {"name": "React Optimize", "date": "2026-04-14", "id": "s1"},
            {"name": "MCP Fix", "date": "2026-04-13", "id": "s2"},
        ]
        widget = Sidebar()
        async with MessageTestApp(widget).run_test() as pilot:
            sidebar = pilot.app.query_one(Sidebar)
            sidebar.load_sessions(sessions)
            assert len(sidebar.sessions) == 2

    @pytest.mark.asyncio
    async def test_starts_hidden(self):
        widget = Sidebar(classes="hidden")
        async with MessageTestApp(widget).run_test() as pilot:
            sidebar = pilot.app.query_one(Sidebar)
            assert sidebar.has_class("hidden")


from friday_ai.tui.widgets.telemetry import TelemetryPanel


class TestTelemetryPanel:
    @pytest.mark.asyncio
    async def test_renders(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            assert panel is not None

    @pytest.mark.asyncio
    async def test_update_health(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            panel.update_health({
                "status": "online",
                "providers": ["ollama", "claude"],
            })
            assert panel.providers == ["ollama", "claude"]

    @pytest.mark.asyncio
    async def test_update_mcp(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            panel.update_mcp({
                "servers": ["dev", "files"],
                "tools": [
                    {"name": "git_status", "server": "dev"},
                    {"name": "find_files", "server": "files"},
                ],
            })
            assert len(panel.mcp_servers) == 2

    @pytest.mark.asyncio
    async def test_update_last_response(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            panel.update_last_response("ollama", "qwen2.5:7b", 0.84)
            assert panel.active_provider == "ollama"
            assert panel.active_model == "qwen2.5:7b"
            assert panel.last_latency == 0.84


from friday_ai.tui.widgets.code_block import CodeBlock


class TestCodeBlock:
    @pytest.mark.asyncio
    async def test_renders(self):
        widget = CodeBlock(code="print('hello')", language="python")
        async with MessageTestApp(widget).run_test() as pilot:
            block = pilot.app.query_one(CodeBlock)
            assert block.code == "print('hello')"
            assert block.language == "python"

    @pytest.mark.asyncio
    async def test_collapsed_when_long(self):
        long_code = "\n".join(f"line {i}" for i in range(60))
        widget = CodeBlock(code=long_code, language="python")
        async with MessageTestApp(widget).run_test() as pilot:
            block = pilot.app.query_one(CodeBlock)
            assert block.is_collapsed is True

    @pytest.mark.asyncio
    async def test_not_collapsed_when_short(self):
        widget = CodeBlock(code="x = 1", language="python")
        async with MessageTestApp(widget).run_test() as pilot:
            block = pilot.app.query_one(CodeBlock)
            assert block.is_collapsed is False
