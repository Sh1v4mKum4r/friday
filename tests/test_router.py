"""Tests for friday_ai/router.py — TDD.

Covers:
- Router selects first available provider (Ollama first)
- Router falls back when first provider is unavailable
- force_provider works correctly
- Auto-escalation skips Ollama for complex prompts
- should_escalate heuristic (length + complex keywords)
- needs_web_search heuristic
- All-providers-unavailable error path
- Race mode: returns fastest provider's response
- Race mode: handles individual provider errors gracefully
- Race mode: cancels slower providers
- Race mode: bypassed by force_provider
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from friday_ai.providers.base import ProviderResponse
from friday_ai.router import ProviderRouter, should_escalate, needs_web_search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_provider(name: str, available: bool = True) -> MagicMock:
    """Create a mock provider with the given name and availability."""
    provider = MagicMock()
    provider.name = name
    provider.is_available = AsyncMock(return_value=available)
    provider.send_message = AsyncMock(
        return_value=ProviderResponse(content=f"response from {name}", provider_name=name)
    )
    provider.supports_tools = MagicMock(return_value=True)
    return provider


# ---------------------------------------------------------------------------
# 1. should_escalate heuristic
# ---------------------------------------------------------------------------


class TestShouldEscalate:
    def test_short_simple_prompt_does_not_escalate(self):
        assert should_escalate("what time is it") is False

    def test_prompt_over_200_chars_escalates(self):
        long_prompt = "a" * 201
        assert should_escalate(long_prompt) is True

    def test_prompt_exactly_200_chars_does_not_escalate(self):
        prompt = "a" * 200
        # 200 chars with no complex keywords — no escalation
        assert should_escalate(prompt) is False

    def test_complex_keyword_write_escalates(self):
        assert should_escalate("write a Python script to parse JSON") is True

    def test_complex_keyword_implement_escalates(self):
        assert should_escalate("implement a binary search tree") is True

    def test_complex_keyword_explain_escalates(self):
        assert should_escalate("explain how transformers work") is True

    def test_complex_keyword_analyze_escalates(self):
        assert should_escalate("analyze this code for bugs") is True

    def test_complex_keyword_debug_escalates(self):
        assert should_escalate("debug this function") is True

    def test_complex_keyword_refactor_escalates(self):
        assert should_escalate("refactor my login module") is True

    def test_complex_keyword_summarize_escalates(self):
        assert should_escalate("summarize this article") is True

    def test_complex_keyword_translate_escalates(self):
        assert should_escalate("translate this paragraph to French") is True

    def test_complex_keyword_generate_escalates(self):
        assert should_escalate("generate a unit test suite") is True

    def test_complex_keyword_compare_escalates(self):
        assert should_escalate("compare React and Vue") is True

    def test_complex_keyword_design_escalates(self):
        assert should_escalate("design a REST API for a blog") is True

    def test_complex_keyword_create_escalates(self):
        assert should_escalate("create a database schema") is True

    def test_complex_keyword_build_escalates(self):
        assert should_escalate("build a CLI tool") is True

    def test_simple_keyword_overrides_complex(self):
        # "open app" is simple; even if "create" is present, simple wins
        assert should_escalate("open app and create a shortcut") is False

    def test_simple_keyword_copy_does_not_escalate(self):
        assert should_escalate("copy this text to clipboard") is False

    def test_simple_keyword_volume_does_not_escalate(self):
        assert should_escalate("volume up") is False

    def test_simple_keyword_screenshot_does_not_escalate(self):
        assert should_escalate("take a screenshot") is False

    def test_simple_keyword_brightness_does_not_escalate(self):
        assert should_escalate("brightness 50") is False

    def test_case_insensitive_complex_keyword(self):
        assert should_escalate("WRITE a function") is True

    def test_case_insensitive_simple_keyword(self):
        assert should_escalate("CLIPBOARD copy") is False


# ---------------------------------------------------------------------------
# 2. needs_web_search heuristic
# ---------------------------------------------------------------------------


class TestNeedsWebSearch:
    def test_latest_triggers_search(self):
        assert needs_web_search("latest news about AI") is True

    def test_current_triggers_search(self):
        assert needs_web_search("current weather in London") is True

    def test_today_triggers_search(self):
        assert needs_web_search("what happened today") is True

    def test_news_triggers_search(self):
        assert needs_web_search("tech news headlines") is True

    def test_weather_triggers_search(self):
        assert needs_web_search("weather forecast for tomorrow") is True

    def test_price_triggers_search(self):
        assert needs_web_search("price of Bitcoin") is True

    def test_stock_triggers_search(self):
        assert needs_web_search("stock market update") is True

    def test_score_triggers_search(self):
        assert needs_web_search("match score of last night's game") is True

    def test_release_triggers_search(self):
        assert needs_web_search("Python 3.14 release date") is True

    def test_update_triggers_search(self):
        assert needs_web_search("latest update for Ubuntu") is True

    def test_plain_prompt_no_search(self):
        assert needs_web_search("write a sorting function") is False

    def test_case_insensitive_search_keyword(self):
        assert needs_web_search("LATEST AI developments") is True


# ---------------------------------------------------------------------------
# 3. Router: uses first available provider (Ollama first)
# ---------------------------------------------------------------------------


class TestRouterFirstAvailable:
    @pytest.mark.asyncio
    async def test_uses_first_available_provider(self):
        ollama = make_provider("ollama", available=True)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[ollama, cloud], auto_escalate=False)

        result = await router.route(
            prompt="what time is it",
            tools=None,
            history=[],
        )

        ollama.send_message.assert_awaited_once()
        cloud.send_message.assert_not_awaited()
        assert result.provider_name == "ollama"

    @pytest.mark.asyncio
    async def test_response_content_comes_from_selected_provider(self):
        ollama = make_provider("ollama", available=True)
        router = ProviderRouter(providers=[ollama], auto_escalate=False)

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.content == "response from ollama"

    @pytest.mark.asyncio
    async def test_provider_name_set_in_response(self):
        ollama = make_provider("ollama", available=True)
        router = ProviderRouter(providers=[ollama], auto_escalate=False)

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.provider_name == "ollama"


# ---------------------------------------------------------------------------
# 4. Router: fallback when first provider unavailable
# ---------------------------------------------------------------------------


class TestRouterFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_second_provider_when_first_unavailable(self):
        ollama = make_provider("ollama", available=False)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[ollama, cloud], auto_escalate=False)

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        ollama.send_message.assert_not_awaited()
        cloud.send_message.assert_awaited_once()
        assert result.provider_name == "claude"

    @pytest.mark.asyncio
    async def test_skips_multiple_unavailable_providers(self):
        p1 = make_provider("p1", available=False)
        p2 = make_provider("p2", available=False)
        p3 = make_provider("p3", available=True)
        router = ProviderRouter(providers=[p1, p2, p3], auto_escalate=False)

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.provider_name == "p3"

    @pytest.mark.asyncio
    async def test_returns_error_response_when_all_providers_unavailable(self):
        p1 = make_provider("p1", available=False)
        p2 = make_provider("p2", available=False)
        router = ProviderRouter(providers=[p1, p2], auto_escalate=False)

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.provider_name == ""
        assert "error" in result.content.lower() or "unavailable" in result.content.lower()

    @pytest.mark.asyncio
    async def test_returns_error_response_when_no_providers(self):
        router = ProviderRouter(providers=[], auto_escalate=False)

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.provider_name == ""


# ---------------------------------------------------------------------------
# 5. Router: force_provider
# ---------------------------------------------------------------------------


class TestRouterForceProvider:
    @pytest.mark.asyncio
    async def test_force_provider_uses_named_provider(self):
        ollama = make_provider("ollama", available=True)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[ollama, cloud], auto_escalate=False)

        result = await router.route(
            prompt="hi",
            tools=None,
            history=[],
            force_provider="claude",
        )

        ollama.send_message.assert_not_awaited()
        cloud.send_message.assert_awaited_once()
        assert result.provider_name == "claude"

    @pytest.mark.asyncio
    async def test_force_provider_returns_error_when_name_not_found(self):
        ollama = make_provider("ollama", available=True)
        router = ProviderRouter(providers=[ollama], auto_escalate=False)

        result = await router.route(
            prompt="hi",
            tools=None,
            history=[],
            force_provider="nonexistent",
        )

        ollama.send_message.assert_not_awaited()
        assert result.provider_name == ""
        assert "error" in result.content.lower() or "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_force_provider_uses_provider_even_if_unavailable(self):
        """force_provider should bypass availability check and try anyway."""
        ollama = make_provider("ollama", available=False)
        router = ProviderRouter(providers=[ollama], auto_escalate=False)

        result = await router.route(
            prompt="hi",
            tools=None,
            history=[],
            force_provider="ollama",
        )

        ollama.send_message.assert_awaited_once()
        assert result.provider_name == "ollama"


# ---------------------------------------------------------------------------
# 6. Router: auto-escalation skips Ollama for complex prompts
# ---------------------------------------------------------------------------


class TestRouterAutoEscalation:
    @pytest.mark.asyncio
    async def test_complex_prompt_skips_ollama_with_auto_escalate(self):
        ollama = make_provider("ollama", available=True)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[ollama, cloud], auto_escalate=True)

        result = await router.route(
            prompt="write a complete REST API with authentication and tests",
            tools=None,
            history=[],
        )

        ollama.send_message.assert_not_awaited()
        cloud.send_message.assert_awaited_once()
        assert result.provider_name == "claude"

    @pytest.mark.asyncio
    async def test_simple_prompt_uses_ollama_with_auto_escalate(self):
        ollama = make_provider("ollama", available=True)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[ollama, cloud], auto_escalate=True)

        result = await router.route(
            prompt="what time is it",
            tools=None,
            history=[],
        )

        ollama.send_message.assert_awaited_once()
        cloud.send_message.assert_not_awaited()
        assert result.provider_name == "ollama"

    @pytest.mark.asyncio
    async def test_escalation_skips_ollama_but_falls_through_to_it_if_only_option(self):
        """If only Ollama is available, escalation still falls back to it."""
        ollama = make_provider("ollama", available=True)
        router = ProviderRouter(providers=[ollama], auto_escalate=True)

        result = await router.route(
            prompt="implement a neural network from scratch",
            tools=None,
            history=[],
        )

        # Ollama is the only option, so it must be used
        ollama.send_message.assert_awaited_once()
        assert result.provider_name == "ollama"

    @pytest.mark.asyncio
    async def test_auto_escalate_false_does_not_skip_ollama_for_complex(self):
        ollama = make_provider("ollama", available=True)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[ollama, cloud], auto_escalate=False)

        result = await router.route(
            prompt="implement a full microservices architecture",
            tools=None,
            history=[],
        )

        ollama.send_message.assert_awaited_once()
        cloud.send_message.assert_not_awaited()
        assert result.provider_name == "ollama"

    @pytest.mark.asyncio
    async def test_long_prompt_triggers_escalation(self):
        ollama = make_provider("ollama", available=True)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[ollama, cloud], auto_escalate=True)

        long_prompt = "please help me " + "with this task " * 20  # > 200 chars

        result = await router.route(
            prompt=long_prompt,
            tools=None,
            history=[],
        )

        ollama.send_message.assert_not_awaited()
        assert result.provider_name == "claude"

    @pytest.mark.asyncio
    async def test_escalation_skips_only_ollama_not_other_providers(self):
        """Only 'ollama' named provider is skipped during escalation."""
        gemini = make_provider("gemini", available=True)
        cloud = make_provider("claude", available=True)
        router = ProviderRouter(providers=[gemini, cloud], auto_escalate=True)

        result = await router.route(
            prompt="implement a complete REST API",
            tools=None,
            history=[],
        )

        # gemini is not named "ollama", so it should be used first
        gemini.send_message.assert_awaited_once()
        cloud.send_message.assert_not_awaited()
        assert result.provider_name == "gemini"


# ---------------------------------------------------------------------------
# 7. Router: system_prompt passthrough
# ---------------------------------------------------------------------------


class TestRouterSystemPrompt:
    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_provider(self):
        ollama = make_provider("ollama", available=True)
        router = ProviderRouter(providers=[ollama], auto_escalate=False)

        await router.route(
            prompt="hi",
            tools=None,
            history=[],
            system_prompt="You are Friday.",
        )

        _, kwargs = ollama.send_message.call_args
        assert kwargs.get("system_prompt") == "You are Friday."

    @pytest.mark.asyncio
    async def test_default_system_prompt_is_empty_string(self):
        ollama = make_provider("ollama", available=True)
        router = ProviderRouter(providers=[ollama], auto_escalate=False)

        await router.route(prompt="hi", tools=None, history=[])

        _, kwargs = ollama.send_message.call_args
        assert kwargs.get("system_prompt", "") == ""


# ---------------------------------------------------------------------------
# 8. Router: race mode
# ---------------------------------------------------------------------------


def make_slow_provider(name: str, delay: float, available: bool = True) -> MagicMock:
    """Create a mock provider whose send_message takes *delay* seconds."""
    provider = MagicMock()
    provider.name = name
    provider.is_available = AsyncMock(return_value=available)

    async def _slow_send(*args, **kwargs):
        await asyncio.sleep(delay)
        return ProviderResponse(content=f"response from {name}", provider_name=name)

    provider.send_message = AsyncMock(side_effect=_slow_send)
    provider.supports_tools = MagicMock(return_value=True)
    return provider


class TestRaceMode:
    @pytest.mark.asyncio
    async def test_race_returns_fastest_provider_response(self):
        """The provider that responds first wins the race."""
        fast = make_slow_provider("fast", delay=0.01)
        slow = make_slow_provider("slow", delay=0.5)
        router = ProviderRouter(
            providers=[fast, slow], auto_escalate=False, provider_mode="race"
        )

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.provider_name == "fast"
        assert result.content == "response from fast"

    @pytest.mark.asyncio
    async def test_race_cancels_slower_providers(self):
        """After the fastest provider responds, pending tasks are cancelled."""
        fast = make_slow_provider("fast", delay=0.01)
        slow = make_slow_provider("slow", delay=10.0)
        router = ProviderRouter(
            providers=[fast, slow], auto_escalate=False, provider_mode="race"
        )

        # Should complete well before the 10-second slow provider
        result = await asyncio.wait_for(
            router.route(prompt="hi", tools=None, history=[]), timeout=2.0
        )

        assert result.provider_name == "fast"

    @pytest.mark.asyncio
    async def test_race_handles_provider_error_gracefully(self):
        """If the fastest provider raises an exception, the next winner is used."""
        error_provider = make_provider("error_provider", available=True)
        error_provider.send_message = AsyncMock(
            side_effect=RuntimeError("provider exploded")
        )
        good = make_slow_provider("good", delay=0.05)
        router = ProviderRouter(
            providers=[error_provider, good], auto_escalate=False, provider_mode="race"
        )

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        # The good provider should win since the error provider crashed
        assert result.provider_name == "good"
        assert result.content == "response from good"

    @pytest.mark.asyncio
    async def test_race_returns_error_when_all_providers_fail(self):
        """When every provider errors, race() returns an error ProviderResponse."""
        p1 = make_provider("p1", available=True)
        p1.send_message = AsyncMock(side_effect=RuntimeError("fail"))
        p2 = make_provider("p2", available=True)
        p2.send_message = AsyncMock(side_effect=RuntimeError("fail"))
        router = ProviderRouter(
            providers=[p1, p2], auto_escalate=False, provider_mode="race"
        )

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.provider_name == ""
        assert "error" in result.content.lower()

    @pytest.mark.asyncio
    async def test_race_no_available_providers_returns_error(self):
        """race() returns an error when no providers are available."""
        p1 = make_provider("p1", available=False)
        router = ProviderRouter(
            providers=[p1], auto_escalate=False, provider_mode="race"
        )

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        assert result.provider_name == ""
        assert "error" in result.content.lower()

    @pytest.mark.asyncio
    async def test_force_provider_bypasses_race_mode(self):
        """force_provider always uses the specific provider regardless of race mode."""
        fast = make_slow_provider("fast", delay=0.01)
        target = make_slow_provider("target", delay=0.5)
        router = ProviderRouter(
            providers=[fast, target], auto_escalate=False, provider_mode="race"
        )

        result = await router.route(
            prompt="hi", tools=None, history=[], force_provider="target"
        )

        # force_provider overrides race — must use "target"
        assert result.provider_name == "target"
        fast.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_race_mode_via_route_method(self):
        """route() dispatches to race() when provider_mode == 'race'."""
        p1 = make_provider("p1", available=True)
        p2 = make_provider("p2", available=True)
        router = ProviderRouter(
            providers=[p1, p2], auto_escalate=False, provider_mode="race"
        )

        result = await router.route(prompt="explain how quantum computing works in detail", tools=None, history=[])

        # Both providers should have been called (race fires all simultaneously)
        p1.send_message.assert_awaited_once()
        p2.send_message.assert_awaited_once()
        assert result.content != ""
