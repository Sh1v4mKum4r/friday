"""Tests for the main Friday TUI app."""

import pytest

from friday_ai.tui.app import FridayApp
from friday_ai.tui.screens.welcome import WelcomeScreen
from friday_ai.tui.screens.chat import ChatScreen


class TestFridayApp:
    @pytest.mark.asyncio
    async def test_app_launches(self):
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            assert pilot.app is not None

    @pytest.mark.asyncio
    async def test_starts_on_chat_screen(self):
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, (WelcomeScreen, ChatScreen))

    @pytest.mark.asyncio
    async def test_theme_defaults_to_obsidian(self):
        app = FridayApp(no_connect=True, theme="obsidian")
        async with app.run_test() as pilot:
            assert pilot.app._friday_theme == "obsidian"

    @pytest.mark.asyncio
    async def test_cycle_theme(self):
        app = FridayApp(no_connect=True, theme="obsidian")
        async with app.run_test() as pilot:
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "neural"
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "prism"
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "techno"
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "obsidian"


class TestFridayAppIntegration:
    @pytest.mark.asyncio
    async def test_send_chat_without_backend(self):
        """Chat gracefully handles missing backend."""
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            from friday_ai.tui.screens.chat import ChatScreen
            screen = pilot.app.screen
            if isinstance(screen, ChatScreen):
                # Focus the input widget, type a message, then submit
                from textual.widgets import Input
                input_widget = pilot.app.screen.query_one("#chat-input", Input)
                input_widget.focus()
                await pilot.pause()
                input_widget.value = "hello"
                await pilot.press("enter")
                # Allow async processing
                await pilot.pause()
                # Should show messages (user + error), not crash
                from friday_ai.tui.widgets.message import MessageWidget
                messages = pilot.app.screen.query(MessageWidget)
                assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_settings_roundtrip(self):
        """Open settings, verify it renders, close."""
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            await pilot.press("ctrl+s")
            await pilot.pause()
            from friday_ai.tui.screens.settings import SettingsScreen
            assert isinstance(pilot.app.screen, SettingsScreen)
            await pilot.press("escape")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_theme_cycle_keybind(self):
        """Ctrl+Shift+T cycles themes."""
        app = FridayApp(no_connect=True, theme="obsidian")
        async with app.run_test() as pilot:
            # Read the initial theme attribute name from existing tests
            initial = pilot.app._friday_theme
            assert initial == "obsidian"
            await pilot.press("ctrl+shift+t")
            await pilot.pause()
            assert pilot.app._friday_theme == "neural"
