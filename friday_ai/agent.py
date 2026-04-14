"""Core Agent class for Friday AI.

Orchestrates identity, memory, tool-loading, and provider routing into a
single async chat loop with tool-call support (up to MAX_TOOL_ROUNDS rounds).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncIterator

from .identity import build_system_prompt, delete_bootstrap, load_identity
from .mcp_client import MCPManager
from .memory import MemoryStore
from .providers.base import ProviderResponse
from .router import ProviderRouter, classify_intent, is_dangerous
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
        mcp_manager: MCPManager | None = None,
    ) -> None:
        self.router = router
        self.tool_loader = tool_loader
        self.config_dir = config_dir
        self.memory = MemoryStore(data_dir)
        self.mcp_manager = mcp_manager
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
        memory_context = self.memory.get_context_for_prompt(query=message)

        # Smart tool filtering — only send relevant tools to keep LLM fast
        intent = classify_intent(message)
        tool_schemas = self._filter_tools(intent, message)
        tools_desc = self._tools_desc_from_schemas(tool_schemas)

        # Select Ollama model based on intent (fast 3B for simple, heavy 7B for complex)
        self._select_ollama_model(intent)

        system_prompt = build_system_prompt(identity, tools_desc, memory_context)

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
                    # Safety check: block dangerous commands
                    args_str = " ".join(str(v) for v in tool_call.arguments.values())
                    if is_dangerous(args_str):
                        result = (
                            f"BLOCKED: '{args_str[:100]}' looks dangerous. "
                            "Friday refuses to run destructive commands without explicit confirmation. "
                            "Tell the user what you were about to do and ask if they want to proceed."
                        )
                    else:
                        try:
                            # Route to MCP or built-in tool
                            if self.mcp_manager and self.mcp_manager.is_mcp_tool(tool_call.name):
                                result = await self.mcp_manager.call_tool(tool_call.name, tool_call.arguments)
                            else:
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

    async def stream_chat(
        self,
        message: str,
        force_provider: str | None = None,
    ) -> AsyncIterator[dict]:
        """Stream chat tokens. Yields {"token": str, "done": bool, ...}."""
        import time

        start = time.monotonic()

        try:
            result = await self.chat(message, force_provider=force_provider)
            content = result.content
            provider_name = result.provider_name

            # Yield tokens (word-level chunks)
            words = content.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield {"token": token, "done": False}

            elapsed = time.monotonic() - start
            yield {"token": "", "done": True, "provider": provider_name, "latency": round(elapsed, 3)}
        except Exception as e:
            yield {"token": "", "done": True, "error": str(e), "provider": "error", "latency": 0}

    # ------------------------------------------------------------------
    # Smart model selection
    # ------------------------------------------------------------------

    def _select_ollama_model(self, intent: str) -> None:
        """Swap the Ollama provider's model based on intent.

        - chat/system/unknown → fast model (3B) — stays loaded, instant
        - complex → heavy model (7B) — loads on demand, better reasoning
        """
        # Find the Ollama provider in the router
        for provider in self.router.providers:
            if provider.name == "ollama":
                if intent == "complex":
                    target = getattr(self, '_heavy_model', 'qwen2.5:7b')
                else:
                    target = getattr(self, '_fast_model', 'qwen2.5:3b')
                if provider.model != target:
                    logger.info("Switching Ollama model: %s → %s (intent: %s)", provider.model, target, intent)
                    provider.model = target
                break

    # ------------------------------------------------------------------
    # Smart tool filtering
    # ------------------------------------------------------------------

    # Always include these core tools (small, general-purpose)
    _CORE_TOOLS = {"run_shell", "memory_save"}

    # Intent → additional tools to include
    _INTENT_TOOLS: dict[str, set[str]] = {
        "complex": {"ask_cloud"},
        "search": {"web_search"},
        "chat": {"__none__"},
        "dangerous": set(),
        "unknown": {"ask_cloud", "web_search", "notify"},
    }

    # Keyword → specific tools (for "system" intent sub-routing)
    _KEYWORD_TOOLS: dict[str, set[str]] = {
        "brightness|bright|dim|backlight|screen light": {"brightness"},
        "volume|mute|unmute|louder|quieter|sound|audio|speaker": {"volume"},
        "play|pause|next track|previous track|skip|song|music|media": {"media"},
        "screenshot|screen ?shot|screen ?cap": {"screenshot"},
        "clipboard|copy|paste|yank": {"clipboard_get", "clipboard_set"},
        "window|workspace|focus|tile|float|fullscreen|move window|launch": {"de_command"},
        "cron|schedule|every hour|every day|every morning": {"cron"},
        "cpu|ram|disk|battery|gpu|temperature|uptime|ip address|system info": {"sysinfo"},
        "notify|notification|alert|remind": {"notify"},
        "file|read file|write file|cat |create file": {"file_read", "file_write"},
        "bluetooth": {"bluetooth"},
        "mouse|click|cursor|drag": {"mouse"},
        "keyboard|type|press key|hotkey": {"keyboard"},
        "screen read|ocr|what.* on screen": {"screen_read"},
    }

    def _filter_tools(self, intent: str, message: str) -> list[dict]:
        """Return only the tool schemas relevant to the detected intent.

        For 'system' intent, uses keyword matching to pick only the
        specific tools needed — e.g. "decrease brightness" → only
        {run_shell, memory_save, brightness} instead of all 12 system tools.
        """
        intent_tools = self._INTENT_TOOLS.get(intent, set())
        # Special case: chat intent sends NO tools
        if "__none__" in intent_tools:
            return []

        allowed = set(self._CORE_TOOLS)

        if intent == "system":
            # Sub-route: match keywords to pick specific tools
            import re
            msg_lower = message.lower()
            matched_any = False
            for pattern, tools in self._KEYWORD_TOOLS.items():
                if re.search(pattern, msg_lower):
                    allowed |= tools
                    matched_any = True
            # If nothing matched, fall back to run_shell + notify
            if not matched_any:
                allowed.add("notify")
        else:
            allowed |= intent_tools

        # If message explicitly mentions a tool name, include it
        msg_lower = message.lower()
        all_schemas = self.tool_loader.get_tool_schemas()
        for schema in all_schemas:
            tool_name = schema["function"]["name"]
            if tool_name in msg_lower:
                allowed.add(tool_name)

        # Filter schemas
        filtered = [s for s in all_schemas if s["function"]["name"] in allowed]

        # Add MCP tools if manager has any
        if self.mcp_manager and self.mcp_manager.tools:
            filtered.extend(self.mcp_manager.get_tool_schemas())

        return filtered

    def _tools_desc_from_schemas(self, schemas: list[dict]) -> str:
        """Build a tool description string from filtered schemas."""
        lines = []
        for s in schemas:
            fn = s["function"]
            params = ", ".join(f"{k}: {v.get('type', 'str')}"
                               for k, v in fn.get("parameters", {}).get("properties", {}).items())
            lines.append(f"- {fn['name']}({params}): {fn.get('description', '')}")
        return "\n".join(lines)

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
