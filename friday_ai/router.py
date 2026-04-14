"""Provider Router for Friday AI.

Selects which provider to use based on a fallback chain:
  Ollama → API providers → CLI fallbacks → web search

Auto-escalation pushes complex tasks to cloud providers by skipping the
local "ollama" provider when the prompt is detected as complex.
"""
from __future__ import annotations

import asyncio
import re

from friday_ai.providers.base import BaseProvider, ProviderResponse

# ---------------------------------------------------------------------------
# Intent classification — compiled regex at module level for performance
# ---------------------------------------------------------------------------

# --- System / desktop actions — handle locally (Ollama) ---
_SYSTEM_KEYWORDS: re.Pattern = re.compile(
    r"\b("
    # Clipboard & copy
    r"clipboard|copy|paste|yank"
    # Notifications
    r"|notify|notification|alert|remind me"
    # Display & brightness
    r"|brightness|bright|dim|backlight|screen light"
    # Volume & audio
    r"|volume|mute|unmute|louder|quieter|sound|audio|speaker"
    # Media playback
    r"|play|pause|next track|previous track|skip|song|music|media"
    # Window & workspace management
    r"|window|workspace|focus|tile|float|fullscreen|minimize|maximize|split"
    r"|move window|close window|snap|resize"
    # Desktop environment
    r"|launch|open app|kill app|taskbar|panel|wallpaper|theme|dark mode|light mode"
    # Screenshot & screen
    r"|screenshot|screen ?shot|screen ?cap|record screen|screencast|screen read|ocr"
    # Mouse & keyboard
    r"|mouse|click|right.?click|double.?click|drag|scroll|cursor"
    r"|type|press key|key ?combo|hotkey|shortcut"
    # Quick system queries
    r"|what time|uptime|battery|cpu temp|ram usage|disk space|ip address"
    # File ops (simple)
    r"|read file|write file|cat |ls |list files|show file"
    # Cron & scheduling
    r"|cron|schedule|every hour|every day|every morning|every night"
    # System management
    r"|shutdown|reboot|restart|suspend|hibernate|lock screen|log ?out"
    r"|wifi|bluetooth|vpn|proxy|network|connect|disconnect"
    # Package management
    r"|install|uninstall|update system|pacman|yay|upgrade"
    r")\b",
    re.IGNORECASE,
)

# --- Complex tasks — escalate to cloud provider ---
_COMPLEX_KEYWORDS: re.Pattern = re.compile(
    r"\b("
    # Code generation & development (standalone verbs that imply complex work)
    r"implement|refactor|debug|architect"
    r"|write (?:a |an |the )?(?:\w+ )*(?:script|program|function|class|module|code|test|api|app|service|server|client|tool|bot|daemon)"
    r"|write code"
    r"|fix (?:the |this |a )?(?:bug|error|issue)"
    r"|code review|pull request|git (?:rebase|cherry)"
    # Standalone creative verbs (when followed by a noun, implies complex task)
    r"|design \w+|create \w+|build \w+|generate \w+|develop \w+|make \w+"
    # Analysis & reasoning
    r"|explain (?:how|why|what)|analyze|evaluate|assess|critique"
    r"|compare \w+|pros (?:and )?cons"
    r"|trade.?offs?|architecture"
    # Writing & generation
    r"|write (?:a |an )?\w*(?:essay|article|report|documentation|readme|doc)"
    r"|summarize|summarise|tldr|tl;dr"
    # Translation
    r"|translate|convert (?:this |from |to )"
    # Math & data
    r"|solve|prove|derive|calculate"
    r"|data (?:analysis|science|model)|machine learning|train (?:a )?model"
    # Research
    r"|research|investigate|deep dive|comprehensive|thorough|detailed"
    r"|literature review|state of the art"
    r")\b",
    re.IGNORECASE,
)

# --- Web search — needs live/current information ---
_SEARCH_KEYWORDS: re.Pattern = re.compile(
    r"\b("
    # Temporal markers
    r"latest|current(?:ly)?|today|yesterday|this (?:week|month|year)"
    r"|recent(?:ly)?|right now|as of"
    # News & events
    r"|news|headline|happening|event|announcement|release(?:d)?"
    # Live data
    r"|weather|forecast|temperature outside"
    r"|price of|stock (?:price|market)|crypto|bitcoin|ethereum"
    r"|score|match|game result|standings|tournament"
    r"|exchange rate|currency"
    # Lookups
    r"|who is|when (?:is|was|did)|where is|how much (?:does|is)"
    r"|status of|track(?:ing)?|shipping|flight"
    # Trending
    r"|trending|popular|viral|top (?:\d+|ten|five)"
    r"|what(?:'s| is) new"
    r")\b",
    re.IGNORECASE,
)

# --- Dangerous commands — require confirmation ---
_DANGEROUS_KEYWORDS: re.Pattern = re.compile(
    r"\b("
    r"rm -rf|mkfs|dd if=|format (?:disk|drive|partition)"
    r"|drop (?:table|database)|truncate|delete (?:all|everything)"
    r"|chmod 777|chmod -R"
    r"|curl .* \| (?:sudo )?(?:bash|sh)"
    r"|wget .* \| (?:sudo )?(?:bash|sh)"
    r"|> /dev/sd|> /dev/nvme"
    r"|kill -9 -1|killall"
    r"|passwd|chown -R|sudo su"
    r"|systemctl (?:disable|mask) (?:sddm|NetworkManager|systemd)"
    r"|pacman -Rns (?:linux|base|systemd|glibc)"
    r")\b",
    re.IGNORECASE,
)

# --- Conversational / simple — no tools needed, Ollama handles fine ---
_CONVERSATIONAL: re.Pattern = re.compile(
    r"^("
    r"(?:hi|hello|hey|yo|sup|good (?:morning|afternoon|evening|night))"
    r"|(?:thanks?|thank you|thx|cheers)"
    r"|(?:bye|goodbye|see you|later|good ?night)"
    r"|(?:how are you|what(?:'s| is) up|how(?:'s| is) it going)"
    r"|(?:who are you|what(?:'s| is) your name|what can you do)"
    r"|(?:yes|no|ok|okay|sure|nah|nope|yep|yeah)"
    r"|(?:lol|haha|lmao|nice|cool|awesome|great)"
    r")[\s?!.]*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public heuristic functions
# ---------------------------------------------------------------------------


def classify_intent(prompt: str) -> str:
    """Classify a prompt into an intent category.

    Returns one of: 'system', 'complex', 'search', 'dangerous', 'chat', 'unknown'

    Priority: dangerous > chat > search > complex > system > unknown.
    Complex is checked before system because multi-word complex patterns
    (e.g. "write a script") are more specific than single system keywords.
    """
    if _DANGEROUS_KEYWORDS.search(prompt):
        return "dangerous"
    if _CONVERSATIONAL.match(prompt):
        return "chat"
    # Check system BEFORE search — "next track" is system, not search
    # Check complex BEFORE system — "write a script" is complex, not system
    if _COMPLEX_KEYWORDS.search(prompt):
        return "complex"
    if _SYSTEM_KEYWORDS.search(prompt):
        return "system"
    if needs_web_search(prompt):
        return "search"
    if len(prompt) > 200:
        return "complex"
    return "unknown"


def should_escalate(prompt: str) -> bool:
    """Return True if the prompt should be escalated to a cloud provider.

    System keywords override complex — if a prompt mentions both window
    management and code writing, it's treated as a system/desktop action.
    """
    if _DANGEROUS_KEYWORDS.search(prompt):
        return False  # dangerous prompts are blocked, not escalated
    if _SYSTEM_KEYWORDS.search(prompt):
        return False  # system keywords take priority — keep local
    if _COMPLEX_KEYWORDS.search(prompt):
        return True
    if len(prompt) > 200:
        return True
    return False


def needs_web_search(prompt: str) -> bool:
    """Return True if the prompt requires a live web search."""
    return bool(_SEARCH_KEYWORDS.search(prompt))


def is_dangerous(prompt: str) -> bool:
    """Return True if the prompt contains potentially destructive commands."""
    return bool(_DANGEROUS_KEYWORDS.search(prompt))


# ---------------------------------------------------------------------------
# ProviderRouter
# ---------------------------------------------------------------------------


class ProviderRouter:
    """Routes prompts to the appropriate provider based on availability and
    complexity heuristics.

    Parameters
    ----------
    providers:
        Ordered list of providers representing the fallback chain.
        The first provider in the list is tried first (e.g. Ollama).
    auto_escalate:
        When True, complex prompts skip the "ollama" provider and prefer
        cloud providers first.  If no cloud provider is available the router
        falls back to Ollama anyway.
    """

    def __init__(
        self,
        providers: list[BaseProvider],
        auto_escalate: bool = True,
        provider_mode: str = "fallback",
    ) -> None:
        self.providers = providers
        self.auto_escalate = auto_escalate
        self.provider_mode = provider_mode

    async def route(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
        force_provider: str | None = None,
    ) -> ProviderResponse:
        """Select a provider and send the message.

        Parameters
        ----------
        prompt:
            The current user instruction.
        tools:
            Optional list of OpenAI-compatible tool schemas.
        history:
            Conversation history (not including the current prompt).
        system_prompt:
            Optional system instruction.
        force_provider:
            If given, use the provider with this exact name.  Returns an error
            response if the name is not found in the provider list.
        """
        # ------------------------------------------------------------------ #
        # force_provider path                                                  #
        # ------------------------------------------------------------------ #
        if force_provider is None and self.provider_mode == "race":
            intent = classify_intent(prompt)
            return await self.smart_race(
                prompt=prompt,
                tools=tools,
                history=history,
                system_prompt=system_prompt,
                intent=intent,
            )

        if force_provider is not None:
            target = self._find_by_name(force_provider)
            if target is None:
                return ProviderResponse(
                    content=f"Error: provider '{force_provider}' not found.",
                    provider_name="",
                )
            return await target.send_message(
                prompt=prompt,
                tools=tools,
                history=history,
                system_prompt=system_prompt,
            )

        # ------------------------------------------------------------------ #
        # Build the candidate list, optionally with escalation                #
        # ------------------------------------------------------------------ #
        candidates = self._build_candidate_list(prompt)

        # ------------------------------------------------------------------ #
        # Try each candidate in order                                          #
        # ------------------------------------------------------------------ #
        for provider in candidates:
            if await provider.is_available():
                try:
                    response = await provider.send_message(
                        prompt=prompt,
                        tools=tools,
                        history=history,
                        system_prompt=system_prompt,
                    )
                    # If provider returned an empty error, try next
                    if response.content or response.tool_calls:
                        return response
                except Exception:
                    continue  # Try next provider

        # ------------------------------------------------------------------ #
        # All providers failed                                                 #
        # ------------------------------------------------------------------ #
        return ProviderResponse(
            content="Error: no providers are currently available.",
            provider_name="",
        )

    async def race(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        """Fire all available providers simultaneously and return the fastest response.

        Parameters
        ----------
        prompt:
            The current user instruction.
        tools:
            Optional list of OpenAI-compatible tool schemas.
        history:
            Conversation history (not including the current prompt).
        system_prompt:
            Optional system instruction.
        """
        available = []
        for p in self.providers:
            if await p.is_available():
                available.append(p)

        if not available:
            return ProviderResponse(
                content="Error: no providers available.",
                provider_name="",
            )

        async def _call(provider: BaseProvider) -> ProviderResponse:
            response = await provider.send_message(
                prompt=prompt,
                tools=tools,
                history=history,
                system_prompt=system_prompt,
            )
            if not response.content and not response.tool_calls:
                raise ValueError("Empty response")
            return response

        all_tasks: set[asyncio.Task] = {
            asyncio.create_task(_call(p)) for p in available
        }

        remaining = set(all_tasks)

        while remaining:
            done, remaining = await asyncio.wait(
                remaining, return_when=asyncio.FIRST_COMPLETED
            )

            # Check completed tasks for a successful result
            for task in done:
                try:
                    winner = task.result()
                    # Cancel all still-pending tasks
                    for t in remaining:
                        t.cancel()
                    return winner
                except Exception:
                    continue
            # All tasks in this batch errored — keep waiting for the rest

        # Every task errored
        return ProviderResponse(
            content="Error: all providers failed during race.",
            provider_name="",
        )

    async def smart_race(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
        intent: str = "unknown",
    ) -> ProviderResponse:
        """Intent-aware racing — only race providers that make sense.

        - chat/system → Ollama only (local is fast enough)
        - complex → race cloud CLIs only (Claude vs Gemini)
        - search → web_search provider only
        - dangerous → block
        - unknown → fallback chain (no race)
        """
        if intent in ("chat", "system", "unknown"):
            # Use Ollama directly, no racing
            for p in self.providers:
                if p.name == "ollama" and await p.is_available():
                    try:
                        response = await p.send_message(prompt, tools, history, system_prompt)
                        if response.content or response.tool_calls:
                            return response
                    except Exception:
                        pass
            # Ollama failed, fall through to fallback
            return await self._fallback(prompt, tools, history, system_prompt)

        if intent == "complex":
            # Race only cloud providers (skip Ollama — too slow for complex)
            cloud = [p for p in self.providers if p.name != "ollama" and p.name != "web_search"]
            available_cloud = []
            for p in cloud:
                if await p.is_available():
                    available_cloud.append(p)

            if available_cloud:
                return await self._race_providers(available_cloud, prompt, tools, history, system_prompt)
            # No cloud available, fall back to Ollama
            return await self._fallback(prompt, tools, history, system_prompt)

        if intent == "search":
            ws = self._find_by_name("web_search")
            if ws and await ws.is_available():
                return await ws.send_message(prompt, tools, history, system_prompt)

        # Default: fallback chain
        return await self._fallback(prompt, tools, history, system_prompt)

    async def _race_providers(
        self,
        providers: list[BaseProvider],
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        """Race a specific set of providers."""
        async def _call(provider: BaseProvider) -> ProviderResponse:
            response = await provider.send_message(prompt, tools, history, system_prompt)
            if not response.content and not response.tool_calls:
                raise ValueError("Empty response")
            return response

        tasks = {asyncio.create_task(_call(p)) for p in providers}
        remaining = set(tasks)

        while remaining:
            done, remaining = await asyncio.wait(remaining, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    winner = task.result()
                    for t in remaining:
                        t.cancel()
                    return winner
                except Exception:
                    continue

        return ProviderResponse(content="Error: all cloud providers failed.", provider_name="")

    async def _fallback(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        """Standard fallback chain — try each provider in order."""
        for provider in self.providers:
            if await provider.is_available():
                try:
                    response = await provider.send_message(prompt, tools, history, system_prompt)
                    if response.content or response.tool_calls:
                        return response
                except Exception:
                    continue
        return ProviderResponse(content="Error: no providers available.", provider_name="")

    # ---------------------------------------------------------------------- #
    # Private helpers                                                          #
    # ---------------------------------------------------------------------- #

    def _find_by_name(self, name: str) -> BaseProvider | None:
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None

    def _build_candidate_list(self, prompt: str) -> list[BaseProvider]:
        """Return providers in the order they should be tried.

        When auto_escalate is True and the prompt should escalate:
        1. Non-Ollama providers first (preserving their relative order).
        2. Ollama appended at the end as a last-resort fallback.
        """
        if self.auto_escalate and should_escalate(prompt):
            non_ollama = [p for p in self.providers if p.name != "ollama"]
            ollama_providers = [p for p in self.providers if p.name == "ollama"]
            return non_ollama + ollama_providers

        return list(self.providers)
