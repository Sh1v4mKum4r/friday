"""FastAPI server for Friday AI.

Exposes the Friday agent over HTTP so that the Rust core (and any other
client) can talk to it via a well-defined REST API.

Usage:
    python -m friday_ai.server
"""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query

from .agent import Agent
from .config import (
    ensure_dirs,
    get_config_dir,
    get_data_dir,
    load_config,
)
from .providers.claude import ClaudeCLIProvider, ClaudeProvider
from .providers.gemini import GeminiCLIProvider, GeminiProvider
from .providers.ollama import OllamaProvider
from .providers.openai_provider import OpenAIProvider
from .providers.web_search import WebSearchProvider
from .mcp_client import MCPManager
from .router import ProviderRouter
from .tool_loader import ToolLoader
from .tools.core import memory_tool

try:
    from pydantic import BaseModel
except ImportError:
    raise ImportError("pydantic is required — install it with: pip install pydantic")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    force_provider: str | None = None
    race: bool = False


class ChatResponse(BaseModel):
    response: str
    provider: str


class ContextResponse(BaseModel):
    context: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(config_path: Path | None = None) -> FastAPI:
    """Build and return the FastAPI application.

    Parameters
    ----------
    config_path:
        Path to a ``config.toml`` file.  When *None* a ``config.toml`` file
        inside the config directory (as returned by :func:`get_config_dir`) is
        used.

    Returns
    -------
    FastAPI
        A fully configured application instance with all endpoints registered.
    """
    app = FastAPI(title="Friday AI", version="0.1.0")

    # ------------------------------------------------------------------ #
    # Resolve directories                                                  #
    # ------------------------------------------------------------------ #
    config_dir = get_config_dir()
    data_dir = get_data_dir()
    ensure_dirs()

    # ------------------------------------------------------------------ #
    # Load config                                                          #
    # ------------------------------------------------------------------ #
    if config_path is None:
        config_path = config_dir / "config.toml"
    config = load_config(config_path)

    # ------------------------------------------------------------------ #
    # Build provider list                                                  #
    # ------------------------------------------------------------------ #
    providers = []

    # 1. Ollama always first (local LLM)
    providers.append(
        OllamaProvider(
            model=config.providers.ollama_model,
            base_url=config.providers.ollama_url,
        )
    )

    # 2. API providers (if keys are configured)
    if config.providers.gemini_api_key:
        providers.append(
            GeminiProvider(
                api_key=config.providers.gemini_api_key,
                model=config.providers.gemini_model,
            )
        )
    if config.providers.claude_api_key:
        providers.append(
            ClaudeProvider(
                api_key=config.providers.claude_api_key,
                model=config.providers.claude_model,
            )
        )
    if config.providers.openai_api_key:
        providers.append(
            OpenAIProvider(
                api_key=config.providers.openai_api_key,
                model=config.providers.openai_model,
            )
        )

    # 3. CLI fallbacks (when no API key is set) — Claude first, faster/more reliable
    if not config.providers.claude_api_key:
        providers.append(ClaudeCLIProvider())
    if not config.providers.gemini_api_key:
        providers.append(GeminiCLIProvider())

    # 4. Web search as last resort
    providers.append(WebSearchProvider())

    # ------------------------------------------------------------------ #
    # Create router, tool loader, and agent                                #
    # ------------------------------------------------------------------ #
    router = ProviderRouter(
        providers=providers,
        auto_escalate=config.behavior.auto_escalate,
        provider_mode=config.behavior.provider_mode,
    )

    tool_loader = ToolLoader(
        tool_dirs=[
            Path(__file__).parent / "tools" / "core",
            config_dir / "tools" / "plugins",
        ]
    )
    tool_loader.discover()

    # MCP server connections
    mcp_manager = MCPManager(config_dir)

    agent = Agent(
        router=router,
        tool_loader=tool_loader,
        config_dir=config_dir,
        data_dir=data_dir,
        mcp_manager=mcp_manager,
    )

    # ------------------------------------------------------------------ #
    # Store on app.state for endpoint access                               #
    # ------------------------------------------------------------------ #
    app.state.agent = agent
    app.state.config = config
    app.state.tool_loader = tool_loader
    app.state.mcp_manager = mcp_manager

    @app.on_event("startup")
    async def startup():
        connected = await mcp_manager.connect_all()
        if connected:
            logger.info("MCP servers connected: %s", connected)

    @app.on_event("shutdown")
    async def shutdown():
        await mcp_manager.disconnect_all()

    # ------------------------------------------------------------------ #
    # Endpoints                                                            #
    # ------------------------------------------------------------------ #

    @app.get("/health")
    async def health():
        """Return server status and available provider names."""
        provider_names = [p.name for p in providers]
        return {"status": "online", "providers": provider_names}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """Send a message to the agent and return the response."""
        result = await app.state.agent.chat(
            message=request.message,
            force_provider=request.force_provider,
            race=request.race,
        )
        return ChatResponse(response=result.content, provider=result.provider_name)

    @app.get("/context", response_model=ContextResponse)
    async def context():
        """Return the current system prompt and recent conversation history."""
        dump = app.state.agent.get_context_dump()
        return ContextResponse(context=dump)

    @app.post("/reload")
    async def reload():
        """Hot-reload all tools from disk and return the new count and names."""
        tools = app.state.tool_loader.reload()
        return {"reloaded": len(tools), "tools": [t.name for t in tools]}

    @app.post("/memory/list")
    async def memory_list():
        """Return all long-term memory entries."""
        entries = app.state.agent.memory.list_memory()
        return {"entries": entries}

    @app.post("/memory/forget")
    async def memory_forget(keyword: str = Query(...)):
        """Remove all memory entries containing *keyword*."""
        app.state.agent.memory.forget_memory(keyword)
        return {"status": "ok", "forgot": keyword}

    @app.post("/memory/clear")
    async def memory_clear():
        """Erase all long-term memory."""
        app.state.agent.memory.clear_memory()
        return {"status": "cleared"}

    @app.post("/session/save")
    async def session_save():
        """Persist the current conversation history to disk."""
        app.state.agent.save_session()
        return {"status": "saved"}

    @app.post("/session/load")
    async def session_load():
        """Load the most recent saved session from disk."""
        loaded = app.state.agent.load_session()
        return {"status": "loaded" if loaded else "no session found"}

    @app.post("/classify")
    async def classify(request: ChatRequest):
        """Classify a message's intent without sending it to an LLM."""
        from .router import classify_intent
        intent = classify_intent(request.message)
        return {"message": request.message, "intent": intent}

    @app.get("/mcp/status")
    async def mcp_status():
        """Show connected MCP servers and their tools."""
        return {
            "servers": list(mcp_manager._sessions.keys()),
            "tools": [
                {"name": t.name, "description": t.description, "server": t.server_name}
                for t in mcp_manager.tools.values()
            ],
        }

    @app.post("/mcp/reconnect")
    async def mcp_reconnect():
        """Disconnect and reconnect all MCP servers."""
        await mcp_manager.disconnect_all()
        connected = await mcp_manager.connect_all()
        return {"connected": connected}

    return app


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Load config and start the uvicorn server."""
    config_dir = get_config_dir()
    config_path = config_dir / "config.toml"

    # Load config just to get server host/port; create_app will reload it
    config = load_config(config_path)

    app = create_app(config_path=config_path)

    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )


# Module-level app for uvicorn (e.g., uvicorn friday_ai.server:app)
app = create_app()

if __name__ == "__main__":
    main()
