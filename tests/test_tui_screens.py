"""Tests for TUI screens."""

import pytest
from textual.app import App, ComposeResult
from textual.screen import Screen

from friday_ai.tui.screens.welcome import WelcomeScreen


class ScreenTestApp(App):
    SCREENS = {"welcome": WelcomeScreen}

    def on_mount(self) -> None:
        self.push_screen("welcome")

    def _get_dom_base(self):
        """Return the active screen so query_one searches the pushed screen."""
        return self.screen


class TestWelcomeScreen:
    @pytest.mark.asyncio
    async def test_renders(self):
        async with ScreenTestApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_has_logo(self):
        async with ScreenTestApp().run_test() as pilot:
            logo = pilot.app.query_one("#welcome-logo")
            assert logo is not None

    @pytest.mark.asyncio
    async def test_has_title(self):
        async with ScreenTestApp().run_test() as pilot:
            title = pilot.app.query_one("#welcome-title")
            assert title is not None

    @pytest.mark.asyncio
    async def test_has_quick_actions(self):
        async with ScreenTestApp().run_test() as pilot:
            actions = pilot.app.query(".quick-action")
            assert len(actions) == 6


from friday_ai.tui.screens.chat import ChatScreen


class ChatScreenTestApp(App):
    SCREENS = {"chat": ChatScreen}

    def on_mount(self) -> None:
        self.push_screen("chat")

    def _get_dom_base(self):
        """Return the active screen so query_one searches the pushed screen."""
        return self.screen


class TestChatScreen:
    @pytest.mark.asyncio
    async def test_renders(self):
        async with ChatScreenTestApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, ChatScreen)

    @pytest.mark.asyncio
    async def test_has_messages_area(self):
        async with ChatScreenTestApp().run_test() as pilot:
            messages = pilot.app.query_one("#messages")
            assert messages is not None

    @pytest.mark.asyncio
    async def test_has_input_bar(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.input_bar import InputBar
            bar = pilot.app.query_one(InputBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_has_mode_bar(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.mode_bar import ModeBar
            bar = pilot.app.query_one(ModeBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_sidebar_hidden_by_default(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.sidebar import Sidebar
            sidebar = pilot.app.query_one(Sidebar)
            assert sidebar.has_class("hidden")

    @pytest.mark.asyncio
    async def test_telemetry_hidden_by_default(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.telemetry import TelemetryPanel
            panel = pilot.app.query_one(TelemetryPanel)
            assert panel.has_class("hidden")

    @pytest.mark.asyncio
    async def test_add_message(self):
        async with ChatScreenTestApp().run_test() as pilot:
            screen = pilot.app.screen
            screen.add_message("Hello", role="user")
            from friday_ai.tui.widgets.message import MessageWidget
            messages = pilot.app.query(MessageWidget)
            assert len(messages) == 1


from friday_ai.tui.screens.settings import SettingsScreen
from friday_ai.tui.config import TUIConfig


class SettingsTestApp(App):
    SCREENS = {"settings": SettingsScreen}

    def on_mount(self) -> None:
        self.push_screen("settings")

    def _get_dom_base(self):
        """Return the active screen so query_one searches the pushed screen."""
        return self.screen


class TestSettingsScreen:
    @pytest.mark.asyncio
    async def test_renders(self):
        async with SettingsTestApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, SettingsScreen)

    @pytest.mark.asyncio
    async def test_simple_mode_by_default(self):
        async with SettingsTestApp().run_test() as pilot:
            screen = pilot.app.screen
            assert screen.settings_mode == "simple"

    @pytest.mark.asyncio
    async def test_toggle_to_advanced(self):
        async with SettingsTestApp().run_test() as pilot:
            screen = pilot.app.screen
            screen.toggle_advanced()
            assert screen.settings_mode == "advanced"
            screen.toggle_advanced()
            assert screen.settings_mode == "simple"

    @pytest.mark.asyncio
    async def test_has_settings_fields(self):
        async with SettingsTestApp().run_test() as pilot:
            fields = pilot.app.query(".settings-field")
            assert len(fields) > 0
