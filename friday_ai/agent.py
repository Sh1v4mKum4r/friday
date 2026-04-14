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

        # Direct tool shortcuts — bypass LLM for obvious commands
        direct = self._try_direct_tool(message)
        if direct:
            self.history.append({"role": "user", "content": message})
            self.history.append({"role": "assistant", "content": direct.content})
            self.memory.append_daily_log(f"[user] {message}")
            self.memory.append_daily_log(f"[assistant] {direct.content}")
            return direct

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
    # Direct tool shortcuts — bypass LLM for obvious commands
    # ------------------------------------------------------------------

    _DIRECT_COMMANDS: list[tuple[str, str, dict]] = [
        # --- Brightness ---
        (r"(?:increase|raise|up)\s*(?:the\s*)?brightness", "brightness", {"action": "up"}),
        (r"(?:decrease|lower|reduce|dim|down)\s*(?:the\s*)?brightness", "brightness", {"action": "down"}),
        (r"(?:set|change)\s*(?:the\s*)?brightness\s*(?:to\s*)?(\d+)", "brightness", {"action": "set {0}"}),
        (r"(?:get|show|what|check).*brightness", "brightness", {"action": "get"}),
        (r"max(?:imum)?\s*brightness", "brightness", {"action": "max"}),
        (r"min(?:imum)?\s*brightness", "brightness", {"action": "min"}),
        # --- Volume ---
        (r"(?:increase|raise|up|louder)\s*(?:the\s*)?volume", "volume", {"action": "up"}),
        (r"(?:decrease|lower|reduce|down|quieter)\s*(?:the\s*)?volume", "volume", {"action": "down"}),
        (r"(?:set|change)\s*(?:the\s*)?volume\s*(?:to\s*)?(\d+)", "volume", {"action": "set {0}"}),
        (r"^mute$|mute\s*(?:the\s*)?(?:audio|volume|sound)", "volume", {"action": "mute"}),
        (r"^unmute$|unmute\s*(?:the\s*)?(?:audio|volume|sound)", "volume", {"action": "unmute"}),
        (r"toggle\s*mute", "volume", {"action": "toggle"}),
        (r"(?:get|show|what|check).*volume", "volume", {"action": "get"}),
        # --- Media ---
        (r"(?:play|resume)\s*(?:music|media|song)?", "media", {"action": "play"}),
        (r"^pause$|pause\s*(?:music|media|song)", "media", {"action": "pause"}),
        (r"(?:next|skip)\s*(?:track|song)?", "media", {"action": "next"}),
        (r"(?:prev|previous)\s*(?:track|song)?", "media", {"action": "previous"}),
        (r"(?:stop)\s*(?:music|media|song|playing)", "media", {"action": "stop"}),
        (r"(?:what(?:'s|\s*is)\s*playing|now\s*playing|current\s*(?:song|track))", "media", {"action": "info"}),
        # --- Screenshot ---
        (r"take\s*(?:a\s*)?(?:full\s*)?screenshot", "screenshot", {"mode": "full"}),
        (r"screenshot\s*(?:of\s*)?(?:a\s*)?region", "screenshot", {"mode": "region"}),
        # --- Clipboard ---
        (r"(?:get|show|read|what(?:'s|\s*is)\s*(?:in|on))\s*(?:the\s*)?clipboard", "clipboard_get", {}),
        (r"(?:copy|set)\s*(?:to\s*)?clipboard\s+(.+)", "clipboard_set", {"content": "{0}"}),
        # --- Notifications ---
        (r"(?:send|show)\s*(?:a\s*)?notif(?:ication)?\s*[:\-]?\s*(.+)", "notify", {"message": "{0}"}),
        # --- System info ---
        (r"(?:show|get|what(?:'s|\s*is))\s*(?:my\s*)?(?:cpu|processor)\s*(?:temp|temperature|info)?", "sysinfo", {"mode": "cpu"}),
        (r"(?:show|get|what(?:'s|\s*is))\s*(?:my\s*)?(?:ram|memory)\s*(?:usage)?", "sysinfo", {"mode": "ram"}),
        (r"(?:show|get|what(?:'s|\s*is))\s*(?:my\s*)?(?:disk|storage)\s*(?:space|usage)?", "sysinfo", {"mode": "disk"}),
        (r"(?:show|get|what(?:'s|\s*is))\s*(?:my\s*)?battery", "sysinfo", {"mode": "battery"}),
        (r"(?:show|get|what(?:'s|\s*is))\s*(?:my\s*)?gpu\s*(?:temp|temperature|info|usage)?", "sysinfo", {"mode": "gpu"}),
        (r"(?:show|get|what(?:'s|\s*is))\s*(?:my\s*)?(?:ip|network|wifi|connection)", "sysinfo", {"mode": "network"}),
        (r"(?:show|get)\s*(?:my\s*)?(?:sys(?:tem)?\s*)?info", "sysinfo", {"mode": "all"}),
        (r"(?:show|get|what(?:'s|\s*is))\s*(?:my\s*)?bluetooth", "sysinfo", {"mode": "bluetooth"}),
        # --- DE commands ---
        (r"(?:move|switch\s*to)\s*workspace\s*(\d+)", "de_command", {"cmd": "workspace {0}"}),
        (r"(?:focus|switch)\s*(?:window\s*)?(?:to\s*)?(?:the\s*)?(left|right|up|down)", "de_command", {"cmd": "focus {0}"}),
        (r"move\s*window\s*(left|right|up|down)", "de_command", {"cmd": "move window {0}"}),
        (r"^fullscreen$|toggle\s*fullscreen", "de_command", {"cmd": "fullscreen"}),
        (r"^float$|toggle\s*float", "de_command", {"cmd": "float"}),
        (r"close\s*(?:this\s*)?window", "de_command", {"cmd": "close"}),
        (r"(?:launch|open)\s+(\S+)", "de_command", {"cmd": "launch {0}"}),
        # --- File operations ---
        (r"(?:read|show|cat)\s+(?:file\s+)?([/~]\S+)", "file_read", {"path": "{0}"}),
        # --- Cron ---
        (r"(?:show|list)\s*(?:my\s*)?(?:cron|scheduled)\s*(?:jobs|tasks)?", "cron", {"action": "list"}),
    ]

    # Greeting patterns → instant responses (no LLM, no tools)
    _GREETINGS: dict[str, list[str]] = {
        r"^(?:hi|hello|hey|yo|sup)[\s!.?]*$": [
            "Hey! What can I do for you?",
            "Hello! Ready to help.",
            "Hey there! What's up?",
        ],
        r"^(?:good\s*(?:morning|afternoon|evening))[\s!.?]*$": [
            "Good to see you! What do you need?",
            "Hey! How can I help today?",
        ],
        r"^(?:thanks?|thank\s*you|thx|cheers)[\s!.?]*$": [
            "Anytime.",
            "No problem.",
            "You got it.",
        ],
        r"^(?:bye|goodbye|see\s*(?:you|ya)|later|good\s*night)[\s!.?]*$": [
            "Later!",
            "See you around.",
            "Catch you later.",
        ],
        r"^(?:how\s*are\s*you|what'?s\s*up|how'?s\s*it\s*going)[\s!.?]*$": [
            "Running smooth. What do you need?",
            "All systems go. What can I do?",
        ],
        r"^(?:who\s*are\s*you|what\s*(?:are|can)\s*you.*)[\s!.?]*$": [
            "I'm Friday, your AI system assistant. I can run commands, control your desktop, search the web, and more. Try asking me something.",
        ],
    }

    def _try_direct_tool(self, message: str) -> ProviderResponse | None:
        """Check if message matches a greeting or a direct tool shortcut.

        Returns a ProviderResponse if matched, None otherwise.
        Bypasses the LLM entirely.
        """
        import re
        import random
        msg = message.lower().strip()

        # Check greetings first — instant, no LLM
        for pattern, responses in self._GREETINGS.items():
            if re.match(pattern, msg):
                return ProviderResponse(
                    content=random.choice(responses),
                    provider_name="friday",
                )

        for pattern, tool_name, args_template in self._DIRECT_COMMANDS:
            match = re.search(pattern, msg)
            if match:
                # Build args, replacing {0}, {1} with capture groups
                args = {}
                for k, v in args_template.items():
                    if isinstance(v, str) and "{0}" in v:
                        groups = match.groups()
                        args[k] = v.format(*groups) if groups else v
                    else:
                        args[k] = v

                try:
                    # Direct shortcuts bypass disabled check — call the tool's run() directly
                    tool = self.tool_loader.tools.get(tool_name)
                    if tool is None:
                        self.tool_loader.discover()
                        tool = self.tool_loader.tools.get(tool_name)
                    if tool is None:
                        continue  # Tool doesn't exist, try next pattern
                    result = str(tool.run(**args))
                except Exception as e:
                    result = f"Error: {e}"
                return ProviderResponse(
                    content=result,
                    provider_name="direct",
                )

        return None

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
        "unknown": {"ask_cloud", "web_search"},
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
        "bluetooth|wifi|network|connect|disconnect|vpn|proxy": {"bluetooth", "sysinfo"},
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
