"""Core Agent class for Friday AI.

Orchestrates identity, memory, tool-loading, and provider routing into a
single async chat loop with tool-call support (up to MAX_TOOL_ROUNDS rounds).
"""

from __future__ import annotations

import logging
from pathlib import Path

from .identity import build_system_prompt, delete_bootstrap, load_identity
from .memory import MemoryStore
from .providers.base import ProviderResponse
from .router import ProviderRouter
from .tool_loader import ToolLoader

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5


class Agent:
    """High-level orchestrator that combines identity, memory, tools, and a
    provider router into a conversational agent.

    Parameters
    ----------
    router:
        :class:`~friday_ai.router.ProviderRouter` used to send messages to the
        appropriate LLM backend.
    tool_loader:
        :class:`~friday_ai.tool_loader.ToolLoader` used to discover and execute
        plugin tools.
    config_dir:
        Directory containing identity files (SOUL.md, USER.md, etc.).
    data_dir:
        Directory used by :class:`~friday_ai.memory.MemoryStore` for logs and
        session persistence.
    """

    def __init__(
        self,
        router: ProviderRouter,
        tool_loader: ToolLoader,
        config_dir: Path,
        data_dir: Path,
    ) -> None:
        self.router = router
        self.tool_loader = tool_loader
        self.config_dir = config_dir
        self.memory = MemoryStore(data_dir)
        self.history: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        force_provider: str | None = None,
        race: bool = False,
    ) -> ProviderResponse:
        """Send *message* through the agent and return the final response.

        The method:
        1. Builds a system prompt from identity files, tool descriptions, and
           memory context.
        2. Adds the user message to history and the daily log.
        3. Runs the tool-call loop (up to :data:`MAX_TOOL_ROUNDS` iterations).
        4. Returns the first non-tool-call response, or the last partial
           response if the max rounds are exceeded.
        5. Handles bootstrap completion by deleting BOOTSTRAP.md.

        Parameters
        ----------
        message:
            The user's message.
        force_provider:
            Optional provider name to force; passed straight through to
            :meth:`~friday_ai.router.ProviderRouter.route`.
        race:
            When True, override the router's provider_mode to "race" for this
            request so all available providers are fired simultaneously.
        """
        # ------------------------------------------------------------------ #
        # Build system prompt                                                  #
        # ------------------------------------------------------------------ #
        identity = load_identity(self.config_dir)
        memory_context = self.memory.get_context_for_prompt()
        tools_desc = self.tool_loader.get_tools_description()
        system_prompt = build_system_prompt(identity, tools_desc, memory_context)

        # ------------------------------------------------------------------ #
        # Get tool schemas                                                      #
        # ------------------------------------------------------------------ #
        tool_schemas = self.tool_loader.get_tool_schemas()

        # ------------------------------------------------------------------ #
        # Add user message to history and daily log                            #
        # ------------------------------------------------------------------ #
        self.history.append({"role": "user", "content": message})
        self.memory.append_daily_log(f"[user] {message}")

        # ------------------------------------------------------------------ #
        # Tool-call loop                                                        #
        # ------------------------------------------------------------------ #
        current_prompt = message
        last_response: ProviderResponse | None = None

        # When race=True, temporarily override provider_mode for this request
        original_mode = self.router.provider_mode
        if race and force_provider is None:
            self.router.provider_mode = "race"

        try:
            for _round in range(MAX_TOOL_ROUNDS):
                response = await self.router.route(
                    prompt=current_prompt,
                    tools=tool_schemas or None,
                    history=self.history[:-1],  # exclude the last user message (it's the prompt)
                    system_prompt=system_prompt,
                    force_provider=force_provider,
                )
                last_response = response

                # No tool calls — this is the final answer
                if not response.tool_calls:
                    self.history.append({"role": "assistant", "content": response.content})
                    self.memory.append_daily_log(f"[assistant] {response.content}")

                    # Check bootstrap completion
                    if identity.bootstrap and "bootstrap is complete" in response.content.lower():
                        delete_bootstrap(self.config_dir)

                    return response

                # There are tool calls — execute each and build a follow-up prompt
                result_parts: list[str] = []
                for tool_call in response.tool_calls:
                    try:
                        result = self.tool_loader.execute(tool_call.name, tool_call.arguments)
                    except Exception as exc:  # noqa: BLE001
                        result = f"Error executing {tool_call.name}: {exc}"
                    result_parts.append(f"Tool '{tool_call.name}' returned: {result}")

                current_prompt = "\n".join(result_parts)

        finally:
            self.router.provider_mode = original_mode

        # ------------------------------------------------------------------ #
        # Max rounds exceeded — return the last partial response               #
        # ------------------------------------------------------------------ #
        if last_response is not None:
            return last_response

        return ProviderResponse(
            content="Error: max tool rounds exceeded with no response.",
            provider_name="",
        )

    def get_context_dump(self) -> str:
        """Return a formatted string showing the current system prompt and
        recent conversation history.

        The system prompt is truncated to the first 2 000 characters.
        Only the last 10 history messages are included.
        """
        identity = load_identity(self.config_dir)
        memory_context = self.memory.get_context_for_prompt()
        tools_desc = self.tool_loader.get_tools_description()
        system_prompt = build_system_prompt(identity, tools_desc, memory_context)

        truncated_prompt = system_prompt[:2000]
        recent_history = self.history[-10:]

        lines: list[str] = [
            "=== System Prompt (first 2000 chars) ===",
            truncated_prompt,
            "",
            "=== History (last 10 messages) ===",
        ]
        for msg in recent_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"[{role}] {content}")

        return "\n".join(lines)

    def save_session(self) -> None:
        """Persist the current conversation history to a timestamped JSON file."""
        self.memory.save_session(self.history)

    def load_session(self) -> bool:
        """Load the most recent saved session into :attr:`history`.

        Returns
        -------
        bool
            ``True`` if a session was found and loaded, ``False`` otherwise.
        """
        messages = self.memory.load_latest_session()
        if messages is None:
            return False
        self.history = messages
        return True
