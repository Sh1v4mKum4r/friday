# Friday — Full System Redesign Spec

## Overview

Friday (Female Replacement Intelligent Digital Assistant Youth) is a personal AI system assistant for Arch Linux. Hybrid Rust + Python architecture: Rust core handles performance-critical orchestration, Python microservice handles AI/LLM logic.

**Hardware target:** i5-10300H (4 cores), 8GB RAM, GTX 1650 (4GB VRAM), NVMe SSD.
**Primary DE:** Cosmic. Secondary: Hyprland. Both fully supported.

---

## Phase 1: Core System

### 1. Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Friday System                      │
│                                                       │
│  ┌────────────────────────────────────────────────┐   │
│  │          Rust Core (single binary)             │   │
│  │                                                │   │
│  │  CLI ── Async Task Manager ── DE Layer         │   │
│  │   │       │       │            │               │   │
│  │  Hotkey  /btw  /parallel   Cosmic/Hypr         │   │
│  │  Launcher       /pipe      auto-detect         │   │
│  │              Panel Widget                      │   │
│  └──────────────┬─────────────────────────────────┘   │
│                 │ HTTP (localhost:65535)               │
│  ┌──────────────▼─────────────────────────────────┐   │
│  │       Python Microservice (FastAPI)            │   │
│  │                                                │   │
│  │  Provider Router                               │   │
│  │   ├─ OllamaProvider    (REST, local)           │   │
│  │   ├─ GeminiProvider    (API key or CLI)        │   │
│  │   ├─ ClaudeProvider    (API key or CLI)        │   │
│  │   ├─ OpenAIProvider    (API key only)          │   │
│  │   └─ WebSearchProvider (googler / Gemini)      │   │
│  │                                                │   │
│  │  Tool System (plugin-based)                    │   │
│  │   ├─ core/  (10 built-in tools)               │   │
│  │   └─ plugins/  (user-added, hot-reload)        │   │
│  │                                                │   │
│  │  Memory & Identity Engine                      │   │
│  │   ├─ SOUL.md, USER.md (injected every session) │   │
│  │   ├─ MEMORY.md (long-term curated)             │   │
│  │   └─ memory/YYYY-MM-DD.md (daily logs)         │   │
│  └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

**Communication:** HTTP on port 65535. Rust sends requests, Python returns responses.

### 2. Provider Router & Fallback Chain

**Priority order:**
1. Ollama (local, always first)
2. API key providers (Gemini → Claude → OpenAI, whichever keys exist)
3. CLI fallback (`gemini -p` / `claude -p` when no API keys)
4. Web search (for queries needing current/live information)

**Auto-escalation:** Complexity scoring heuristic:
- Short prompt + system keywords → Ollama
- Long prompt, code generation, multi-step reasoning → cloud
- "latest", "current", "today", "news" keywords → web search
- User can force provider: `/ollama`, `/gemini`, `/claude`, `/openai`, `/search`

**Provider interface contract:**
```
send_message(prompt, tools?, history?) → response
is_available() → bool
supports_tools() → bool
```

**CLI fallback tool-calling:** Tool descriptions wrapped in prompt text. Response parsed for structured pattern:
```
TOOL_CALL: {"name": "run_shell", "args": {"command": "ls -la"}}
```
Friday regex-matches `TOOL_CALL: {json}` in the response, executes the tool, appends the result, and re-prompts. Parsing failure = treat entire response as plain text. Max 5 tool-call rounds per request.

**Provider config (`~/.config/friday/config.toml`):**
```toml
[providers]
ollama_model = "qwen2.5:7b"
ollama_url = "http://localhost:11434"
gemini_api_key = ""
claude_api_key = ""
openai_api_key = ""

[server]
port = 65535
host = "127.0.0.1"

[behavior]
auto_escalate = true
max_workers = 4

[de]
override = ""  # empty = auto-detect via $XDG_CURRENT_DESKTOP

[voice]
enabled = false
```

### 3. Execution Model

**Single agent identity, multi-threaded execution.**

The Rust core parses user input, detects independent sub-tasks, and spawns parallel `tokio::spawn` workers. Each worker makes its own HTTP call to the Python backend. Python backend is stateless per-request — thread-safe by design.

**Task types:**

| Type | Trigger | Behavior |
|---|---|---|
| Foreground | Normal message | Blocks CLI, shows "thinking...", streams response |
| Background | `/btw <task>` | Non-blocking, notifies via `notify-send` when done |
| Parallel | Auto-detected or `/parallel t1 && t2` | Splits into workers, waits for all, returns combined |
| Pipeline | `/pipe t1 \| t2` | Output of task1 feeds into task2 sequentially |

**Task splitting heuristic:** Messages containing "and also", "while you're at it", or multiple independent clauses get split into parallel workers.

**Resource limits:**
- Max 4 concurrent workers (matches CPU core count)
- Background tasks get lower priority than foreground
- If Ollama is busy, queue rather than drop
- If a worker fails on Ollama, retry once on cloud provider
- If all providers fail, notify user

### 4. Tool System

**10 core tools, always loaded:**

| Tool | What it does |
|---|---|
| `run_shell` | Execute any shell command |
| `clipboard_get` | Read clipboard (wl-paste) |
| `clipboard_set` | Write clipboard (wl-copy) |
| `notify` | Send desktop notification |
| `de_command` | Window/workspace management (auto-routes to Cosmic or Hyprland) |
| `file_read` | Read a file |
| `file_write` | Write a file |
| `web_search` | Search the web |
| `memory_read` | Recall from persistent memory |
| `memory_write` | Save to persistent memory |

**Plugin system:**
```
~/.config/friday/tools/
├── core/           # ships with Friday
└── plugins/        # user-added
```

Each plugin is a Python file following a simple contract:
```python
name = "screenshot"
description = "Capture a screenshot of the current screen or a specific region"

def run(region: str = "full") -> str:
    # implementation
```

Friday discovers all tools at startup by scanning both directories. `/reload` rescans without restart. Keep total loaded tools under ~20 for reliable 7B model tool-calling.

**DE abstraction in tools:**
`de_command("move window left")` auto-routes to:
- Cosmic → cosmic-comp DBus call
- Hyprland → `hyprctl dispatch movewindow l`

DE detected at startup via `$XDG_CURRENT_DESKTOP`, overridable in config.

### 5. Identity & Memory (OpenClaw-inspired)

**Identity files (`~/.config/friday/`):**

| File | Purpose |
|---|---|
| `SOUL.md` | Personality, voice, tone, opinions, humor, operating rules. Friday can self-evolve this file (notifies user when changed). |
| `USER.md` | About the user — name, preferences, how to address them. Friday updates as it learns. |
| `AGENTS.md` | Worker behavior rules — task splitting heuristics, resource limits, escalation policy. |
| `BOOTSTRAP.md` | First-run ritual: asks user's name, detects DE, sets initial preferences. Self-deletes after completion. |
| `config.toml` | Technical settings (providers, port, DE override, voice toggle). |

All .md identity files are injected into the system prompt at the start of every session.

**Memory (`~/.local/share/friday/`):**

| Path | Purpose |
|---|---|
| `memory/MEMORY.md` | Long-term curated knowledge. Friday writes here when it learns something durable. |
| `memory/YYYY-MM-DD.md` | Daily session log. Auto-created, auto-pruned after 30 days (configurable). |
| `history/session-*.json` | Full conversation sessions. On startup, offers to resume last or start fresh. |

**Memory commands:** `/memory list`, `/memory forget <key>`, `/memory clear`
**Context inspection:** `/context` shows exactly what's being sent to the model.

### 6. Interface Layer

**CLI (primary):**
- Async readline with `tokio`, never blocks on LLM response
- Live status line: active workers, provider in use, online/offline

| Command | Action |
|---|---|
| `/btw <task>` | Background task |
| `/parallel t1 && t2` | Parallel execution |
| `/pipe t1 \| t2` | Pipeline tasks |
| `/ollama`, `/gemini`, `/claude`, `/openai` | Force provider |
| `/search <query>` | Web search mode |
| `/memory list/forget/clear` | Memory management |
| `/context` | Inspect prompt being sent |
| `/reload` | Reload tools + config |
| `/session resume/new/list` | Session management |

**Panel Widget:**
- Cosmic → panel applet via `libcosmic` (Rust)
- Hyprland → Waybar custom module (JSON stdout)
- Shows: online/offline, active worker count, current provider

**Hotkey Launcher:**
- Keybind (e.g., `Super+F`) opens one-shot prompt popup
- Cosmic → cosmic launcher plugin or dialog
- Hyprland → Rofi/Wofi in dmenu mode
- Returns result via notification

**Startup modes:**
```
friday              → starts Rust core + Python backend (full mode)
friday --daemon     → background mode (panel widget + hotkey only)
friday --cli-only   → terminal only, no panel/launcher
```

---

## Phase 2: Future Enhancements

These are designed-for but NOT built in Phase 1. The architecture supports plugging them in without rearchitecting.

### 2.1 RAG (Retrieval-Augmented Generation)
- **What:** Friday indexes your local files (`~/Documents`, `~/Projects`, etc.) and retrieves relevant context before answering.
- **How:** Embedding model via Ollama, vector store via ChromaDB or SQLite-vss.
- **Integration point:** A `context_providers` interface in the Python backend. Phase 1 returns only session history + memory. Phase 2 adds a RAG provider that queries the vector store.
- **Enables:** "What did I write about X last week?", "Find the config I changed yesterday."

### 2.2 Voice Input/Output
- **STT (Speech-to-Text):** Whisper.cpp running locally. Small model (~400MB VRAM). Triggered by push-to-talk hotkey (`Super+V`).
- **TTS (Text-to-Speech):** Piper TTS, runs on CPU (~50MB per voice model). Friday speaks responses aloud.
- **VRAM concern:** Whisper and Ollama can't share 4GB VRAM simultaneously. Solution: Whisper loads on-demand, Ollama unloads temporarily. Or run Whisper on CPU (~2s per sentence).
- **Config:**
  ```toml
  [voice]
  enabled = true
  stt_engine = "whisper"
  stt_model = "small"
  stt_device = "cpu"
  tts_engine = "piper"
  tts_voice = "en_US-amy"
  hotkey = "Super+V"
  ```
- **Integration point:** Voice is just another input/output mode for the Rust core. STT produces text → same pipeline. TTS consumes response text → audio out.

### 2.3 Dreaming (Background Memory Consolidation)
- **What:** Periodic background process that reviews daily logs and consolidates important patterns into MEMORY.md.
- **How:** Runs via cron or systemd timer during idle. Uses local Ollama model to score and promote memory candidates.
- **Phases:** Light (ingest recent signals) → Deep (score and promote to MEMORY.md) → REM (reflect on themes).
- **Integration point:** Reads `memory/YYYY-MM-DD.md` files, writes to `memory/MEMORY.md`. No architecture change needed.

### 2.4 Semantic Memory Search
- **What:** Hybrid semantic + keyword search over all memory files.
- **How:** Embeddings via Ollama, stored in SQLite-vss or ChromaDB alongside the RAG index.
- **Integration point:** Enhances `memory_read` tool. Phase 1 does keyword grep. Phase 2 does vector similarity.

### 2.5 Memory Wiki
- **What:** Compiles durable memories into a structured, provenance-rich wiki vault.
- **How:** Plugin that processes MEMORY.md + daily logs into categorized wiki pages with contradiction tracking and freshness scoring.
- **Integration point:** New tool plugin in `~/.config/friday/tools/plugins/`.

### 2.6 Multi-Device / Messaging Gateway
- **What:** Access Friday from phone, other machines, or messaging apps (Telegram, Discord, etc.).
- **How:** Gateway daemon (inspired by OpenClaw) that bridges messaging platforms to Friday's API.
- **Integration point:** The Python microservice already exposes HTTP endpoints. A gateway would be another client alongside the Rust CLI.

### 2.7 Canvas / Rich UI
- **What:** Agent-editable HTML/CSS/JS surfaces for rich output (charts, dashboards, interactive widgets).
- **How:** Local web server serving agent-generated HTML, opened in browser.
- **Integration point:** New tool plugin that writes HTML and opens it.

---

## Project Structure

```
~/Projects/friday/
├── friday_core/              # Rust core
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs           # entry point, CLI
│       ├── task_manager.rs   # async task spawning, /btw, /parallel, /pipe
│       ├── provider_client.rs # HTTP client to Python backend
│       ├── de.rs             # DE detection + abstraction
│       ├── panel.rs          # Waybar/Cosmic panel widget
│       ├── launcher.rs       # Rofi/Cosmic hotkey launcher
│       └── config.rs         # config.toml parser
│
├── friday_ai/                # Python microservice
│   ├── server.py             # FastAPI app
│   ├── providers/
│   │   ├── base.py           # Provider interface
│   │   ├── ollama.py         # Ollama REST client
│   │   ├── gemini.py         # Gemini API + CLI fallback
│   │   ├── claude.py         # Claude API + CLI fallback
│   │   ├── openai.py         # OpenAI API
│   │   └── web_search.py     # googler / Gemini grounding
│   ├── router.py             # Provider selection + escalation logic
│   ├── agent.py              # Prompt construction, tool-call loop
│   ├── memory.py             # MEMORY.md + daily logs + session history
│   ├── identity.py           # SOUL.md + USER.md + AGENTS.md loader
│   ├── tool_loader.py        # Plugin discovery + loading
│   └── tools/
│       ├── core/
│       │   ├── shell.py
│       │   ├── clipboard.py
│       │   ├── notify.py
│       │   ├── de.py
│       │   ├── files.py
│       │   ├── web_search.py
│       │   └── memory.py
│       └── plugins/
│
├── config/                   # Default identity files (copied to ~/.config/friday/ on first run)
│   ├── SOUL.md
│   ├── USER.md
│   ├── AGENTS.md
│   ├── BOOTSTRAP.md
│   └── config.toml
│
├── start.sh                  # Launcher script
├── pyproject.toml            # Python dependencies
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-13-friday-redesign-design.md  # this file
```

---

## Technical Constraints & Notes

1. **Wayland environment variables for DE tools:** When Python executes `hyprctl` or cosmic-comp commands via the DE abstraction layer, it needs access to `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, and `HYPRLAND_INSTANCE_SIGNATURE`. If the Python microservice runs as a systemd background service, these must be explicitly passed from the Rust core (via the HTTP request payload or detected at Python startup from `/proc`).

2. **VRAM constraints (GTX 1650 4GB):** Qwen 2.5 7B Q4 consumes ~3.5-4GB VRAM. Tight but doable. Configure Ollama to unload the model quickly (`OLLAMA_KEEP_ALIVE=5m` or shorter) so VRAM is freed for gaming or other GPU tasks. Recommend a 3B model (e.g., Phi-3 mini) as a faster/lighter fallback option in config.

3. **Port 65535:** Hardcoded as default but configurable via `config.toml`. If binding fails, fall back to scanning 65534 → 49152 for an open port, or error with a clear message.

4. **Tool plugin hot-reloading:** `/reload` must use `importlib.reload()` with proper module cleanup — unregister old tool instances before loading new ones. Track loaded modules by path to prevent stacking duplicate tools in memory.

## Success Criteria

1. `friday` launches both Rust core and Python backend, connects on port 65535
2. Chat works with Ollama locally (no internet required)
3. `/btw` spawns a background task and notifies on completion
4. `/parallel` splits independent tasks across workers
5. Provider fallback chain works: Ollama → API → CLI → web search
6. DE auto-detection works for both Cosmic and Hyprland
7. Panel widget shows status in the active DE's panel
8. Hotkey launcher opens a one-shot prompt popup
9. SOUL.md personality is reflected in responses
10. BOOTSTRAP.md runs on first launch and self-deletes
11. Memory persists across sessions (MEMORY.md + daily logs)
12. `/context` shows what's being sent to the model
13. Tool plugins in `~/.config/friday/tools/plugins/` are auto-discovered
