"""MCP Client for Friday AI.

Connects to MCP servers (via stdio), discovers their tools, and routes
tool calls to the correct server. Integrates with Friday's existing
tool system — MCP tools appear alongside built-in tools.

MCP servers are configured in ~/.config/friday/mcp_servers.json:
{
  "servers": {
    "friday-gaming": {
      "command": "python",
      "args": ["/home/user/Projects/friday/mcp_servers/gaming/server.py"],
      "enabled": true
    }
  }
}
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str]
    enabled: bool = True
    env: dict[str, str] | None = None


@dataclass
class MCPTool:
    """An MCP tool discovered from a connected server."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    server_name: str


class MCPManager:
    """Manages connections to MCP servers and routes tool calls."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_path = config_dir / "mcp_servers.json"
        self.servers: dict[str, MCPServerConfig] = {}
        self.tools: dict[str, MCPTool] = {}  # tool_name -> MCPTool
        self._sessions: dict[str, tuple[ClientSession, Any]] = {}  # server_name -> (session, context)

    def load_config(self) -> None:
        """Load MCP server configs from mcp_servers.json."""
        if not self.config_path.exists():
            self.servers = {}
            return

        try:
            data = json.loads(self.config_path.read_text())
            for name, conf in data.get("servers", {}).items():
                self.servers[name] = MCPServerConfig(
                    name=name,
                    command=conf["command"],
                    args=conf.get("args", []),
                    enabled=conf.get("enabled", True),
                    env=conf.get("env"),
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse mcp_servers.json: %s", e)
            self.servers = {}

    async def connect_all(self) -> list[str]:
        """Connect to all enabled MCP servers and discover their tools.

        Returns list of connected server names.
        """
        self.load_config()
        connected = []

        for name, config in self.servers.items():
            if not config.enabled:
                continue
            try:
                await self._connect_server(config)
                connected.append(name)
            except Exception as e:
                logger.warning("Failed to connect to MCP server '%s': %s", name, e)

        return connected

    async def _connect_server(self, config: MCPServerConfig) -> None:
        """Connect to a single MCP server and discover its tools."""
        params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env,
        )

        # Create the stdio client connection
        read_stream, write_stream = await asyncio.wait_for(
            self._create_streams(params),
            timeout=10,
        )

        session = ClientSession(read_stream, write_stream)
        await session.initialize()

        # Discover tools
        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            mcp_tool = MCPTool(
                name=f"mcp_{config.name}_{tool.name}",  # prefix to avoid collisions
                description=f"[{config.name}] {tool.description}",
                parameters=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                server_name=config.name,
            )
            self.tools[mcp_tool.name] = mcp_tool

        self._sessions[config.name] = session
        logger.info("Connected to MCP server '%s': %d tools", config.name, len(tools_result.tools))

    async def _create_streams(self, params: StdioServerParameters):
        """Create stdio streams for an MCP server."""
        env = params.env or {}
        process = await asyncio.create_subprocess_exec(
            params.command, *params.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**__import__('os').environ, **env} if env else None,
        )
        return process.stdout, process.stdin

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call an MCP tool by name."""
        tool = self.tools.get(tool_name)
        if tool is None:
            return f"Error: MCP tool '{tool_name}' not found"

        session = self._sessions.get(tool.server_name)
        if session is None:
            return f"Error: MCP server '{tool.server_name}' not connected"

        try:
            # Strip the mcp_{server}_ prefix to get original tool name
            original_name = tool_name.replace(f"mcp_{tool.server_name}_", "", 1)
            result = await session.call_tool(original_name, arguments)

            # Extract text from result
            if hasattr(result, 'content'):
                texts = []
                for block in result.content:
                    if hasattr(block, 'text'):
                        texts.append(block.text)
                return "\n".join(texts) if texts else "Done."
            return str(result)
        except Exception as e:
            return f"Error calling MCP tool '{tool_name}': {e}"

    def get_tool_schemas(self) -> list[dict]:
        """Return OpenAI-compatible tool schemas for all MCP tools."""
        schemas = []
        for tool in self.tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters or {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            })
        return schemas

    def get_tools_description(self) -> str:
        """Return formatted tool descriptions for prompt injection."""
        lines = []
        for tool in self.tools.values():
            props = tool.parameters.get("properties", {})
            params = ", ".join(f"{k}: {v.get('type', 'str')}" for k, v in props.items())
            lines.append(f"- {tool.name}({params}): {tool.description}")
        return "\n".join(lines)

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name belongs to an MCP server."""
        return tool_name in self.tools

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for name, session in self._sessions.items():
            try:
                if hasattr(session, 'close'):
                    await session.close()
            except Exception:
                pass
        self._sessions.clear()
        self.tools.clear()
