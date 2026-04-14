# Friday TUI Design Spec

## Overview

A keyboard-driven Terminal UI for Friday AI, built with Python Textual. Runs in a floating kitty window via Super+F. Talks to the Friday backend at `http://127.0.0.1:65535`.

Design language inspired by four web UI themes from `stitch.zip` — adapted for terminal constraints. Core philosophy: ultra-dark backgrounds, tonal layering instead of borders, accent colors per theme, JetBrains Mono for technical content.

## Architecture

**Approach:** Pure Textual (Approach A). TUI lives inside `friday_ai/tui/` to share types, config, and models with the backend. Minimal new dependencies (`textual`, `sse-starlette`).

### File Structure

```
friday_ai/tui/
├── __init__.py
├── app.py              # FridayApp — main Textual app, keybindings, mode switching
├── client.py           # Async HTTP client wrapping Friday API + SSE streaming
├── config.py           # TUI-specific config (theme, render mode, keybinds)
│
├── screens/
│   ├── __init__.py
│   ├── chat.py         # Main chat screen (default)
│   ├── settings.py     # btop-style full-screen settings overlay
│   └── welcome.py      # Empty state / "What can I help with?" quick actions
│
├── widgets/
│   ├── __init__.py
│   ├── message.py      # Chat message widget (user/assistant, provider tag, timestamp)
│   ├── input_bar.py    # Smart input — detects !/slash/bare text, mode indicator
│   ├── sidebar.py      # Conversation history overlay (toggle)
│   ├── telemetry.py    # Provider health, latency, MCP status panel (toggle)
│   ├── mode_bar.py     # Chat/Command/Search mode switcher
│   └── code_block.py   # Syntax-highlighted code with copy-to-clipboard
│
├── themes/
│   ├── obsidian.tcss   # Purple — default
│   ├── neural.tcss     # Cyan HUD
│   ├── prism.tcss      # Red stealth
│   └── techno.tcss     # Green terminal
│
└── utils/
    ├── __init__.py
    ├── markdown.py     # Markdown-to-Rich rendering helpers
    └── clipboard.py    # wl-copy / xclip abstraction

bin/friday-tui             # Entry point shell script
```

## Screens & Navigation

### Three Screens

1. **WelcomeScreen** — shown on launch when no conversation history exists. ASCII "F" logo, "What can I help with?" prompt, 6 quick-action cards in a grid. Clicking/selecting a card transitions to ChatScreen with that prompt.

2. **ChatScreen** — the main interface. Contains:
   - Scrollable message list (vertical, fills available space)
   - Input bar (bottom-docked)
   - Mode bar (above input)
   - Sidebar overlay (left, hidden by default)
   - Telemetry panel overlay (right, hidden by default)

3. **SettingsScreen** — full-screen overlay with two modes (Simple/Advanced). Esc returns to previous screen.

### Keybindings

| Keybind | Action |
|---------|--------|
| `Ctrl+B` | Toggle sidebar overlay |
| `Ctrl+T` | Toggle telemetry panel |
| `Ctrl+S` | Open settings screen |
| `Ctrl+N` | New conversation |
| `Ctrl+P` | Fuzzy search conversations |
| `Ctrl+R` | Toggle render mode (Live/Typewriter) |
| `Ctrl+Shift+T` | Cycle theme |
| `Ctrl+1` | Chat mode |
| `Ctrl+2` | Command mode |
| `Ctrl+3` | Search mode |
| `Tab` | Cycle focus: input -> messages -> sidebar |
| `Esc` | Close any overlay / back to chat |
| `j/k` | Scroll messages (when message area focused) |
| `g/G` | Jump to top/bottom of messages |
| `y` | Copy focused code block to clipboard |
| `/` | Focus input in search mode |
| `i` | Focus input in chat mode (vim-style) |
| `a` | Toggle Simple/Advanced settings (when in settings) |

All keybinds are rebindable via the Keybinds tab in Advanced settings.

## Widget Details

### Message Widget

- **User messages:** right-aligned, minimal styling (surface background), text + timestamp
- **Assistant messages:** left-aligned, accent-colored left border, provider tag (colored chip), timestamp + response latency
- **Code blocks:** language label header, syntax highlighting via Rich, `[y]` hint for copy keybind, collapsible if over 50 lines
- **Markdown:** rendered inline — bold, links, lists, headers, inline code
- **Large responses:** messages over 200 lines collapsed with `[Show full response]` toggle

### Input Bar

- Mode indicator line above: `CHAT  COMMAND  SEARCH` with active mode highlighted
- Placeholder changes per mode:
  - Chat: `Message Friday...`
  - Command: `! shell or /friday command...`
  - Search: `Search conversations...`
- Typing/thinking indicator replaces send button while waiting: `Thinking...`
- Send with `Enter`, newline with `Shift+Enter`
- Empty submit ignored, rapid submits queued sequentially

### Mode Switcher

Three modes accessible via `Ctrl+1/2/3` or clicking the mode bar:

- **Chat** — bare text sent to `/chat` (or `/chat/stream`)
- **Command** — `!` prefix for shell execution (output shown inline), `/` prefix for Friday API commands (`/reload`, `/memory list`, `/mcp status`, etc.)
- **Search** — filters conversation history, searches memory via `/memory/list`

### Sidebar (Toggle Overlay, Left)

- Hidden by default, toggled with `Ctrl+B`
- Conversation list grouped by date: Today / Yesterday / This Week / Older
- Pinned conversations section at top
- `j/k` to navigate, `Enter` to load, `d` to delete, `p` to pin
- `Ctrl+P` opens fuzzy search across all conversations
- `+ New Session` action at top
- Width configurable in settings (default 30 chars)

### Telemetry Panel (Toggle Overlay, Right)

- Hidden by default, toggled with `Ctrl+T`
- Sections:
  - **Provider Status** — each provider with online/offline indicator, active provider highlighted
  - **Active Session** — current model, latency of last response, provider mode (fallback/race)
  - **MCP Servers** — each server with status + tool count
  - **Memory** — fact count, session save status
- Auto-refreshes every 30s (configurable), manual refresh with keybind
- Width configurable in settings (default 30 chars)

### Overlay Coexistence

Sidebar (left) and telemetry (right) can both be open simultaneously — the chat area shrinks to fill the remaining space between them. If terminal width is too narrow (< 80 cols), opening one auto-closes the other.

## Theme System

Four switchable themes, each a `.tcss` file. The app swaps stylesheets at runtime.

### Color Tokens

| Token | Obsidian | Neural | Prism | Techno |
|-------|----------|--------|-------|--------|
| `$bg` | `#0e0d15` | `#0e0e14` | `#050505` | `#0a0a0a` |
| `$surface` | `#13131b` | `#131319` | `#121212` | `#111111` |
| `$surface-high` | `#191922` | `#1b1b21` | `#201f1f` | `#1a1a1a` |
| `$surface-active` | `#252530` | `#25252e` | `#353534` | `#222222` |
| `$accent` | `#ba9eff` | `#69daff` | `#ff0033` | `#4ae176` |
| `$accent-dim` | `#8455ef` | `#00cffc` | `#d73357` | `#22c55e` |
| `$text` | `#f2effa` | `#e0f0ff` | `#f0e0e0` | `#e0ffe0` |
| `$text-dim` | `#8a8694` | `#6a8a94` | `#8a7674` | `#6a946a` |
| `$success` | `#4ae176` | `#4ae176` | `#4ae176` | `#4ae176` |
| `$error` | `#d73357` | `#ff4466` | `#ff0033` | `#ff4444` |

### Design Philosophy Translation

- **"No-line rule"** -> `border: none` on containers, background color shifts between nested elements
- **"Ghost borders"** -> `border: tall $surface-active` (barely visible, tonal)
- **"Glassmorphism"** -> overlays use `$surface-high` background, not achievable as blur in terminal
- **"Signature textures"** -> accent-colored left borders on assistant messages, accent underline on focused input
- **Tonal layering** -> Textual CSS class-based surface hierarchy: `$bg` < `$surface` < `$surface-high` < `$surface-active`

### Runtime Switching

Cycle themes with `Ctrl+Shift+T` or select in settings. Preference persisted in config under `[tui]` section.

## Streaming & Backend Changes

### Two Rendering Modes (switchable via `Ctrl+R` or settings)

**Mode 1: Live Stream (SSE)**

New backend endpoint:

```
POST /chat/stream
Content-Type: text/event-stream

data: {"token": "To", "done": false}
data: {"token": " minimize", "done": false}
...
data: {"token": "", "done": true, "provider": "ollama", "latency": 0.84}
```

- TUI opens async `httpx` stream, appends tokens to message widget in real-time
- Final event carries metadata (provider, latency) for telemetry
- Requires new dependency: `sse-starlette>=2.0.0`
- Requires new `stream_chat()` method on the agent
- Each provider handles streaming differently: Ollama natively streams, Claude/Gemini APIs stream, web search returns in bulk

**Mode 2: Typewriter**

- Calls existing `/chat` endpoint (full response)
- Renders characters at configurable speed (default 40 chars/s)
- Skippable: press any key during animation to show full response immediately
- Zero backend changes needed

### Client Wrapper

`friday_ai/tui/client.py` — async HTTP client that mirrors all Friday API endpoints:

- `chat(message)` -> full response from `/chat`
- `chat_stream(message)` -> async generator yielding tokens from `/chat/stream`
- `health()` -> `/health`
- `classify(message)` -> `/classify`
- `context()` -> `/context`
- `session_save()` / `session_load()` -> session endpoints
- `memory_list()` / `memory_forget(keyword)` / `memory_clear()` -> memory endpoints
- `reload()` -> `/reload`
- `mcp_status()` / `mcp_reconnect()` -> MCP endpoints

## Settings Screen

### Two Modes

**Simple Mode** (default) — single page, ~12 essential fields:

- Theme, Model, Provider Mode, Render Mode, Auto Escalate, Dangerous Blocking, Show Timestamps, Message Spacing, MCP Servers count, Memory count, Tools count

**Advanced Mode** — full btop-style, 8 tabs, 70+ fields. Accessed by pressing `a` or selecting `[Advanced]` from Simple mode. Mode preference persisted in config.

### Advanced Mode Tabs

**General (14 fields):**
Render Mode, Typewriter Speed, Auto Escalate, Provider Mode, Max Workers, Max Tool Rounds, History Sync, Auto Save Session, Auto Save Interval, Dangerous Cmd Blocking, Session History Limit, Log Level, Log File Path

**Provider (14 fields):**
Default Provider, Fallback Order (reorderable), Ollama URL, Ollama Model Fast/Default/Heavy, Claude Model, Claude API Key (masked), Gemini Model, Gemini API Key (masked), OpenAI Model, OpenAI API Key (masked), Race Timeout, Provider Health Check Interval

**MCP Servers (per-server + global):**
Per server (x11): Enabled toggle, Status (read-only), Tool Count (read-only), Auto Reconnect, Reconnect Interval. Global: Reconnect All action, Max Concurrent servers

**Tools:**
Per built-in tool (x21): Enabled toggle, Category (read-only). Global: Intent Tool Filtering toggle, Hot Reload action

**Memory:**
Memory Entries count (read-only), View Memory action (scrollable list), Clear All Memory action (with confirm), Daily Log Retention, Memory Search text input

**Identity:**
SOUL.md / USER.md / AGENTS.md / BOOTSTRAP.md — read-only 5-line previews with "Open in $EDITOR" action for each

**Appearance (12 fields):**
Theme, Show Timestamps, Show Provider Tags, Show Latency, Message Spacing (Compact/Normal/Relaxed), Code Theme (monokai/dracula/github-dark/native), Sidebar Width, Telemetry Panel Width, Telemetry Refresh Rate, ASCII Logo on Welcome, Clock in Header

**Keybinds:**
All keybindings listed with rebind support. Each field captures a new key combo on Enter.

### Interaction Model (btop-style)

- `j/k` or `Up/Down` — navigate fields
- `h/l` or `Left/Right` — cycle enum values
- `Enter` — toggle booleans, confirm text input, trigger actions
- `Tab` — next section tab
- `Shift+Tab` — previous section tab
- `s` — save all changes to `~/.config/friday/config.toml` + call `/reload`
- `Esc` — discard and close
- Changes buffered until explicit save, `[modified]` indicator shown when unsaved

## Error Handling

### Connection Failures

- **On launch:** `/health` check — if backend is down, shows connection screen with `[r] Retry  [s] Settings  [q] Quit`
- **Mid-conversation:** toast notification, messages queue locally, auto-retry every 5s
- **Provider-specific:** inline message — "ollama failed, fell back to claude" with both provider tags

### Streaming Interruption

- Partial message kept with `[stream interrupted]` marker
- `r` on that message to retry

### Empty States

- No conversations: Welcome screen with quick actions
- No providers online: telemetry panel flashes, input bar shows "No providers available"
- No MCP servers: graceful degradation, tools show 0 count

### Large Responses

- Messages over 200 lines: collapsed with `[Show full response]` toggle
- Code blocks over 50 lines: collapsed with line count

## Entry Point & Launch

### Shell Script (`bin/friday-tui`)

```bash
#!/usr/bin/env bash
FRIDAY_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
source "$FRIDAY_DIR/.venv/bin/activate"
python -m friday_ai.tui "$@"
```

### Launch Methods

- Direct: `friday-tui`
- Floating kitty: `kitty --class friday-tui -e friday-tui`
- Super+F keybind (already wired): toggles kitty floating window
- With overrides: `friday-tui --theme neural --port 8080`

### CLI Flags

| Flag | Purpose |
|------|---------|
| `--theme` | Override startup theme |
| `--port` | Override API port |
| `--host` | Override API host |
| `--no-connect` | Launch without connecting (offline history browsing) |
| `--session` | Load a specific session file on start |

### Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
tui = ["textual>=1.0.0"]
stream = ["sse-starlette>=2.0.0"]

[project.scripts]
friday-tui = "friday_ai.tui:main"
```

`httpx` is already a project dependency.

## Config Changes

New `[tui]` section in `~/.config/friday/config.toml`:

```toml
[tui]
theme = "obsidian"
render_mode = "live_stream"   # or "typewriter"
typewriter_speed = 40
settings_mode = "simple"      # or "advanced"
show_timestamps = true
show_provider_tags = true
show_latency = true
message_spacing = "normal"    # compact / normal / relaxed
code_theme = "monokai"
sidebar_width = 30
telemetry_width = 30
telemetry_refresh = 30
ascii_logo = true
clock_in_header = true
```

Keybinds stored in a separate `[tui.keybinds]` section:

```toml
[tui.keybinds]
toggle_sidebar = "ctrl+b"
toggle_telemetry = "ctrl+t"
open_settings = "ctrl+s"
new_conversation = "ctrl+n"
search_conversations = "ctrl+p"
cycle_theme = "ctrl+shift+t"
toggle_render_mode = "ctrl+r"
copy_code = "y"
send_message = "enter"
newline = "shift+enter"
```
