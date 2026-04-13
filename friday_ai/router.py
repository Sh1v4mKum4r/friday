"""Provider Router for Friday AI.

Selects which provider to use based on a fallback chain:
  Ollama → API providers → CLI fallbacks → web search

Auto-escalation pushes complex tasks to cloud providers by skipping the
local "ollama" provider when the prompt is detected as complex.
"""
from __future__ import annotations

import re

from friday_ai.providers.base import BaseProvider, ProviderResponse

# ---------------------------------------------------------------------------
# Complexity / routing heuristics — compiled at module level for performance
# ---------------------------------------------------------------------------

_SIMPLE_KEYWORDS: re.Pattern = re.compile(
    r"\b("
    r"clipboard|copy|paste|notify|brightness|volume|window|workspace"
    r"|move|close|open app|screenshot|what time"
    r")\b",
    re.IGNORECASE,
)

_COMPLEX_KEYWORDS: re.Pattern = re.compile(
    r"\b("
    r"write|implement|create|build|refactor|debug|explain|analyze"
    r"|compare|summarize|translate|generate|design"
    r")\b",
    re.IGNORECASE,
)

_SEARCH_KEYWORDS: re.Pattern = re.compile(
    r"\b("
    r"latest|current|today|news|weather|price|stock|score|release|update"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public heuristic functions
# ---------------------------------------------------------------------------


def should_escalate(prompt: str) -> bool:
    """Return True if the prompt should be escalated to a cloud provider.

    Escalation is triggered when:
    - The prompt exceeds 200 characters, OR
    - The prompt contains complex keywords AND does not contain simple keywords
      (simple keywords override complex ones — the task is likely a desktop action).
    """
    if len(prompt) > 200:
        return True

    if _COMPLEX_KEYWORDS.search(prompt):
        # Simple keywords take precedence; if found, it's a desktop action
        if not _SIMPLE_KEYWORDS.search(prompt):
            return True

    return False


def needs_web_search(prompt: str) -> bool:
    """Return True if the prompt requires a live web search."""
    return bool(_SEARCH_KEYWORDS.search(prompt))


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
    ) -> None:
        self.providers = providers
        self.auto_escalate = auto_escalate

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
                return await provider.send_message(
                    prompt=prompt,
                    tools=tools,
                    history=history,
                    system_prompt=system_prompt,
                )

        # ------------------------------------------------------------------ #
        # All providers failed                                                 #
        # ------------------------------------------------------------------ #
        return ProviderResponse(
            content="Error: no providers are currently available.",
            provider_name="",
        )

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
