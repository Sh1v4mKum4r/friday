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
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            assert pilot.app._friday_theme == "obsidian"

    @pytest.mark.asyncio
    async def test_cycle_theme(self):
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "neural"
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "prism"
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "techno"
            pilot.app.action_cycle_theme()
            assert pilot.app._friday_theme == "obsidian"
