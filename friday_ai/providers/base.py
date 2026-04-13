"""Abstract base provider interface for Friday AI.

All provider implementations must subclass BaseProvider and implement the
three abstract methods: send_message, is_available, and supports_tools.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """Represents a single tool call requested by the model."""

    name: str
    arguments: dict


@dataclass
class ProviderResponse:
    """Unified response returned by any provider."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider_name: str = ""


class BaseProvider(ABC):
    """Abstract base class that all providers must implement."""

    name: str = "base"

    @abstractmethod
    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        """Send a message and return a unified ProviderResponse.

        Parameters
        ----------
        prompt:
            The current user message / instruction.
        tools:
            List of OpenAI-compatible tool schemas, or None.
        history:
            Conversation history as a list of ``{"role": ..., "content": ...}``
            dicts (not including the current *prompt*).
        system_prompt:
            Optional system instruction prepended to the message list.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this provider is reachable and ready to serve requests."""

    @abstractmethod
    def supports_tools(self) -> bool:
        """Return True if this provider supports structured tool/function calling."""
