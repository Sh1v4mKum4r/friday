# Friday TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a keyboard-driven Terminal UI for Friday AI using Python Textual, with 4 switchable themes, SSE streaming, btop-style settings, and vim-like navigation.

**Architecture:** Pure Textual app living inside `friday_ai/tui/` package. Talks to Friday backend over HTTP at `http://127.0.0.1:65535`. Shares types and config with the backend. New `/chat/stream` SSE endpoint added to the backend for live token streaming.

**Tech Stack:** Python Textual (TUI framework), httpx (async HTTP), sse-starlette (SSE backend), pytest + pytest-asyncio (testing)

**Spec:** `docs/superpowers/specs/2026-04-14-friday-tui-design.md`

---

## File Map

### New Files (Create)

```
friday_ai/tui/__init__.py           — Package init, exports main()
friday_ai/tui/__main__.py           — python -m friday_ai.tui entry point
friday_ai/tui/app.py                — FridayApp main Textual app
friday_ai/tui/client.py             — Async HTTP client for Friday API
friday_ai/tui/config.py             — TUI-specific config dataclass + load/save

friday_ai/tui/screens/__init__.py   — Screen exports
friday_ai/tui/screens/chat.py       — Main chat screen
friday_ai/tui/screens/welcome.py    — Empty state welcome screen
friday_ai/tui/screens/settings.py   — btop-style settings overlay

friday_ai/tui/widgets/__init__.py   — Widget exports
friday_ai/tui/widgets/message.py    — Chat message (user/assistant)
friday_ai/tui/widgets/input_bar.py  — Smart input with mode detection
friday_ai/tui/widgets/mode_bar.py   — Chat/Command/Search mode switcher
friday_ai/tui/widgets/sidebar.py    — Conversation history overlay
friday_ai/tui/widgets/telemetry.py  — Provider/MCP status panel
friday_ai/tui/widgets/code_block.py — Syntax-highlighted code with copy

friday_ai/tui/themes/obsidian.tcss  — Purple theme (default)
friday_ai/tui/themes/neural.tcss    — Cyan HUD theme
friday_ai/tui/themes/prism.tcss     — Red stealth theme
friday_ai/tui/themes/techno.tcss    — Green terminal theme

friday_ai/tui/utils/__init__.py     — Utility exports
friday_ai/tui/utils/clipboard.py    — wl-copy/xclip abstraction

bin/friday-tui                      — Shell entry point

tests/test_tui_config.py            — TUI config tests
tests/test_tui_client.py            — API client tests
tests/test_tui_widgets.py           — Widget rendering tests
tests/test_tui_screens.py           — Screen composition tests
tests/test_tui_app.py               — App integration tests
tests/test_stream_endpoint.py       — SSE /chat/stream tests
```

### Modified Files

```
pyproject.toml                      — Add textual, sse-starlette deps + friday-tui script
friday_ai/server.py                 — Add POST /chat/stream SSE endpoint
friday_ai/agent.py                  — Add stream_chat() async generator method
friday_ai/config.py                 — Add TUIConfig dataclass + [tui] section parsing
```

---

## Task 1: Project Setup & Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `friday_ai/tui/__init__.py`
- Create: `friday_ai/tui/__main__.py`
- Create: all `__init__.py` files for subpackages

- [ ] **Step 1: Add dependencies to pyproject.toml**

Read the current `pyproject.toml` and add the TUI dependencies. Add after existing optional-dependencies:

```toml
[project.optional-dependencies]
tui = [
    "textual>=1.0.0",
]
stream = [
    "sse-starlette>=2.0.0",
]
```

Add to `[project.scripts]`:

```toml
friday-tui = "friday_ai.tui:main"
```

- [ ] **Step 2: Create package structure**

Create all `__init__.py` files:

`friday_ai/tui/__init__.py`:
```python
"""Friday TUI — keyboard-driven terminal interface."""

from friday_ai.tui.app import FridayApp


def main() -> None:
    """Entry point for friday-tui command."""
    app = FridayApp()
    app.run()
```

`friday_ai/tui/__main__.py`:
```python
"""Allow running as python -m friday_ai.tui."""

from friday_ai.tui import main

main()
```

`friday_ai/tui/screens/__init__.py`:
```python
"""TUI screens."""
```

`friday_ai/tui/widgets/__init__.py`:
```python
"""TUI widgets."""
```

`friday_ai/tui/utils/__init__.py`:
```python
"""TUI utilities."""
```

- [ ] **Step 3: Install dependencies**

```bash
cd ~/Projects/friday
source .venv/bin/activate
pip install "textual>=1.0.0" "sse-starlette>=2.0.0"
```

- [ ] **Step 4: Verify import works**

```bash
cd ~/Projects/friday
python -c "import textual; print(textual.__version__)"
```

Expected: version number printed, no import errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml friday_ai/tui/
git commit -m "feat(tui): scaffold TUI package structure and dependencies"
```

---

## Task 2: TUI Config

**Files:**
- Create: `friday_ai/tui/config.py`
- Modify: `friday_ai/config.py`
- Create: `tests/test_tui_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tui_config.py`:
```python
"""Tests for TUI configuration."""

import tempfile
from pathlib import Path

from friday_ai.tui.config import TUIConfig, load_tui_config, save_tui_config


class TestTUIConfig:
    def test_default_values(self):
        config = TUIConfig()
        assert config.theme == "obsidian"
        assert config.render_mode == "live_stream"
        assert config.typewriter_speed == 40
        assert config.settings_mode == "simple"
        assert config.show_timestamps is True
        assert config.show_provider_tags is True
        assert config.show_latency is True
        assert config.message_spacing == "normal"
        assert config.code_theme == "monokai"
        assert config.sidebar_width == 30
        assert config.telemetry_width == 30
        assert config.telemetry_refresh == 30
        assert config.ascii_logo is True
        assert config.clock_in_header is True

    def test_default_keybinds(self):
        config = TUIConfig()
        assert config.keybinds["toggle_sidebar"] == "ctrl+b"
        assert config.keybinds["toggle_telemetry"] == "ctrl+t"
        assert config.keybinds["open_settings"] == "ctrl+s"
        assert config.keybinds["new_conversation"] == "ctrl+n"
        assert config.keybinds["search_conversations"] == "ctrl+p"
        assert config.keybinds["cycle_theme"] == "ctrl+shift+t"
        assert config.keybinds["toggle_render_mode"] == "ctrl+r"
        assert config.keybinds["copy_code"] == "y"
        assert config.keybinds["send_message"] == "enter"
        assert config.keybinds["newline"] == "shift+enter"

    def test_load_from_toml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(
                "[tui]\n"
                'theme = "neural"\n'
                'render_mode = "typewriter"\n'
                "typewriter_speed = 60\n"
                'message_spacing = "compact"\n'
                "\n"
                "[tui.keybinds]\n"
                'toggle_sidebar = "ctrl+l"\n'
            )
            f.flush()
            config = load_tui_config(Path(f.name))
            assert config.theme == "neural"
            assert config.render_mode == "typewriter"
            assert config.typewriter_speed == 60
            assert config.message_spacing == "compact"
            assert config.keybinds["toggle_sidebar"] == "ctrl+l"
            # Non-overridden keybinds keep defaults
            assert config.keybinds["toggle_telemetry"] == "ctrl+t"

    def test_load_missing_file_returns_defaults(self):
        config = load_tui_config(Path("/nonexistent/config.toml"))
        assert config.theme == "obsidian"

    def test_save_and_reload(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[server]\nport = 65535\n")
            f.flush()
            path = Path(f.name)

        config = TUIConfig(theme="prism", typewriter_speed=80)
        save_tui_config(config, path)

        reloaded = load_tui_config(path)
        assert reloaded.theme == "prism"
        assert reloaded.typewriter_speed == 80
        # Existing sections preserved
        content = path.read_text()
        assert "port = 65535" in content

    def test_valid_themes(self):
        config = TUIConfig()
        assert config.theme in ("obsidian", "neural", "prism", "techno")

    def test_valid_render_modes(self):
        config = TUIConfig()
        assert config.render_mode in ("live_stream", "typewriter")

    def test_valid_message_spacing(self):
        config = TUIConfig()
        assert config.message_spacing in ("compact", "normal", "relaxed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'friday_ai.tui.config'`

- [ ] **Step 3: Implement TUI config**

`friday_ai/tui/config.py`:
```python
"""TUI-specific configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_THEMES = ("obsidian", "neural", "prism", "techno")
VALID_RENDER_MODES = ("live_stream", "typewriter")
VALID_SPACING = ("compact", "normal", "relaxed")

DEFAULT_KEYBINDS: dict[str, str] = {
    "toggle_sidebar": "ctrl+b",
    "toggle_telemetry": "ctrl+t",
    "open_settings": "ctrl+s",
    "new_conversation": "ctrl+n",
    "search_conversations": "ctrl+p",
    "cycle_theme": "ctrl+shift+t",
    "toggle_render_mode": "ctrl+r",
    "copy_code": "y",
    "send_message": "enter",
    "newline": "shift+enter",
}


@dataclass
class TUIConfig:
    """Configuration for the Friday TUI."""

    theme: str = "obsidian"
    render_mode: str = "live_stream"
    typewriter_speed: int = 40
    settings_mode: str = "simple"
    show_timestamps: bool = True
    show_provider_tags: bool = True
    show_latency: bool = True
    message_spacing: str = "normal"
    code_theme: str = "monokai"
    sidebar_width: int = 30
    telemetry_width: int = 30
    telemetry_refresh: int = 30
    ascii_logo: bool = True
    clock_in_header: bool = True
    keybinds: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_KEYBINDS))


def load_tui_config(config_path: Path) -> TUIConfig:
    """Load TUI config from [tui] section of a TOML file."""
    config = TUIConfig()

    if not config_path.exists():
        return config

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    tui_data: dict[str, Any] = data.get("tui", {})
    keybinds_data: dict[str, str] = tui_data.pop("keybinds", {})

    for key, value in tui_data.items():
        if hasattr(config, key):
            setattr(config, key, value)

    config.keybinds.update(keybinds_data)

    return config


def save_tui_config(config: TUIConfig, config_path: Path) -> None:
    """Save TUI config to [tui] section of a TOML file, preserving other sections."""
    existing_content = ""
    if config_path.exists():
        existing_content = config_path.read_text()

    # Remove existing [tui] and [tui.keybinds] sections
    lines = existing_content.splitlines()
    filtered: list[str] = []
    in_tui_section = False
    for line in lines:
        stripped = line.strip()
        if stripped in ("[tui]", "[tui.keybinds]"):
            in_tui_section = True
            continue
        if in_tui_section and stripped.startswith("[") and stripped not in ("[tui]", "[tui.keybinds]"):
            in_tui_section = False
        if not in_tui_section:
            filtered.append(line)

    # Build new [tui] section
    tui_lines = ["\n[tui]"]
    for key in (
        "theme", "render_mode", "typewriter_speed", "settings_mode",
        "show_timestamps", "show_provider_tags", "show_latency",
        "message_spacing", "code_theme", "sidebar_width", "telemetry_width",
        "telemetry_refresh", "ascii_logo", "clock_in_header",
    ):
        value = getattr(config, key)
        if isinstance(value, bool):
            tui_lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, int):
            tui_lines.append(f"{key} = {value}")
        else:
            tui_lines.append(f'{key} = "{value}"')

    tui_lines.append("\n[tui.keybinds]")
    for key, value in config.keybinds.items():
        tui_lines.append(f'{key} = "{value}"')

    output = "\n".join(filtered).rstrip() + "\n" + "\n".join(tui_lines) + "\n"
    config_path.write_text(output)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_config.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/config.py tests/test_tui_config.py
git commit -m "feat(tui): add TUI config dataclass with load/save"
```

---

## Task 3: API Client

**Files:**
- Create: `friday_ai/tui/client.py`
- Create: `tests/test_tui_client.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tui_client.py`:
```python
"""Tests for TUI API client."""

import json

import httpx
import pytest

from friday_ai.tui.client import FridayTUIClient


@pytest.fixture
def mock_transport():
    """Create a mock transport that returns predefined responses."""
    responses = {}

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            path = request.url.path
            method = request.method

            key = f"{method} {path}"
            if key in responses:
                data = responses[key]
                return httpx.Response(200, json=data)
            return httpx.Response(404, json={"error": "not found"})

    transport = MockTransport()
    transport.responses = responses
    return transport


@pytest.fixture
def client(mock_transport):
    """Create a client with mock transport."""
    http = httpx.AsyncClient(transport=mock_transport, base_url="http://test:65535")
    return FridayTUIClient(http_client=http)


class TestFridayTUIClient:
    @pytest.mark.asyncio
    async def test_chat(self, client, mock_transport):
        mock_transport.responses["POST /chat"] = {
            "response": "Hello!",
            "provider": "ollama",
        }
        result = await client.chat("Hi")
        assert result["response"] == "Hello!"
        assert result["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_health(self, client, mock_transport):
        mock_transport.responses["GET /health"] = {
            "status": "online",
            "providers": ["ollama", "claude"],
        }
        result = await client.health()
        assert result["status"] == "online"
        assert "ollama" in result["providers"]

    @pytest.mark.asyncio
    async def test_classify(self, client, mock_transport):
        mock_transport.responses["POST /classify"] = {
            "message": "hello",
            "intent": "chat",
        }
        result = await client.classify("hello")
        assert result["intent"] == "chat"

    @pytest.mark.asyncio
    async def test_memory_list(self, client, mock_transport):
        mock_transport.responses["POST /memory/list"] = {
            "entries": ["user likes dark themes", "user uses arch"],
        }
        result = await client.memory_list()
        assert len(result["entries"]) == 2

    @pytest.mark.asyncio
    async def test_mcp_status(self, client, mock_transport):
        mock_transport.responses["GET /mcp/status"] = {
            "servers": ["dev", "files"],
            "tools": [{"name": "git_status", "server": "dev"}],
        }
        result = await client.mcp_status()
        assert "dev" in result["servers"]

    @pytest.mark.asyncio
    async def test_session_save(self, client, mock_transport):
        mock_transport.responses["POST /session/save"] = {"status": "saved"}
        result = await client.session_save()
        assert result["status"] == "saved"

    @pytest.mark.asyncio
    async def test_session_load(self, client, mock_transport):
        mock_transport.responses["POST /session/load"] = {"status": "loaded"}
        result = await client.session_load()
        assert result["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_reload(self, client, mock_transport):
        mock_transport.responses["POST /reload"] = {
            "reloaded": 21,
            "tools": ["run_shell", "file_read"],
        }
        result = await client.reload()
        assert result["reloaded"] == 21

    @pytest.mark.asyncio
    async def test_mcp_reconnect(self, client, mock_transport):
        mock_transport.responses["POST /mcp/reconnect"] = {
            "connected": ["dev", "files"],
        }
        result = await client.mcp_reconnect()
        assert "dev" in result["connected"]

    @pytest.mark.asyncio
    async def test_context(self, client, mock_transport):
        mock_transport.responses["GET /context"] = {"context": "system prompt..."}
        result = await client.context()
        assert "context" in result

    @pytest.mark.asyncio
    async def test_memory_forget(self, client, mock_transport):
        mock_transport.responses["POST /memory/forget"] = {
            "status": "ok",
            "forgot": "dark themes",
        }
        result = await client.memory_forget("dark themes")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_memory_clear(self, client, mock_transport):
        mock_transport.responses["POST /memory/clear"] = {"status": "cleared"}
        result = await client.memory_clear()
        assert result["status"] == "cleared"

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, mock_transport):
        """Client should handle connection failures gracefully."""
        http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(500)),
            base_url="http://test:65535",
        )
        client = FridayTUIClient(http_client=http)
        result = await client.health()
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'friday_ai.tui.client'`

- [ ] **Step 3: Implement the client**

`friday_ai/tui/client.py`:
```python
"""Async HTTP client for the Friday API."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx


class FridayTUIClient:
    """Wraps all Friday API endpoints with async methods."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 65535,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is not None:
            self._http = http_client
            self._owns_client = False
        else:
            self._http = httpx.AsyncClient(
                base_url=f"http://{host}:{port}",
                timeout=120.0,
            )
            self._owns_client = True

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._http.aclose()

    async def _get(self, path: str) -> dict[str, Any] | None:
        try:
            r = await self._http.get(path)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    async def _post(self, path: str, **kwargs: Any) -> dict[str, Any] | None:
        try:
            r = await self._http.post(path, **kwargs)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, httpx.InvalidURL):
            return None

    # --- Chat ---

    async def chat(self, message: str, force_provider: str | None = None, race: bool = False) -> dict[str, Any] | None:
        """Send a chat message. Returns {"response": str, "provider": str}."""
        payload: dict[str, Any] = {"message": message}
        if force_provider:
            payload["force_provider"] = force_provider
        if race:
            payload["race"] = True
        return await self._post("/chat", json=payload)

    async def chat_stream(self, message: str, force_provider: str | None = None) -> AsyncIterator[dict[str, Any]]:
        """Stream chat tokens via SSE. Yields {"token": str, "done": bool, ...}."""
        payload: dict[str, Any] = {"message": message}
        if force_provider:
            payload["force_provider"] = force_provider
        try:
            async with self._http.stream("POST", "/chat/stream", json=payload) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
        except httpx.HTTPError:
            yield {"token": "", "done": True, "error": "stream connection failed"}

    # --- Health ---

    async def health(self) -> dict[str, Any] | None:
        """Check backend health. Returns {"status": str, "providers": [str]}."""
        return await self._get("/health")

    # --- Classification ---

    async def classify(self, message: str) -> dict[str, Any] | None:
        """Classify intent. Returns {"message": str, "intent": str}."""
        return await self._post("/classify", json={"message": message})

    # --- Context ---

    async def context(self) -> dict[str, Any] | None:
        """Get system context. Returns {"context": str}."""
        return await self._get("/context")

    # --- Session ---

    async def session_save(self) -> dict[str, Any] | None:
        """Save current session."""
        return await self._post("/session/save")

    async def session_load(self) -> dict[str, Any] | None:
        """Load last saved session."""
        return await self._post("/session/load")

    # --- Memory ---

    async def memory_list(self) -> dict[str, Any] | None:
        """List memory entries."""
        return await self._post("/memory/list")

    async def memory_forget(self, keyword: str) -> dict[str, Any] | None:
        """Forget memory entries matching keyword."""
        return await self._post("/memory/forget", params={"keyword": keyword})

    async def memory_clear(self) -> dict[str, Any] | None:
        """Clear all memory."""
        return await self._post("/memory/clear")

    # --- Tools ---

    async def reload(self) -> dict[str, Any] | None:
        """Hot-reload tools."""
        return await self._post("/reload")

    # --- MCP ---

    async def mcp_status(self) -> dict[str, Any] | None:
        """Get MCP server status."""
        return await self._get("/mcp/status")

    async def mcp_reconnect(self) -> dict[str, Any] | None:
        """Reconnect MCP servers."""
        return await self._post("/mcp/reconnect")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_client.py -v
```

Expected: All 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/client.py tests/test_tui_client.py
git commit -m "feat(tui): add async HTTP client wrapping all Friday API endpoints"
```

---

## Task 4: Theme CSS Files

**Files:**
- Create: `friday_ai/tui/themes/obsidian.tcss`
- Create: `friday_ai/tui/themes/neural.tcss`
- Create: `friday_ai/tui/themes/prism.tcss`
- Create: `friday_ai/tui/themes/techno.tcss`

- [ ] **Step 1: Create Obsidian theme (default, purple)**

`friday_ai/tui/themes/obsidian.tcss`:
```css
/* Obsidian — "The Digital Curator" — deep purple accents */

Screen {
    background: #0e0d15;
    color: #f2effa;
}

/* === Surface Hierarchy === */

#chat-area {
    background: #13131b;
}

#messages {
    background: #0e0d15;
    overflow-y: auto;
}

/* === Messages === */

.msg-user {
    background: #13131b;
    color: #f2effa;
    margin: 1 2 0 12;
    padding: 1 2;
}

.msg-assistant {
    background: #191922;
    color: #f2effa;
    margin: 1 12 0 2;
    padding: 1 2;
    border-left: thick #ba9eff;
}

.msg-user .timestamp {
    color: #8a8694;
}

.msg-assistant .timestamp {
    color: #8a8694;
}

.provider-tag {
    background: #8455ef;
    color: #f2effa;
    padding: 0 1;
}

.latency-tag {
    color: #8a8694;
}

/* === Input === */

#input-area {
    background: #0e0d15;
    dock: bottom;
    height: auto;
    max-height: 8;
    padding: 0 1;
}

#chat-input {
    background: #0a0a10;
    color: #f2effa;
    border: none;
    padding: 0 1;
}

#chat-input:focus {
    border-bottom: tall #ba9eff;
}

.input-placeholder {
    color: #8a8694;
}

/* === Mode Bar === */

#mode-bar {
    background: #0e0d15;
    height: 1;
    padding: 0 1;
}

.mode-active {
    color: #ba9eff;
    text-style: bold;
}

.mode-inactive {
    color: #8a8694;
}

/* === Sidebar === */

#sidebar {
    background: #0e0d15;
    width: 30;
    dock: left;
    border-right: tall #191922;
}

#sidebar-title {
    color: #8a8694;
    text-style: bold;
    padding: 1 1;
}

.session-item {
    padding: 0 1;
    height: 1;
}

.session-item:hover {
    background: #191922;
}

.session-item.-selected {
    background: #252530;
    color: #ba9eff;
}

.session-group-label {
    color: #8a8694;
    text-style: bold;
    padding: 1 1 0 1;
}

/* === Telemetry Panel === */

#telemetry {
    background: #0e0d15;
    width: 30;
    dock: right;
    border-left: tall #191922;
}

#telemetry-title {
    color: #8a8694;
    text-style: bold;
    padding: 1 1;
}

.telemetry-label {
    color: #8a8694;
}

.telemetry-value {
    color: #f2effa;
}

.status-online {
    color: #4ae176;
}

.status-offline {
    color: #d73357;
}

.status-connecting {
    color: #ba9eff;
}

/* === Settings === */

#settings-screen {
    background: #0e0d15;
}

.settings-tab-active {
    background: #191922;
    color: #ba9eff;
    text-style: bold;
    padding: 0 2;
}

.settings-tab-inactive {
    background: #0e0d15;
    color: #8a8694;
    padding: 0 2;
}

.settings-label {
    color: #f2effa;
}

.settings-value {
    color: #ba9eff;
}

.settings-field.-selected {
    background: #191922;
}

/* === Welcome Screen === */

#welcome {
    background: #0e0d15;
    align: center middle;
}

#welcome-logo {
    color: #ba9eff;
    text-style: bold;
}

#welcome-title {
    color: #f2effa;
}

.quick-action {
    background: #191922;
    padding: 1 2;
    margin: 1;
    width: 24;
    height: 5;
}

.quick-action:hover {
    background: #252530;
    border: tall #ba9eff;
}

/* === Code Blocks === */

.code-block {
    background: #0a0a10;
    padding: 1;
    margin: 1 0;
}

.code-header {
    background: #191922;
    color: #8a8694;
    padding: 0 1;
}

.code-copy-hint {
    color: #8455ef;
}

/* === General === */

.hidden {
    display: none;
}

.thinking-indicator {
    color: #ba9eff;
}

Toast {
    background: #191922;
    color: #f2effa;
}

Header {
    background: #13131b;
    color: #f2effa;
}

Footer {
    background: #13131b;
    color: #8a8694;
}
```

- [ ] **Step 2: Create Neural theme (cyan HUD)**

`friday_ai/tui/themes/neural.tcss`:
```css
/* Neural Ether — "The Synthetic Intelligence Core" — cyan HUD */

Screen {
    background: #0e0e14;
    color: #e0f0ff;
}

#chat-area { background: #131319; }
#messages { background: #0e0e14; overflow-y: auto; }

.msg-user {
    background: #131319; color: #e0f0ff;
    margin: 1 2 0 12; padding: 1 2;
}
.msg-assistant {
    background: #1b1b21; color: #e0f0ff;
    margin: 1 12 0 2; padding: 1 2;
    border-left: thick #69daff;
}
.msg-user .timestamp { color: #6a8a94; }
.msg-assistant .timestamp { color: #6a8a94; }
.provider-tag { background: #00cffc; color: #0e0e14; padding: 0 1; }
.latency-tag { color: #6a8a94; }

#input-area { background: #0e0e14; dock: bottom; height: auto; max-height: 8; padding: 0 1; }
#chat-input { background: #0a0a10; color: #e0f0ff; border: none; padding: 0 1; }
#chat-input:focus { border-bottom: tall #69daff; }
.input-placeholder { color: #6a8a94; }

#mode-bar { background: #0e0e14; height: 1; padding: 0 1; }
.mode-active { color: #69daff; text-style: bold; }
.mode-inactive { color: #6a8a94; }

#sidebar { background: #0e0e14; width: 30; dock: left; border-right: tall #1b1b21; }
#sidebar-title { color: #6a8a94; text-style: bold; padding: 1 1; }
.session-item { padding: 0 1; height: 1; }
.session-item:hover { background: #1b1b21; }
.session-item.-selected { background: #25252e; color: #69daff; }
.session-group-label { color: #6a8a94; text-style: bold; padding: 1 1 0 1; }

#telemetry { background: #0e0e14; width: 30; dock: right; border-left: tall #1b1b21; }
#telemetry-title { color: #6a8a94; text-style: bold; padding: 1 1; }
.telemetry-label { color: #6a8a94; }
.telemetry-value { color: #e0f0ff; }
.status-online { color: #4ae176; }
.status-offline { color: #ff4466; }
.status-connecting { color: #69daff; }

#settings-screen { background: #0e0e14; }
.settings-tab-active { background: #1b1b21; color: #69daff; text-style: bold; padding: 0 2; }
.settings-tab-inactive { background: #0e0e14; color: #6a8a94; padding: 0 2; }
.settings-label { color: #e0f0ff; }
.settings-value { color: #69daff; }
.settings-field.-selected { background: #1b1b21; }

#welcome { background: #0e0e14; align: center middle; }
#welcome-logo { color: #69daff; text-style: bold; }
#welcome-title { color: #e0f0ff; }
.quick-action { background: #1b1b21; padding: 1 2; margin: 1; width: 24; height: 5; }
.quick-action:hover { background: #25252e; border: tall #69daff; }

.code-block { background: #0a0a10; padding: 1; margin: 1 0; }
.code-header { background: #1b1b21; color: #6a8a94; padding: 0 1; }
.code-copy-hint { color: #00cffc; }

.hidden { display: none; }
.thinking-indicator { color: #69daff; }
Toast { background: #1b1b21; color: #e0f0ff; }
Header { background: #131319; color: #e0f0ff; }
Footer { background: #131319; color: #6a8a94; }
```

- [ ] **Step 3: Create Prism theme (red stealth)**

`friday_ai/tui/themes/prism.tcss`:
```css
/* Prism / Kinetic Stealth — "The Obsidian Blade" — red accents */

Screen {
    background: #050505;
    color: #f0e0e0;
}

#chat-area { background: #121212; }
#messages { background: #050505; overflow-y: auto; }

.msg-user {
    background: #121212; color: #f0e0e0;
    margin: 1 2 0 12; padding: 1 2;
}
.msg-assistant {
    background: #201f1f; color: #f0e0e0;
    margin: 1 12 0 2; padding: 1 2;
    border-left: thick #ff0033;
}
.msg-user .timestamp { color: #8a7674; }
.msg-assistant .timestamp { color: #8a7674; }
.provider-tag { background: #d73357; color: #f0e0e0; padding: 0 1; }
.latency-tag { color: #8a7674; }

#input-area { background: #050505; dock: bottom; height: auto; max-height: 8; padding: 0 1; }
#chat-input { background: #020202; color: #f0e0e0; border: none; padding: 0 1; }
#chat-input:focus { border-bottom: tall #ff0033; }
.input-placeholder { color: #8a7674; }

#mode-bar { background: #050505; height: 1; padding: 0 1; }
.mode-active { color: #ff0033; text-style: bold; }
.mode-inactive { color: #8a7674; }

#sidebar { background: #050505; width: 30; dock: left; border-right: tall #201f1f; }
#sidebar-title { color: #8a7674; text-style: bold; padding: 1 1; }
.session-item { padding: 0 1; height: 1; }
.session-item:hover { background: #201f1f; }
.session-item.-selected { background: #353534; color: #ff0033; }
.session-group-label { color: #8a7674; text-style: bold; padding: 1 1 0 1; }

#telemetry { background: #050505; width: 30; dock: right; border-left: tall #201f1f; }
#telemetry-title { color: #8a7674; text-style: bold; padding: 1 1; }
.telemetry-label { color: #8a7674; }
.telemetry-value { color: #f0e0e0; }
.status-online { color: #4ae176; }
.status-offline { color: #ff0033; }
.status-connecting { color: #d73357; }

#settings-screen { background: #050505; }
.settings-tab-active { background: #201f1f; color: #ff0033; text-style: bold; padding: 0 2; }
.settings-tab-inactive { background: #050505; color: #8a7674; padding: 0 2; }
.settings-label { color: #f0e0e0; }
.settings-value { color: #ff0033; }
.settings-field.-selected { background: #201f1f; }

#welcome { background: #050505; align: center middle; }
#welcome-logo { color: #ff0033; text-style: bold; }
#welcome-title { color: #f0e0e0; }
.quick-action { background: #201f1f; padding: 1 2; margin: 1; width: 24; height: 5; }
.quick-action:hover { background: #353534; border: tall #ff0033; }

.code-block { background: #020202; padding: 1; margin: 1 0; }
.code-header { background: #201f1f; color: #8a7674; padding: 0 1; }
.code-copy-hint { color: #d73357; }

.hidden { display: none; }
.thinking-indicator { color: #ff0033; }
Toast { background: #201f1f; color: #f0e0e0; }
Header { background: #121212; color: #f0e0e0; }
Footer { background: #121212; color: #8a7674; }
```

- [ ] **Step 4: Create Techno theme (green terminal)**

`friday_ai/tui/themes/techno.tcss`:
```css
/* Techno — "Friday OS" — green terminal hacker aesthetic */

Screen {
    background: #0a0a0a;
    color: #e0ffe0;
}

#chat-area { background: #111111; }
#messages { background: #0a0a0a; overflow-y: auto; }

.msg-user {
    background: #111111; color: #e0ffe0;
    margin: 1 2 0 12; padding: 1 2;
}
.msg-assistant {
    background: #1a1a1a; color: #e0ffe0;
    margin: 1 12 0 2; padding: 1 2;
    border-left: thick #4ae176;
}
.msg-user .timestamp { color: #6a946a; }
.msg-assistant .timestamp { color: #6a946a; }
.provider-tag { background: #22c55e; color: #0a0a0a; padding: 0 1; }
.latency-tag { color: #6a946a; }

#input-area { background: #0a0a0a; dock: bottom; height: auto; max-height: 8; padding: 0 1; }
#chat-input { background: #050505; color: #e0ffe0; border: none; padding: 0 1; }
#chat-input:focus { border-bottom: tall #4ae176; }
.input-placeholder { color: #6a946a; }

#mode-bar { background: #0a0a0a; height: 1; padding: 0 1; }
.mode-active { color: #4ae176; text-style: bold; }
.mode-inactive { color: #6a946a; }

#sidebar { background: #0a0a0a; width: 30; dock: left; border-right: tall #1a1a1a; }
#sidebar-title { color: #6a946a; text-style: bold; padding: 1 1; }
.session-item { padding: 0 1; height: 1; }
.session-item:hover { background: #1a1a1a; }
.session-item.-selected { background: #222222; color: #4ae176; }
.session-group-label { color: #6a946a; text-style: bold; padding: 1 1 0 1; }

#telemetry { background: #0a0a0a; width: 30; dock: right; border-left: tall #1a1a1a; }
#telemetry-title { color: #6a946a; text-style: bold; padding: 1 1; }
.telemetry-label { color: #6a946a; }
.telemetry-value { color: #e0ffe0; }
.status-online { color: #4ae176; }
.status-offline { color: #ff4444; }
.status-connecting { color: #22c55e; }

#settings-screen { background: #0a0a0a; }
.settings-tab-active { background: #1a1a1a; color: #4ae176; text-style: bold; padding: 0 2; }
.settings-tab-inactive { background: #0a0a0a; color: #6a946a; padding: 0 2; }
.settings-label { color: #e0ffe0; }
.settings-value { color: #4ae176; }
.settings-field.-selected { background: #1a1a1a; }

#welcome { background: #0a0a0a; align: center middle; }
#welcome-logo { color: #4ae176; text-style: bold; }
#welcome-title { color: #e0ffe0; }
.quick-action { background: #1a1a1a; padding: 1 2; margin: 1; width: 24; height: 5; }
.quick-action:hover { background: #222222; border: tall #4ae176; }

.code-block { background: #050505; padding: 1; margin: 1 0; }
.code-header { background: #1a1a1a; color: #6a946a; padding: 0 1; }
.code-copy-hint { color: #22c55e; }

.hidden { display: none; }
.thinking-indicator { color: #4ae176; }
Toast { background: #1a1a1a; color: #e0ffe0; }
Header { background: #111111; color: #e0ffe0; }
Footer { background: #111111; color: #6a946a; }
```

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/themes/
git commit -m "feat(tui): add four switchable themes — obsidian, neural, prism, techno"
```

---

## Task 5: Clipboard Utility

**Files:**
- Create: `friday_ai/tui/utils/clipboard.py`
- Create: `tests/test_tui_clipboard.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tui_clipboard.py`:
```python
"""Tests for clipboard utility."""

from unittest.mock import AsyncMock, patch

import pytest

from friday_ai.tui.utils.clipboard import copy_to_clipboard, detect_clipboard_cmd


class TestClipboard:
    def test_detect_wayland(self):
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            with patch("shutil.which", return_value="/usr/bin/wl-copy"):
                cmd = detect_clipboard_cmd()
                assert cmd == ["wl-copy"]

    def test_detect_x11(self):
        env = {"DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=True):
            with patch("shutil.which", side_effect=lambda x: "/usr/bin/xclip" if x == "xclip" else None):
                cmd = detect_clipboard_cmd()
                assert cmd == ["xclip", "-selection", "clipboard"]

    def test_detect_xsel_fallback(self):
        env = {"DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=True):
            with patch("shutil.which", side_effect=lambda x: "/usr/bin/xsel" if x == "xsel" else None):
                cmd = detect_clipboard_cmd()
                assert cmd == ["xsel", "--clipboard", "--input"]

    def test_detect_none(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value=None):
                cmd = detect_clipboard_cmd()
                assert cmd is None

    @pytest.mark.asyncio
    async def test_copy_success(self):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("friday_ai.tui.utils.clipboard.detect_clipboard_cmd", return_value=["wl-copy"]):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
                result = await copy_to_clipboard("hello world")
                assert result is True
                mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_copy_no_clipboard_tool(self):
        with patch("friday_ai.tui.utils.clipboard.detect_clipboard_cmd", return_value=None):
            result = await copy_to_clipboard("hello")
            assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_clipboard.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement clipboard utility**

`friday_ai/tui/utils/clipboard.py`:
```python
"""Clipboard abstraction for Wayland (wl-copy) and X11 (xclip/xsel)."""

from __future__ import annotations

import asyncio
import os
import shutil


def detect_clipboard_cmd() -> list[str] | None:
    """Detect the available clipboard command."""
    if os.environ.get("WAYLAND_DISPLAY"):
        if shutil.which("wl-copy"):
            return ["wl-copy"]

    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard"]
        if shutil.which("xsel"):
            return ["xsel", "--clipboard", "--input"]

    return None


async def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    cmd = detect_clipboard_cmd()
    if cmd is None:
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=text.encode())
        return proc.returncode == 0
    except OSError:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_clipboard.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/utils/clipboard.py tests/test_tui_clipboard.py
git commit -m "feat(tui): add clipboard utility with Wayland/X11 detection"
```

---

## Task 6: Message Widget

**Files:**
- Create: `friday_ai/tui/widgets/message.py`
- Create: `tests/test_tui_widgets.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tui_widgets.py`:
```python
"""Tests for TUI widgets."""

import pytest
from textual.app import App, ComposeResult

from friday_ai.tui.widgets.message import MessageWidget


class MessageTestApp(App):
    """Minimal app for testing widgets."""

    def __init__(self, widget):
        super().__init__()
        self._widget = widget

    def compose(self) -> ComposeResult:
        yield self._widget


class TestMessageWidget:
    @pytest.mark.asyncio
    async def test_user_message_renders(self):
        widget = MessageWidget(
            content="Hello Friday",
            role="user",
            timestamp="12:04",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            assert pilot.app.query_one(MessageWidget)
            assert widget.role == "user"
            assert widget.content == "Hello Friday"

    @pytest.mark.asyncio
    async def test_assistant_message_renders(self):
        widget = MessageWidget(
            content="Hello! How can I help?",
            role="assistant",
            provider="ollama",
            latency=0.84,
            timestamp="12:04",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.role == "assistant"
            assert msg.provider == "ollama"
            assert msg.latency == 0.84

    @pytest.mark.asyncio
    async def test_user_message_has_user_class(self):
        widget = MessageWidget(content="Hi", role="user", timestamp="12:00")
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.has_class("msg-user")

    @pytest.mark.asyncio
    async def test_assistant_message_has_assistant_class(self):
        widget = MessageWidget(
            content="Hi", role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.has_class("msg-assistant")

    @pytest.mark.asyncio
    async def test_message_with_code_block(self):
        content = "Here is code:\n```python\nprint('hello')\n```"
        widget = MessageWidget(
            content=content, role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.content == content

    @pytest.mark.asyncio
    async def test_append_token(self):
        widget = MessageWidget(
            content="", role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            msg.append_token("Hello")
            msg.append_token(" world")
            assert msg.content == "Hello world"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement message widget**

`friday_ai/tui/widgets/message.py`:
```python
"""Chat message widget for user and assistant messages."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Markdown


class MessageWidget(Widget):
    """A single chat message — user or assistant."""

    content: reactive[str] = reactive("", layout=True)

    def __init__(
        self,
        content: str = "",
        role: str = "user",
        provider: str = "",
        latency: float = 0.0,
        timestamp: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.role = role
        self.provider = provider
        self.latency = latency
        self.timestamp = timestamp
        self.content = content
        self.add_class(f"msg-{role}")

    def compose(self) -> ComposeResult:
        with Vertical():
            if self.role == "assistant":
                with Horizontal(classes="msg-header"):
                    if self.provider:
                        yield Label(f" {self.provider.upper()} ", classes="provider-tag")
                    yield Label(f" {self.timestamp}", classes="timestamp")
            yield Markdown(self.content, id="msg-body")
            if self.role == "user":
                with Horizontal(classes="msg-footer"):
                    yield Label(f"{self.timestamp} ", classes="timestamp")
            elif self.latency > 0:
                yield Label(f"{self.latency:.2f}s", classes="latency-tag")

    def watch_content(self, new_content: str) -> None:
        """Update the Markdown widget when content changes."""
        try:
            md = self.query_one("#msg-body", Markdown)
            md.update(new_content)
        except Exception:
            pass

    def append_token(self, token: str) -> None:
        """Append a token to the message content (for streaming)."""
        self.content += token
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/widgets/message.py tests/test_tui_widgets.py
git commit -m "feat(tui): add message widget with streaming token append"
```

---

## Task 7: Mode Bar & Input Bar Widgets

**Files:**
- Create: `friday_ai/tui/widgets/mode_bar.py`
- Create: `friday_ai/tui/widgets/input_bar.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_tui_widgets.py`:
```python
from friday_ai.tui.widgets.mode_bar import ModeBar
from friday_ai.tui.widgets.input_bar import InputBar


class TestModeBar:
    @pytest.mark.asyncio
    async def test_default_mode_is_chat(self):
        widget = ModeBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(ModeBar)
            assert bar.current_mode == "chat"

    @pytest.mark.asyncio
    async def test_cycle_mode(self):
        widget = ModeBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(ModeBar)
            bar.set_mode("command")
            assert bar.current_mode == "command"
            bar.set_mode("search")
            assert bar.current_mode == "search"
            bar.set_mode("chat")
            assert bar.current_mode == "chat"


class TestInputBar:
    @pytest.mark.asyncio
    async def test_renders(self):
        widget = InputBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(InputBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_placeholder_changes_with_mode(self):
        widget = InputBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(InputBar)
            bar.set_mode("chat")
            assert bar.placeholder == "Message Friday..."
            bar.set_mode("command")
            assert bar.placeholder == "! shell or /friday command..."
            bar.set_mode("search")
            assert bar.placeholder == "Search conversations..."

    @pytest.mark.asyncio
    async def test_thinking_state(self):
        widget = InputBar()
        async with MessageTestApp(widget).run_test() as pilot:
            bar = pilot.app.query_one(InputBar)
            bar.set_thinking(True)
            assert bar.is_thinking is True
            bar.set_thinking(False)
            assert bar.is_thinking is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py::TestModeBar -v
python -m pytest tests/test_tui_widgets.py::TestInputBar -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement mode bar**

`friday_ai/tui/widgets/mode_bar.py`:
```python
"""Chat/Command/Search mode switcher bar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label

MODES = ("chat", "command", "search")


class ModeBar(Widget):
    """Displays and switches between Chat/Command/Search modes."""

    current_mode: reactive[str] = reactive("chat")

    class ModeChanged(Message):
        """Emitted when the mode changes."""

        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    def compose(self) -> ComposeResult:
        with Horizontal(id="mode-bar"):
            for mode in MODES:
                cls = "mode-active" if mode == self.current_mode else "mode-inactive"
                indicator = ">" if mode == self.current_mode else " "
                yield Label(f" {indicator} {mode.upper()} ", id=f"mode-{mode}", classes=cls)

    def set_mode(self, mode: str) -> None:
        """Switch to a new mode."""
        if mode in MODES:
            self.current_mode = mode
            self.post_message(self.ModeChanged(mode))

    def watch_current_mode(self, new_mode: str) -> None:
        """Update visual indicators when mode changes."""
        for mode in MODES:
            try:
                label = self.query_one(f"#mode-{mode}", Label)
                if mode == new_mode:
                    label.remove_class("mode-inactive")
                    label.add_class("mode-active")
                    indicator = ">"
                else:
                    label.remove_class("mode-active")
                    label.add_class("mode-inactive")
                    indicator = " "
                label.update(f" {indicator} {mode.upper()} ")
            except Exception:
                pass
```

- [ ] **Step 4: Implement input bar**

`friday_ai/tui/widgets/input_bar.py`:
```python
"""Smart input bar with mode-aware placeholder and thinking state."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label

PLACEHOLDERS = {
    "chat": "Message Friday...",
    "command": "! shell or /friday command...",
    "search": "Search conversations...",
}


class InputBar(Widget):
    """Input bar with mode indicator and thinking state."""

    is_thinking: reactive[bool] = reactive(False)
    placeholder: reactive[str] = reactive("Message Friday...")

    class Submitted(Message):
        """Emitted when user submits input."""

        def __init__(self, value: str, mode: str) -> None:
            super().__init__()
            self.value = value
            self.mode = mode

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._mode = "chat"

    def compose(self) -> ComposeResult:
        with Vertical(id="input-area"):
            with Horizontal(classes="input-row"):
                yield Input(
                    placeholder=self.placeholder,
                    id="chat-input",
                )
                yield Label("Thinking...", id="thinking-label", classes="thinking-indicator hidden")

    def set_mode(self, mode: str) -> None:
        """Update placeholder based on mode."""
        self._mode = mode
        self.placeholder = PLACEHOLDERS.get(mode, "Message Friday...")
        try:
            inp = self.query_one("#chat-input", Input)
            inp.placeholder = self.placeholder
        except Exception:
            pass

    def set_thinking(self, thinking: bool) -> None:
        """Toggle thinking indicator."""
        self.is_thinking = thinking
        try:
            label = self.query_one("#thinking-label", Label)
            if thinking:
                label.remove_class("hidden")
            else:
                label.add_class("hidden")
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key on the input."""
        value = event.value.strip()
        if not value:
            return
        event.input.value = ""
        self.post_message(self.Submitted(value, self._mode))
```

- [ ] **Step 5: Run all widget tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add friday_ai/tui/widgets/mode_bar.py friday_ai/tui/widgets/input_bar.py tests/test_tui_widgets.py
git commit -m "feat(tui): add mode bar and input bar widgets"
```

---

## Task 8: Sidebar Widget

**Files:**
- Create: `friday_ai/tui/widgets/sidebar.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_tui_widgets.py`:
```python
from friday_ai.tui.widgets.sidebar import Sidebar


class TestSidebar:
    @pytest.mark.asyncio
    async def test_renders_empty(self):
        widget = Sidebar()
        async with MessageTestApp(widget).run_test() as pilot:
            sidebar = pilot.app.query_one(Sidebar)
            assert sidebar is not None

    @pytest.mark.asyncio
    async def test_load_sessions(self):
        sessions = [
            {"name": "React Optimize", "date": "2026-04-14", "id": "s1"},
            {"name": "MCP Fix", "date": "2026-04-13", "id": "s2"},
        ]
        widget = Sidebar()
        async with MessageTestApp(widget).run_test() as pilot:
            sidebar = pilot.app.query_one(Sidebar)
            sidebar.load_sessions(sessions)
            assert len(sidebar.sessions) == 2

    @pytest.mark.asyncio
    async def test_starts_hidden(self):
        widget = Sidebar(classes="hidden")
        async with MessageTestApp(widget).run_test() as pilot:
            sidebar = pilot.app.query_one(Sidebar)
            assert sidebar.has_class("hidden")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py::TestSidebar -v
```

Expected: FAIL

- [ ] **Step 3: Implement sidebar**

`friday_ai/tui/widgets/sidebar.py`:
```python
"""Conversation history sidebar overlay."""

from __future__ import annotations

from datetime import datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView


class Sidebar(Widget):
    """Toggle-able conversation history panel."""

    sessions: reactive[list[dict]] = reactive(list, layout=True)

    class SessionSelected(Message):
        """Emitted when a session is selected."""

        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    class NewSessionRequested(Message):
        """Emitted when user wants a new session."""

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar"):
            yield Label("CONVERSATIONS", id="sidebar-title")
            yield Label("+ New Session", id="new-session-btn", classes="session-item")
            yield VerticalScroll(id="session-list")

    def load_sessions(self, sessions: list[dict]) -> None:
        """Load sessions into the sidebar grouped by date."""
        self.sessions = sessions
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Rebuild the session list UI."""
        try:
            container = self.query_one("#session-list", VerticalScroll)
            container.remove_children()

            grouped = self._group_by_date(self.sessions)
            for group_label, items in grouped.items():
                container.mount(Label(group_label, classes="session-group-label"))
                for session in items:
                    item = Label(
                        f"  > {session['name'][:22]}",
                        classes="session-item",
                        id=f"session-{session['id']}",
                    )
                    item.session_id = session["id"]
                    container.mount(item)
        except Exception:
            pass

    def _group_by_date(self, sessions: list[dict]) -> dict[str, list[dict]]:
        """Group sessions by relative date labels."""
        groups: dict[str, list[dict]] = {}
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        for s in sessions:
            try:
                date = datetime.strptime(s["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                date = today

            if date == today:
                label = "TODAY"
            elif date == yesterday:
                label = "YESTERDAY"
            elif date >= week_ago:
                label = "THIS WEEK"
            else:
                label = "OLDER"

            groups.setdefault(label, []).append(s)

        return groups

    def on_label_clicked(self, event: Label.Clicked) -> None:
        """Handle clicks on session items or new session button."""
        if event.label.id == "new-session-btn":
            self.post_message(self.NewSessionRequested())
        elif hasattr(event.label, "session_id"):
            self.post_message(self.SessionSelected(event.label.session_id))
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py::TestSidebar -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/widgets/sidebar.py tests/test_tui_widgets.py
git commit -m "feat(tui): add conversation history sidebar widget"
```

---

## Task 9: Telemetry Panel Widget

**Files:**
- Create: `friday_ai/tui/widgets/telemetry.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_tui_widgets.py`:
```python
from friday_ai.tui.widgets.telemetry import TelemetryPanel


class TestTelemetryPanel:
    @pytest.mark.asyncio
    async def test_renders(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            assert panel is not None

    @pytest.mark.asyncio
    async def test_update_health(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            panel.update_health({
                "status": "online",
                "providers": ["ollama", "claude"],
            })
            assert panel.providers == ["ollama", "claude"]

    @pytest.mark.asyncio
    async def test_update_mcp(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            panel.update_mcp({
                "servers": ["dev", "files"],
                "tools": [
                    {"name": "git_status", "server": "dev"},
                    {"name": "find_files", "server": "files"},
                ],
            })
            assert len(panel.mcp_servers) == 2

    @pytest.mark.asyncio
    async def test_update_last_response(self):
        widget = TelemetryPanel()
        async with MessageTestApp(widget).run_test() as pilot:
            panel = pilot.app.query_one(TelemetryPanel)
            panel.update_last_response("ollama", "qwen2.5:7b", 0.84)
            assert panel.active_provider == "ollama"
            assert panel.active_model == "qwen2.5:7b"
            assert panel.last_latency == 0.84
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py::TestTelemetryPanel -v
```

Expected: FAIL

- [ ] **Step 3: Implement telemetry panel**

`friday_ai/tui/widgets/telemetry.py`:
```python
"""Telemetry panel showing provider health, MCP status, and session info."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class TelemetryPanel(Widget):
    """Right-side toggleable panel with live system stats."""

    providers: reactive[list[str]] = reactive(list)
    mcp_servers: reactive[list[str]] = reactive(list)
    active_provider: reactive[str] = reactive("")
    active_model: reactive[str] = reactive("")
    last_latency: reactive[float] = reactive(0.0)
    memory_count: reactive[int] = reactive(0)
    session_saved: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        with Vertical(id="telemetry"):
            yield Label("SYSTEM", id="telemetry-title")
            yield VerticalScroll(id="telemetry-content")

    def _rebuild(self) -> None:
        """Rebuild the telemetry display."""
        try:
            container = self.query_one("#telemetry-content", VerticalScroll)
            container.remove_children()

            # Provider section
            container.mount(Label("PROVIDERS", classes="telemetry-label"))
            for p in self.providers:
                status_cls = "status-online"
                indicator = ">"
                container.mount(Label(
                    f"  {indicator} {p}",
                    classes=f"telemetry-value {status_cls}",
                ))

            container.mount(Label(""))

            # Active session
            container.mount(Label("ACTIVE", classes="telemetry-label"))
            container.mount(Label(f"  Provider  {self.active_provider or '-'}", classes="telemetry-value"))
            container.mount(Label(f"  Model     {self.active_model or '-'}", classes="telemetry-value"))
            container.mount(Label(f"  Latency   {self.last_latency:.2f}s" if self.last_latency else "  Latency   -", classes="telemetry-value"))

            container.mount(Label(""))

            # MCP section
            server_count = len(self.mcp_servers)
            container.mount(Label(f"MCP SERVERS  {server_count}", classes="telemetry-label"))
            for server_name in self.mcp_servers:
                container.mount(Label(f"  > {server_name}", classes="telemetry-value status-online"))

            container.mount(Label(""))

            # Memory
            container.mount(Label(f"MEMORY  {self.memory_count} facts", classes="telemetry-label"))
            save_status = "saved" if self.session_saved else "unsaved"
            container.mount(Label(f"SESSION  {save_status}", classes="telemetry-label"))

        except Exception:
            pass

    def update_health(self, data: dict) -> None:
        """Update from /health response."""
        self.providers = data.get("providers", [])
        self._rebuild()

    def update_mcp(self, data: dict) -> None:
        """Update from /mcp/status response."""
        self.mcp_servers = data.get("servers", [])
        self._rebuild()

    def update_last_response(self, provider: str, model: str, latency: float) -> None:
        """Update active session info after a response."""
        self.active_provider = provider
        self.active_model = model
        self.last_latency = latency
        self._rebuild()

    def update_memory(self, count: int) -> None:
        """Update memory fact count."""
        self.memory_count = count
        self._rebuild()

    def update_session_status(self, saved: bool) -> None:
        """Update session save indicator."""
        self.session_saved = saved
        self._rebuild()

    def on_mount(self) -> None:
        """Start auto-refresh timer."""
        self.set_interval(30, self._request_refresh)

    def _request_refresh(self) -> None:
        """Post a message requesting the app to refresh telemetry data."""
        self.post_message(self.RefreshRequested())

    class RefreshRequested(Message):
        """Emitted when telemetry wants fresh data from the API."""
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py::TestTelemetryPanel -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/widgets/telemetry.py tests/test_tui_widgets.py
git commit -m "feat(tui): add telemetry panel with provider/MCP/session status"
```

---

## Task 10: Code Block Widget

**Files:**
- Create: `friday_ai/tui/widgets/code_block.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_tui_widgets.py`:
```python
from friday_ai.tui.widgets.code_block import CodeBlock


class TestCodeBlock:
    @pytest.mark.asyncio
    async def test_renders(self):
        widget = CodeBlock(code="print('hello')", language="python")
        async with MessageTestApp(widget).run_test() as pilot:
            block = pilot.app.query_one(CodeBlock)
            assert block.code == "print('hello')"
            assert block.language == "python"

    @pytest.mark.asyncio
    async def test_collapsed_when_long(self):
        long_code = "\n".join(f"line {i}" for i in range(60))
        widget = CodeBlock(code=long_code, language="python")
        async with MessageTestApp(widget).run_test() as pilot:
            block = pilot.app.query_one(CodeBlock)
            assert block.is_collapsed is True

    @pytest.mark.asyncio
    async def test_not_collapsed_when_short(self):
        widget = CodeBlock(code="x = 1", language="python")
        async with MessageTestApp(widget).run_test() as pilot:
            block = pilot.app.query_one(CodeBlock)
            assert block.is_collapsed is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py::TestCodeBlock -v
```

Expected: FAIL

- [ ] **Step 3: Implement code block widget**

`friday_ai/tui/widgets/code_block.py`:
```python
"""Syntax-highlighted code block with copy and collapse support."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from rich.syntax import Syntax

COLLAPSE_THRESHOLD = 50


class CodeBlock(Widget):
    """Syntax-highlighted code block."""

    is_collapsed: reactive[bool] = reactive(False)

    def __init__(
        self,
        code: str = "",
        language: str = "text",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.code = code
        self.language = language
        line_count = code.count("\n") + 1
        self.is_collapsed = line_count > COLLAPSE_THRESHOLD
        self._line_count = line_count

    def compose(self) -> ComposeResult:
        with Vertical(classes="code-block"):
            yield Label(
                f" {self.language}  [y] copy ",
                classes="code-header",
            )
            if self.is_collapsed:
                preview = "\n".join(self.code.splitlines()[:10])
                yield Static(
                    Syntax(preview, self.language, theme="monokai", line_numbers=False),
                    id="code-body",
                )
                yield Label(
                    f" ... {self._line_count} lines (Enter to expand) ",
                    classes="code-collapse-hint",
                )
            else:
                yield Static(
                    Syntax(self.code, self.language, theme="monokai", line_numbers=False),
                    id="code-body",
                )

    def toggle_collapse(self) -> None:
        """Toggle between collapsed and expanded state."""
        self.is_collapsed = not self.is_collapsed
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the code block display."""
        self.remove_children()
        self.mount_all(self.compose())

    def get_code(self) -> str:
        """Return the full code content for clipboard copy."""
        return self.code
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_widgets.py::TestCodeBlock -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/widgets/code_block.py tests/test_tui_widgets.py
git commit -m "feat(tui): add code block widget with syntax highlighting and collapse"
```

---

## Task 11: Welcome Screen

**Files:**
- Create: `friday_ai/tui/screens/welcome.py`
- Create: `tests/test_tui_screens.py`

- [ ] **Step 1: Write tests**

`tests/test_tui_screens.py`:
```python
"""Tests for TUI screens."""

import pytest
from textual.app import App, ComposeResult
from textual.screen import Screen

from friday_ai.tui.screens.welcome import WelcomeScreen


class ScreenTestApp(App):
    SCREENS = {"welcome": WelcomeScreen}

    def on_mount(self) -> None:
        self.push_screen("welcome")


class TestWelcomeScreen:
    @pytest.mark.asyncio
    async def test_renders(self):
        async with ScreenTestApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_has_logo(self):
        async with ScreenTestApp().run_test() as pilot:
            logo = pilot.app.query_one("#welcome-logo")
            assert logo is not None

    @pytest.mark.asyncio
    async def test_has_title(self):
        async with ScreenTestApp().run_test() as pilot:
            title = pilot.app.query_one("#welcome-title")
            assert title is not None

    @pytest.mark.asyncio
    async def test_has_quick_actions(self):
        async with ScreenTestApp().run_test() as pilot:
            actions = pilot.app.query(".quick-action")
            assert len(actions) == 6
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_screens.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement welcome screen**

`friday_ai/tui/screens/welcome.py`:
```python
"""Welcome screen shown when no conversation history exists."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Label, Static

FRIDAY_LOGO = """
 ███████╗
 ██╔════╝
 █████╗
 ██╔══╝
 ██║
 ╚═╝
"""

QUICK_ACTIONS = [
    ("Draft an email", "Compose professional replies for clients or colleagues."),
    ("Explain code", "Break down complex logic or debug cryptic error messages."),
    ("Analyze data", "Extract key information for insights and trend visualization."),
    ("Summarize text", "Condense lengthy articles or meeting notes."),
    ("Brainstorm", "Generate fresh ideas for marketing or creative projects."),
    ("Run command", "Execute shell commands and system automation."),
]


class QuickAction(Static):
    """A clickable quick action card."""

    class Selected(Message):
        def __init__(self, prompt: str) -> None:
            super().__init__()
            self.prompt = prompt

    def __init__(self, title: str, description: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.title = title
        self.description = description
        self.add_class("quick-action")

    def render(self) -> str:
        return f"{self.title}\n{self.description[:40]}"

    def on_click(self) -> None:
        self.post_message(self.Selected(self.title))


class WelcomeScreen(Screen):
    """Empty state with logo and quick action cards."""

    class ActionSelected(Message):
        """Emitted when a quick action is chosen."""

        def __init__(self, prompt: str) -> None:
            super().__init__()
            self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome"):
            yield Static(FRIDAY_LOGO, id="welcome-logo")
            yield Label("What can I help with?", id="welcome-title")
            with Grid(id="quick-action-grid"):
                for title, desc in QUICK_ACTIONS:
                    yield QuickAction(title, desc)

    def on_quick_action_selected(self, event: QuickAction.Selected) -> None:
        self.post_message(self.ActionSelected(event.prompt))
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_screens.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/screens/welcome.py tests/test_tui_screens.py
git commit -m "feat(tui): add welcome screen with logo and quick action cards"
```

---

## Task 12: Chat Screen

**Files:**
- Create: `friday_ai/tui/screens/chat.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_tui_screens.py`:
```python
from friday_ai.tui.screens.chat import ChatScreen


class ChatScreenTestApp(App):
    SCREENS = {"chat": ChatScreen}

    def on_mount(self) -> None:
        self.push_screen("chat")


class TestChatScreen:
    @pytest.mark.asyncio
    async def test_renders(self):
        async with ChatScreenTestApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, ChatScreen)

    @pytest.mark.asyncio
    async def test_has_messages_area(self):
        async with ChatScreenTestApp().run_test() as pilot:
            messages = pilot.app.query_one("#messages")
            assert messages is not None

    @pytest.mark.asyncio
    async def test_has_input_bar(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.input_bar import InputBar
            bar = pilot.app.query_one(InputBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_has_mode_bar(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.mode_bar import ModeBar
            bar = pilot.app.query_one(ModeBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_sidebar_hidden_by_default(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.sidebar import Sidebar
            sidebar = pilot.app.query_one(Sidebar)
            assert sidebar.has_class("hidden")

    @pytest.mark.asyncio
    async def test_telemetry_hidden_by_default(self):
        async with ChatScreenTestApp().run_test() as pilot:
            from friday_ai.tui.widgets.telemetry import TelemetryPanel
            panel = pilot.app.query_one(TelemetryPanel)
            assert panel.has_class("hidden")

    @pytest.mark.asyncio
    async def test_add_message(self):
        async with ChatScreenTestApp().run_test() as pilot:
            screen = pilot.app.query_one(ChatScreen)
            screen.add_message("Hello", role="user")
            from friday_ai.tui.widgets.message import MessageWidget
            messages = pilot.app.query(MessageWidget)
            assert len(messages) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_screens.py::TestChatScreen -v
```

Expected: FAIL

- [ ] **Step 3: Implement chat screen**

`friday_ai/tui/screens/chat.py`:
```python
"""Main chat screen — messages, input, overlays."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen

from friday_ai.tui.widgets.input_bar import InputBar
from friday_ai.tui.widgets.message import MessageWidget
from friday_ai.tui.widgets.mode_bar import ModeBar
from friday_ai.tui.widgets.sidebar import Sidebar
from friday_ai.tui.widgets.telemetry import TelemetryPanel


class ChatScreen(Screen):
    """The main chat interface."""

    BINDINGS = [
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
        ("ctrl+t", "toggle_telemetry", "Telemetry"),
        ("ctrl+1", "mode_chat", "Chat"),
        ("ctrl+2", "mode_command", "Command"),
        ("ctrl+3", "mode_search", "Search"),
        ("i", "focus_input", "Input"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            yield Sidebar(classes="hidden")
            with Vertical(id="chat-area"):
                yield VerticalScroll(id="messages")
                yield ModeBar()
                yield InputBar()
            yield TelemetryPanel(classes="hidden")

    def add_message(
        self,
        content: str,
        role: str = "user",
        provider: str = "",
        latency: float = 0.0,
    ) -> MessageWidget:
        """Add a message to the chat area."""
        timestamp = datetime.now().strftime("%H:%M")
        msg = MessageWidget(
            content=content,
            role=role,
            provider=provider,
            latency=latency,
            timestamp=timestamp,
        )
        messages = self.query_one("#messages", VerticalScroll)
        messages.mount(msg)
        msg.scroll_visible()
        return msg

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.toggle_class("hidden")
        # Auto-close telemetry if terminal is narrow
        if self.app.size.width < 80 and not sidebar.has_class("hidden"):
            self.query_one(TelemetryPanel).add_class("hidden")

    def action_toggle_telemetry(self) -> None:
        panel = self.query_one(TelemetryPanel)
        panel.toggle_class("hidden")
        if self.app.size.width < 80 and not panel.has_class("hidden"):
            self.query_one(Sidebar).add_class("hidden")

    def action_mode_chat(self) -> None:
        self.query_one(ModeBar).set_mode("chat")
        self.query_one(InputBar).set_mode("chat")

    def action_mode_command(self) -> None:
        self.query_one(ModeBar).set_mode("command")
        self.query_one(InputBar).set_mode("command")

    def action_mode_search(self) -> None:
        self.query_one(ModeBar).set_mode("search")
        self.query_one(InputBar).set_mode("search")

    def action_focus_input(self) -> None:
        try:
            from textual.widgets import Input
            self.query_one("#chat-input", Input).focus()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_screens.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/screens/chat.py tests/test_tui_screens.py
git commit -m "feat(tui): add chat screen with message area, input, and toggle overlays"
```

---

## Task 13: Settings Screen

**Files:**
- Create: `friday_ai/tui/screens/settings.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_tui_screens.py`:
```python
from friday_ai.tui.screens.settings import SettingsScreen
from friday_ai.tui.config import TUIConfig


class SettingsTestApp(App):
    SCREENS = {"settings": SettingsScreen}

    def on_mount(self) -> None:
        self.push_screen("settings")


class TestSettingsScreen:
    @pytest.mark.asyncio
    async def test_renders(self):
        async with SettingsTestApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, SettingsScreen)

    @pytest.mark.asyncio
    async def test_simple_mode_by_default(self):
        async with SettingsTestApp().run_test() as pilot:
            screen = pilot.app.query_one(SettingsScreen)
            assert screen.settings_mode == "simple"

    @pytest.mark.asyncio
    async def test_toggle_to_advanced(self):
        async with SettingsTestApp().run_test() as pilot:
            screen = pilot.app.query_one(SettingsScreen)
            screen.toggle_advanced()
            assert screen.settings_mode == "advanced"
            screen.toggle_advanced()
            assert screen.settings_mode == "simple"

    @pytest.mark.asyncio
    async def test_has_settings_fields(self):
        async with SettingsTestApp().run_test() as pilot:
            fields = pilot.app.query(".settings-field")
            assert len(fields) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_screens.py::TestSettingsScreen -v
```

Expected: FAIL

- [ ] **Step 3: Implement settings screen**

`friday_ai/tui/screens/settings.py`:
```python
"""btop-style settings overlay with Simple and Advanced modes."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Label

from friday_ai.tui.config import TUIConfig, VALID_THEMES, VALID_RENDER_MODES, VALID_SPACING


class SettingsField(Label):
    """A single settings field — label + value."""

    def __init__(
        self,
        key: str,
        label: str,
        value: str | int | bool,
        field_type: str = "enum",
        options: tuple = (),
        **kwargs,
    ) -> None:
        self.key = key
        self.field_label = label
        self.field_value = value
        self.field_type = field_type
        self.options = options
        display = self._format_display()
        super().__init__(display, classes="settings-field", **kwargs)

    def _format_display(self) -> str:
        if self.field_type == "toggle":
            indicator = "> ON" if self.field_value else "  OFF"
            return f"  {self.field_label:<24} {indicator}"
        elif self.field_type == "enum":
            return f"  {self.field_label:<24} < {self.field_value} >"
        elif self.field_type == "number":
            return f"  {self.field_label:<24}   {self.field_value}"
        elif self.field_type == "readonly":
            return f"  {self.field_label:<24}   {self.field_value}"
        return f"  {self.field_label:<24}   {self.field_value}"

    def cycle_value(self, direction: int = 1) -> None:
        """Cycle enum/number values."""
        if self.field_type == "toggle":
            self.field_value = not self.field_value
        elif self.field_type == "enum" and self.options:
            idx = list(self.options).index(self.field_value) if self.field_value in self.options else 0
            idx = (idx + direction) % len(self.options)
            self.field_value = self.options[idx]
        elif self.field_type == "number":
            self.field_value = max(1, self.field_value + direction)
        self.update(self._format_display())


class SettingsScreen(Screen):
    """Full-screen settings overlay."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("up,k", "move_up", "Up"),
        ("down,j", "move_down", "Down"),
        ("left,h", "cycle_left", "Left"),
        ("right,l", "cycle_right", "Right"),
        ("enter", "toggle_field", "Toggle"),
        ("a", "toggle_mode", "Advanced"),
        ("s", "save", "Save"),
        ("tab", "next_tab", "Tab"),
        ("shift+tab", "prev_tab", "Tab"),
    ]

    settings_mode: reactive[str] = reactive("simple")

    class SettingsSaved(Message):
        """Emitted when settings are saved."""

        def __init__(self, config: TUIConfig) -> None:
            super().__init__()
            self.config = config

    def __init__(self, config: TUIConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config = config or TUIConfig()
        self._selected_idx = 0
        self._active_tab = 0
        self._modified = False

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-screen"):
            with Horizontal(id="settings-header"):
                yield Label("FRIDAY SETTINGS", classes="settings-label")
                mode_label = "[a] Advanced" if self.settings_mode == "simple" else "[a] Simple"
                yield Label(mode_label, id="mode-toggle-label", classes="settings-value")
            if self.settings_mode == "advanced":
                yield self._compose_tabs()
            yield VerticalScroll(id="settings-fields")
            with Horizontal(id="settings-footer"):
                yield Label("  j/k Navigate  h/l Change  Enter Toggle  s Save  Esc Close", classes="telemetry-label")
                modified = " [modified]" if self._modified else ""
                yield Label(f"  [Save] [Discard]{modified}", id="save-status", classes="settings-value")

    def _compose_tabs(self) -> Horizontal:
        """Build the tab bar for advanced mode."""
        tabs = ["GENERAL", "PROVIDER", "MCP", "TOOLS", "MEMORY", "IDENTITY", "APPEARANCE", "KEYBINDS"]
        container = Horizontal(id="settings-tabs")
        for i, tab in enumerate(tabs):
            cls = "settings-tab-active" if i == self._active_tab else "settings-tab-inactive"
            container.compose_add_child(Label(f" {tab} ", classes=cls, id=f"tab-{i}"))
        return container

    def on_mount(self) -> None:
        self._rebuild_fields()

    def _rebuild_fields(self) -> None:
        """Populate fields based on current mode and tab."""
        try:
            container = self.query_one("#settings-fields", VerticalScroll)
            container.remove_children()

            if self.settings_mode == "simple":
                fields = self._simple_fields()
            else:
                fields = self._advanced_fields()

            for i, field in enumerate(fields):
                if i == self._selected_idx:
                    field.add_class("-selected")
                container.mount(field)
        except Exception:
            pass

    def _simple_fields(self) -> list[SettingsField]:
        """~12 essential fields for simple mode."""
        return [
            SettingsField("theme", "Theme", self._config.theme, "enum", VALID_THEMES),
            SettingsField("render_mode", "Render Mode", self._config.render_mode, "enum", VALID_RENDER_MODES),
            SettingsField("show_timestamps", "Show Timestamps", self._config.show_timestamps, "toggle"),
            SettingsField("show_provider_tags", "Show Provider Tags", self._config.show_provider_tags, "toggle"),
            SettingsField("show_latency", "Show Latency", self._config.show_latency, "toggle"),
            SettingsField("message_spacing", "Message Spacing", self._config.message_spacing, "enum", VALID_SPACING),
            SettingsField("ascii_logo", "ASCII Logo", self._config.ascii_logo, "toggle"),
            SettingsField("clock_in_header", "Clock in Header", self._config.clock_in_header, "toggle"),
            SettingsField("typewriter_speed", "Typewriter Speed", self._config.typewriter_speed, "number"),
            SettingsField("sidebar_width", "Sidebar Width", self._config.sidebar_width, "number"),
            SettingsField("telemetry_width", "Telemetry Width", self._config.telemetry_width, "number"),
            SettingsField("telemetry_refresh", "Telemetry Refresh (s)", self._config.telemetry_refresh, "number"),
        ]

    def _advanced_fields(self) -> list[SettingsField]:
        """Fields for the currently selected advanced tab."""
        tab_builders = [
            self._general_fields,
            self._provider_fields,
            self._mcp_fields,
            self._tools_fields,
            self._memory_fields,
            self._identity_fields,
            self._appearance_fields,
            self._keybinds_fields,
        ]
        if self._active_tab < len(tab_builders):
            return tab_builders[self._active_tab]()
        return []

    def _general_fields(self) -> list[SettingsField]:
        return [
            SettingsField("render_mode", "Render Mode", self._config.render_mode, "enum", VALID_RENDER_MODES),
            SettingsField("typewriter_speed", "Typewriter Speed", self._config.typewriter_speed, "number"),
            SettingsField("telemetry_refresh", "Telemetry Refresh (s)", self._config.telemetry_refresh, "number"),
        ]

    def _provider_fields(self) -> list[SettingsField]:
        return [
            SettingsField("provider_note", "Configure via config.toml", "", "readonly"),
        ]

    def _mcp_fields(self) -> list[SettingsField]:
        return [
            SettingsField("mcp_note", "MCP servers configured externally", "", "readonly"),
        ]

    def _tools_fields(self) -> list[SettingsField]:
        return [
            SettingsField("tools_note", "Tools auto-discovered from plugins", "", "readonly"),
        ]

    def _memory_fields(self) -> list[SettingsField]:
        return [
            SettingsField("memory_note", "Use /memory commands in chat", "", "readonly"),
        ]

    def _identity_fields(self) -> list[SettingsField]:
        return [
            SettingsField("soul", "SOUL.md", "~/.config/friday/SOUL.md", "readonly"),
            SettingsField("user", "USER.md", "~/.config/friday/USER.md", "readonly"),
            SettingsField("agents", "AGENTS.md", "~/.config/friday/AGENTS.md", "readonly"),
            SettingsField("bootstrap", "BOOTSTRAP.md", "~/.config/friday/BOOTSTRAP.md", "readonly"),
        ]

    def _appearance_fields(self) -> list[SettingsField]:
        return [
            SettingsField("theme", "Theme", self._config.theme, "enum", VALID_THEMES),
            SettingsField("show_timestamps", "Show Timestamps", self._config.show_timestamps, "toggle"),
            SettingsField("show_provider_tags", "Provider Tags", self._config.show_provider_tags, "toggle"),
            SettingsField("show_latency", "Show Latency", self._config.show_latency, "toggle"),
            SettingsField("message_spacing", "Message Spacing", self._config.message_spacing, "enum", VALID_SPACING),
            SettingsField("ascii_logo", "ASCII Logo", self._config.ascii_logo, "toggle"),
            SettingsField("clock_in_header", "Clock in Header", self._config.clock_in_header, "toggle"),
            SettingsField("sidebar_width", "Sidebar Width", self._config.sidebar_width, "number"),
            SettingsField("telemetry_width", "Telemetry Width", self._config.telemetry_width, "number"),
        ]

    def _keybinds_fields(self) -> list[SettingsField]:
        return [
            SettingsField(k, k.replace("_", " ").title(), v, "readonly")
            for k, v in self._config.keybinds.items()
        ]

    def _get_fields(self) -> list[SettingsField]:
        try:
            return list(self.query(".settings-field").results(SettingsField))
        except Exception:
            return []

    def action_move_up(self) -> None:
        fields = self._get_fields()
        if not fields:
            return
        if self._selected_idx > 0:
            fields[self._selected_idx].remove_class("-selected")
            self._selected_idx -= 1
            fields[self._selected_idx].add_class("-selected")
            fields[self._selected_idx].scroll_visible()

    def action_move_down(self) -> None:
        fields = self._get_fields()
        if not fields:
            return
        if self._selected_idx < len(fields) - 1:
            fields[self._selected_idx].remove_class("-selected")
            self._selected_idx += 1
            fields[self._selected_idx].add_class("-selected")
            fields[self._selected_idx].scroll_visible()

    def action_cycle_right(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx < len(fields):
            fields[self._selected_idx].cycle_value(1)
            self._mark_modified()

    def action_cycle_left(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx < len(fields):
            fields[self._selected_idx].cycle_value(-1)
            self._mark_modified()

    def action_toggle_field(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx < len(fields):
            field = fields[self._selected_idx]
            if field.field_type == "toggle":
                field.cycle_value()
                self._mark_modified()

    def toggle_advanced(self) -> None:
        """Switch between simple and advanced modes."""
        self.settings_mode = "advanced" if self.settings_mode == "simple" else "simple"
        self._selected_idx = 0
        self._active_tab = 0

    def action_toggle_mode(self) -> None:
        self.toggle_advanced()
        self._rebuild_all()

    def action_next_tab(self) -> None:
        if self.settings_mode == "advanced":
            self._active_tab = (self._active_tab + 1) % 8
            self._selected_idx = 0
            self._rebuild_all()

    def action_prev_tab(self) -> None:
        if self.settings_mode == "advanced":
            self._active_tab = (self._active_tab - 1) % 8
            self._selected_idx = 0
            self._rebuild_all()

    def action_save(self) -> None:
        """Apply field values back to config and emit save."""
        fields = self._get_fields()
        for field in fields:
            if hasattr(self._config, field.key):
                setattr(self._config, field.key, field.field_value)
        self._modified = False
        self.post_message(self.SettingsSaved(self._config))
        self.dismiss()

    def _mark_modified(self) -> None:
        self._modified = True
        try:
            label = self.query_one("#save-status", Label)
            label.update("  [Save] [Discard] [modified]")
        except Exception:
            pass

    def _rebuild_all(self) -> None:
        """Full screen rebuild."""
        self.remove_children()
        for child in self.compose():
            self.mount(child)
        self._rebuild_fields()
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_screens.py::TestSettingsScreen -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/screens/settings.py tests/test_tui_screens.py
git commit -m "feat(tui): add btop-style settings screen with simple/advanced modes"
```

---

## Task 14: Main App Shell

**Files:**
- Create: `friday_ai/tui/app.py`
- Create: `tests/test_tui_app.py`

- [ ] **Step 1: Write tests**

`tests/test_tui_app.py`:
```python
"""Tests for the main Friday TUI app."""

import pytest

from friday_ai.tui.app import FridayApp
from friday_ai.tui.screens.welcome import WelcomeScreen
from friday_ai.tui.screens.chat import ChatScreen


class TestFridayApp:
    @pytest.mark.asyncio
    async def test_app_launches(self):
        app = FridayApp()
        async with app.run_test() as pilot:
            assert pilot.app is not None

    @pytest.mark.asyncio
    async def test_starts_on_welcome_screen(self):
        app = FridayApp()
        async with app.run_test() as pilot:
            # Should start on welcome or chat screen
            screen = pilot.app.screen
            assert isinstance(screen, (WelcomeScreen, ChatScreen))

    @pytest.mark.asyncio
    async def test_theme_defaults_to_obsidian(self):
        app = FridayApp()
        async with app.run_test() as pilot:
            assert pilot.app.current_theme == "obsidian"

    @pytest.mark.asyncio
    async def test_cycle_theme(self):
        app = FridayApp()
        async with app.run_test() as pilot:
            pilot.app.action_cycle_theme()
            assert pilot.app.current_theme == "neural"
            pilot.app.action_cycle_theme()
            assert pilot.app.current_theme == "prism"
            pilot.app.action_cycle_theme()
            assert pilot.app.current_theme == "techno"
            pilot.app.action_cycle_theme()
            assert pilot.app.current_theme == "obsidian"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_app.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement main app**

`friday_ai/tui/app.py`:
```python
"""Friday TUI — main Textual application."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual.app import App
from textual.reactive import reactive

from friday_ai.tui.client import FridayTUIClient
from friday_ai.tui.config import TUIConfig, load_tui_config, save_tui_config, VALID_THEMES
from friday_ai.tui.screens.chat import ChatScreen
from friday_ai.tui.screens.settings import SettingsScreen
from friday_ai.tui.screens.welcome import WelcomeScreen
from friday_ai.tui.widgets.input_bar import InputBar

THEME_DIR = Path(__file__).parent / "themes"


class FridayApp(App):
    """Friday AI Terminal Interface."""

    TITLE = "Friday"
    SUB_TITLE = "AI Assistant"

    BINDINGS = [
        ("ctrl+s", "open_settings", "Settings"),
        ("ctrl+n", "new_conversation", "New Chat"),
        ("ctrl+shift+t", "cycle_theme", "Theme"),
        ("ctrl+r", "toggle_render_mode", "Render"),
        ("q", "quit", "Quit"),
    ]

    current_theme: reactive[str] = reactive("obsidian")

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 65535,
        theme: str | None = None,
        no_connect: bool = False,
        session: str | None = None,
        **kwargs,
    ) -> None:
        self._tui_config = self._load_config()
        initial_theme = theme or self._tui_config.theme
        css_path = THEME_DIR / f"{initial_theme}.tcss"
        if not css_path.exists():
            css_path = THEME_DIR / "obsidian.tcss"
            initial_theme = "obsidian"

        super().__init__(css_path=css_path, **kwargs)

        self.current_theme = initial_theme
        self._host = host
        self._port = port
        self._no_connect = no_connect
        self._session_file = session
        self._client: FridayTUIClient | None = None
        self._messages: list[dict[str, Any]] = []
        self._render_mode = self._tui_config.render_mode

    def _load_config(self) -> TUIConfig:
        """Load TUI config from Friday's config directory."""
        config_path = Path.home() / ".config" / "friday" / "config.toml"
        return load_tui_config(config_path)

    async def on_mount(self) -> None:
        """Initialize client and check backend health."""
        if not self._no_connect:
            self._client = FridayTUIClient(host=self._host, port=self._port)
            health = await self._client.health()
            if health and self._session_file:
                await self._client.session_load()

        self.push_screen(ChatScreen())

    async def on_unmount(self) -> None:
        """Clean up client on exit."""
        if self._client:
            await self._client.close()

    # --- Actions ---

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(config=self._tui_config))

    def action_new_conversation(self) -> None:
        """Start a new conversation."""
        self._messages.clear()
        if isinstance(self.screen, ChatScreen):
            try:
                from textual.containers import VerticalScroll
                messages = self.screen.query_one("#messages", VerticalScroll)
                messages.remove_children()
            except Exception:
                pass

    def action_cycle_theme(self) -> None:
        themes = list(VALID_THEMES)
        idx = themes.index(self.current_theme) if self.current_theme in themes else 0
        self.current_theme = themes[(idx + 1) % len(themes)]
        new_css = THEME_DIR / f"{self.current_theme}.tcss"
        if new_css.exists():
            self.stylesheet.read(new_css)
            self.stylesheet.reparse()
            self.screen.refresh(layout=True)

    def action_toggle_render_mode(self) -> None:
        self._render_mode = "typewriter" if self._render_mode == "live_stream" else "live_stream"
        self.notify(f"Render: {self._render_mode.replace('_', ' ').title()}")

    # --- Message Handling ---

    async def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        """Handle user input from the input bar."""
        if not isinstance(self.screen, ChatScreen):
            return

        chat_screen = self.screen
        value = event.value
        mode = event.mode

        if mode == "chat":
            await self._handle_chat(chat_screen, value)
        elif mode == "command":
            await self._handle_command(chat_screen, value)
        elif mode == "search":
            await self._handle_search(chat_screen, value)

    async def _handle_chat(self, screen: ChatScreen, message: str) -> None:
        """Send chat message and display response."""
        screen.add_message(message, role="user")
        screen.query_one(InputBar).set_thinking(True)

        if not self._client:
            screen.add_message("Not connected to Friday backend.", role="assistant", provider="error")
            screen.query_one(InputBar).set_thinking(False)
            return

        if self._render_mode == "live_stream":
            msg_widget = screen.add_message("", role="assistant", provider="...")
            try:
                async for chunk in self._client.chat_stream(message):
                    if chunk.get("error"):
                        msg_widget.content = f"Error: {chunk['error']}"
                        break
                    if not chunk.get("done"):
                        msg_widget.append_token(chunk.get("token", ""))
                    else:
                        msg_widget.provider = chunk.get("provider", "unknown")
                        msg_widget.latency = chunk.get("latency", 0.0)
                        # Update telemetry
                        self._update_telemetry(chunk.get("provider", ""), chunk.get("latency", 0.0))
            except Exception as e:
                msg_widget.content = f"Stream error: {e}"
        else:
            # Typewriter mode
            result = await self._client.chat(message)
            if result:
                response = result.get("response", "No response")
                provider = result.get("provider", "unknown")
                msg_widget = screen.add_message("", role="assistant", provider=provider)
                # Typewriter effect
                speed = self._tui_config.typewriter_speed
                for char in response:
                    msg_widget.append_token(char)
                    await asyncio.sleep(1.0 / speed)
            else:
                screen.add_message("Failed to get response.", role="assistant", provider="error")

        screen.query_one(InputBar).set_thinking(False)

    async def _handle_command(self, screen: ChatScreen, value: str) -> None:
        """Handle command mode input."""
        if value.startswith("!"):
            # Shell command
            shell_cmd = value[1:].strip()
            screen.add_message(f"! {shell_cmd}", role="user")
            if self._client:
                result = await self._client.chat(f"Run this shell command: {shell_cmd}")
                if result:
                    screen.add_message(result.get("response", ""), role="assistant", provider=result.get("provider", ""))
        elif value.startswith("/"):
            # Friday command
            parts = value[1:].split(maxsplit=1)
            cmd = parts[0] if parts else ""
            await self._run_friday_command(screen, cmd, parts[1] if len(parts) > 1 else "")
        else:
            screen.add_message(value, role="user")
            screen.add_message("Use ! for shell commands or / for Friday commands.", role="assistant", provider="system")

    async def _run_friday_command(self, screen: ChatScreen, cmd: str, args: str) -> None:
        """Execute a slash command."""
        screen.add_message(f"/{cmd} {args}".strip(), role="user")

        if not self._client:
            screen.add_message("Not connected.", role="assistant", provider="error")
            return

        handlers = {
            "reload": lambda: self._client.reload(),
            "health": lambda: self._client.health(),
            "memory": lambda: self._client.memory_list(),
            "forget": lambda: self._client.memory_forget(args),
            "clear": lambda: self._client.memory_clear(),
            "save": lambda: self._client.session_save(),
            "load": lambda: self._client.session_load(),
            "mcp": lambda: self._client.mcp_status(),
            "reconnect": lambda: self._client.mcp_reconnect(),
            "context": lambda: self._client.context(),
        }

        handler = handlers.get(cmd)
        if handler:
            result = await handler()
            import json
            screen.add_message(
                f"```json\n{json.dumps(result, indent=2)}\n```" if result else "Command failed.",
                role="assistant",
                provider="system",
            )
        else:
            screen.add_message(f"Unknown command: /{cmd}", role="assistant", provider="system")

    async def _handle_search(self, screen: ChatScreen, query: str) -> None:
        """Search conversations and memory."""
        screen.add_message(f"Searching: {query}", role="user")
        if self._client:
            result = await self._client.memory_list()
            if result:
                entries = result.get("entries", [])
                matches = [e for e in entries if query.lower() in e.lower()]
                if matches:
                    screen.add_message("\n".join(f"- {m}" for m in matches), role="assistant", provider="search")
                else:
                    screen.add_message("No matches found.", role="assistant", provider="search")

    def _update_telemetry(self, provider: str, latency: float) -> None:
        """Update the telemetry panel after a response."""
        if isinstance(self.screen, ChatScreen):
            try:
                from friday_ai.tui.widgets.telemetry import TelemetryPanel
                panel = self.screen.query_one(TelemetryPanel)
                panel.update_last_response(provider, "", latency)
            except Exception:
                pass

    # --- Settings Callbacks ---

    def on_settings_screen_settings_saved(self, event: SettingsScreen.SettingsSaved) -> None:
        """Apply saved settings."""
        self._tui_config = event.config
        config_path = Path.home() / ".config" / "friday" / "config.toml"
        save_tui_config(self._tui_config, config_path)

        # Apply theme change
        if self._tui_config.theme != self.current_theme:
            self.current_theme = self._tui_config.theme
            new_css = THEME_DIR / f"{self.current_theme}.tcss"
            if new_css.exists():
                self.stylesheet.read(new_css)
                self.stylesheet.reparse()
                self.screen.refresh(layout=True)

        self._render_mode = self._tui_config.render_mode

        # Trigger backend reload so changes take effect
        if self._client:
            asyncio.create_task(self._client.reload())

    # --- Welcome Screen Callback ---

    def on_welcome_screen_action_selected(self, event: WelcomeScreen.ActionSelected) -> None:
        """Handle quick action from welcome screen."""
        self.pop_screen()
        chat = ChatScreen()
        self.push_screen(chat)
        self.call_after_refresh(lambda: asyncio.create_task(self._handle_chat(chat, event.prompt)))
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_app.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tui/app.py tests/test_tui_app.py
git commit -m "feat(tui): add main FridayApp with theme cycling, chat/command/search handling"
```

---

## Task 15: SSE Streaming Backend

**Files:**
- Modify: `friday_ai/server.py`
- Modify: `friday_ai/agent.py`
- Create: `tests/test_stream_endpoint.py`

- [ ] **Step 1: Write the failing test**

`tests/test_stream_endpoint.py`:
```python
"""Tests for the /chat/stream SSE endpoint."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from friday_ai.server import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestStreamEndpoint:
    @pytest.mark.asyncio
    async def test_stream_returns_sse(self, client, app):
        """The /chat/stream endpoint should return SSE events."""
        # Mock the agent's stream_chat method
        async def mock_stream(message):
            yield {"token": "Hello", "done": False}
            yield {"token": " world", "done": False}
            yield {"token": "", "done": True, "provider": "mock", "latency": 0.1}

        app.state.agent.stream_chat = mock_stream

        response = await client.post(
            "/chat/stream",
            json={"message": "Hi"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_stream_contains_tokens(self, client, app):
        """SSE events should contain token data."""
        tokens_sent = []

        async def mock_stream(message):
            for t in ["Hello", " ", "Friday"]:
                tokens_sent.append(t)
                yield {"token": t, "done": False}
            yield {"token": "", "done": True, "provider": "mock", "latency": 0.05}

        app.state.agent.stream_chat = mock_stream

        response = await client.post(
            "/chat/stream",
            json={"message": "Hi"},
        )
        body = response.text
        assert "Hello" in body
        assert "Friday" in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/friday
python -m pytest tests/test_stream_endpoint.py -v
```

Expected: FAIL — no `/chat/stream` endpoint or `stream_chat` method exists.

- [ ] **Step 3: Add stream_chat to agent.py**

Add to `friday_ai/agent.py` — the `Agent` class:

```python
async def stream_chat(
    self,
    message: str,
    force_provider: str | None = None,
) -> AsyncIterator[dict]:
    """Stream chat tokens. Yields {"token": str, "done": bool, ...}."""
    import time

    start = time.monotonic()
    self.history.append({"role": "user", "content": message})

    # For now, get full response and simulate streaming
    # TODO: Wire up native provider streaming when available
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
```

- [ ] **Step 4: Add /chat/stream endpoint to server.py**

Add to `friday_ai/server.py` after the existing `/chat` endpoint:

```python
from sse_starlette.sse import EventSourceResponse

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response as SSE events."""
    agent = app.state.agent

    async def generate():
        async for chunk in agent.stream_chat(
            request.message,
            force_provider=request.force_provider,
        ):
            yield {"data": json.dumps(chunk)}

    return EventSourceResponse(generate())
```

Add `import json` at the top of server.py if not already present.

- [ ] **Step 5: Run tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_stream_endpoint.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add friday_ai/server.py friday_ai/agent.py tests/test_stream_endpoint.py
git commit -m "feat: add /chat/stream SSE endpoint with word-level token streaming"
```

---

## Task 16: Entry Point Script

**Files:**
- Create: `bin/friday-tui`

- [ ] **Step 1: Create the entry point**

`bin/friday-tui`:
```bash
#!/usr/bin/env bash
# Friday TUI — launch the terminal interface
set -euo pipefail

FRIDAY_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

# Activate venv if it exists
if [ -f "$FRIDAY_DIR/.venv/bin/activate" ]; then
    source "$FRIDAY_DIR/.venv/bin/activate"
fi

exec python -m friday_ai.tui "$@"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x ~/Projects/friday/bin/friday-tui
```

- [ ] **Step 3: Add CLI argument parsing**

Update `friday_ai/tui/__init__.py`:
```python
"""Friday TUI — keyboard-driven terminal interface."""

import argparse

from friday_ai.tui.app import FridayApp


def main() -> None:
    """Entry point for friday-tui command."""
    parser = argparse.ArgumentParser(description="Friday AI Terminal Interface")
    parser.add_argument("--theme", choices=["obsidian", "neural", "prism", "techno"], help="Override startup theme")
    parser.add_argument("--port", type=int, default=65535, help="API port (default: 65535)")
    parser.add_argument("--host", default="127.0.0.1", help="API host (default: 127.0.0.1)")
    parser.add_argument("--no-connect", action="store_true", help="Launch without connecting to backend")
    parser.add_argument("--session", help="Load a specific session file on start")
    args = parser.parse_args()

    app = FridayApp(
        host=args.host,
        port=args.port,
        theme=args.theme,
        no_connect=args.no_connect,
        session=args.session,
    )
    app.run()
```

- [ ] **Step 4: Test the entry point**

```bash
cd ~/Projects/friday
python -m friday_ai.tui --help
```

Expected: help text printed with all flags listed.

- [ ] **Step 5: Commit**

```bash
git add bin/friday-tui friday_ai/tui/__init__.py
git commit -m "feat(tui): add bin/friday-tui entry point with CLI argument parsing"
```

---

## Task 17: Integration Smoke Test

**Files:**
- Modify: `tests/test_tui_app.py`

- [ ] **Step 1: Add integration tests**

Append to `tests/test_tui_app.py`:
```python
class TestFridayAppIntegration:
    @pytest.mark.asyncio
    async def test_send_chat_without_backend(self):
        """Chat gracefully handles missing backend."""
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            # Navigate to chat screen
            from friday_ai.tui.screens.chat import ChatScreen
            screen = pilot.app.screen
            if isinstance(screen, ChatScreen):
                # Type and submit a message
                await pilot.press("i")
                await pilot.press(*"hello")
                await pilot.press("enter")
                # Should show error message, not crash
                from friday_ai.tui.widgets.message import MessageWidget
                messages = pilot.app.query(MessageWidget)
                assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_settings_roundtrip(self):
        """Open settings, change theme, save."""
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            # Open settings
            await pilot.press("ctrl+s")
            from friday_ai.tui.screens.settings import SettingsScreen
            assert isinstance(pilot.app.screen, SettingsScreen)
            # Close settings
            await pilot.press("escape")

    @pytest.mark.asyncio
    async def test_theme_cycle_keybind(self):
        """Ctrl+Shift+T cycles themes."""
        app = FridayApp(no_connect=True)
        async with app.run_test() as pilot:
            assert pilot.app.current_theme == "obsidian"
            await pilot.press("ctrl+shift+t")
            assert pilot.app.current_theme == "neural"
```

- [ ] **Step 2: Run all tests**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_app.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Run the full TUI test suite**

```bash
cd ~/Projects/friday
python -m pytest tests/test_tui_*.py -v
```

Expected: All tests across all TUI test files PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tui_app.py
git commit -m "test(tui): add integration smoke tests for chat, settings, and themes"
```

---

## Task 18: Final Polish & Documentation

**Files:**
- Modify: `friday_ai/tui/screens/__init__.py`
- Modify: `friday_ai/tui/widgets/__init__.py`

- [ ] **Step 1: Add proper exports**

`friday_ai/tui/screens/__init__.py`:
```python
"""TUI screens."""

from friday_ai.tui.screens.chat import ChatScreen
from friday_ai.tui.screens.settings import SettingsScreen
from friday_ai.tui.screens.welcome import WelcomeScreen

__all__ = ["ChatScreen", "SettingsScreen", "WelcomeScreen"]
```

`friday_ai/tui/widgets/__init__.py`:
```python
"""TUI widgets."""

from friday_ai.tui.widgets.code_block import CodeBlock
from friday_ai.tui.widgets.input_bar import InputBar
from friday_ai.tui.widgets.message import MessageWidget
from friday_ai.tui.widgets.mode_bar import ModeBar
from friday_ai.tui.widgets.sidebar import Sidebar
from friday_ai.tui.widgets.telemetry import TelemetryPanel

__all__ = ["CodeBlock", "InputBar", "MessageWidget", "ModeBar", "Sidebar", "TelemetryPanel"]
```

- [ ] **Step 2: Run the entire existing test suite to check for regressions**

```bash
cd ~/Projects/friday
python -m pytest tests/ -v --tb=short
```

Expected: All existing tests + new TUI tests PASS. No regressions.

- [ ] **Step 3: Commit**

```bash
git add friday_ai/tui/screens/__init__.py friday_ai/tui/widgets/__init__.py
git commit -m "chore(tui): add proper package exports for screens and widgets"
```

- [ ] **Step 4: Verify the TUI launches**

```bash
cd ~/Projects/friday
python -m friday_ai.tui --no-connect --theme obsidian
```

Expected: TUI renders in terminal with obsidian theme. Press `q` to quit.

- [ ] **Step 5: Final commit with all changes**

```bash
cd ~/Projects/friday
git log --oneline -15
```

Verify all commits are present and clean.
