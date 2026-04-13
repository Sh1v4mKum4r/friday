# Friday

**Female Replacement Intelligent Digital Assistant Youth**

A personal AI system assistant for Arch Linux — always-on, provider-agnostic, and built to think with you.

```
  Language    Rust + Python
  LLM Modes   Ollama · Gemini · Claude · OpenAI · CLI fallbacks
  DE Support  Hyprland · Cosmic (auto-detected)
  Tests       279
  Status      Active development
```

---

## What It Is

Friday is a hybrid Rust + Python AI assistant designed to live on your desktop. A Rust core handles everything low-level — the CLI, async task spawning, hotkey listener, panel widget, and Unix socket daemon. A Python FastAPI microservice handles the intelligence layer — LLM provider routing, agent logic, tool execution, and memory.

You talk to Friday from a terminal, a hotkey (Super+F), or a panel widget. It can run shell commands, search the web, read and write files, copy to clipboard, send desktop notifications, and remember things across sessions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       User Input                        │
│          terminal · hotkey (Super+F) · panel widget     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   friday_core  (Rust)                   │
│                                                         │
│  clap CLI  ──►  task_manager  ──►  Unix socket client   │
│  launcher  ──►  panel widget  ──►  DE detection         │
│                  tokio async                            │
└────────────────────────┬────────────────────────────────┘
                         │  HTTP  (127.0.0.1:65535)
┌────────────────────────▼────────────────────────────────┐
│                  friday_ai  (Python)                    │
│                                                         │
│  FastAPI router  ──►  agent.py  ──►  tool_loader        │
│                            │                            │
│              ┌─────────────▼─────────────┐              │
│              │      Provider Router       │              │
│              │  Ollama · Gemini · Claude  │              │
│              │  OpenAI · CLI fallbacks    │              │
│              └─────────────┬─────────────┘              │
│                            │                            │
│  memory.py  ◄──────────────┘                            │
│  identity.py  (SOUL.md · USER.md · AGENTS.md)           │
└─────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    Tools Layer                          │
│                                                         │
│  core/   shell · clipboard · notify · files · de        │
│          web_search · memory_tool                       │
│  plugins/  drop any .py here — auto-discovered          │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### Multi-Provider LLM with Fallback and Racing

Friday supports Ollama (local), Gemini, Claude, and OpenAI simultaneously. Three provider modes:

- **fallback** — try providers in order, move on if one fails
- **race** — fire all configured providers at once, return the fastest response
- **single** — pin to one provider

API keys are optional. If a cloud provider's SDK call fails, Friday falls back to the CLI (`gemini`, `claude`) automatically.

### Persistent Memory and Active Learning

Every session is logged. Friday searches past interactions before responding, so it builds up context about you over time. Memory is plain Markdown — `MEMORY.md` plus daily logs — readable and editable by hand.

SOUL.md defines Friday's personality. USER.md describes you. BOOTSTRAP.md runs on first interaction. All files live in `~/.config/friday/` and can be customized freely.

### Plugin Tool System

Drop a `.py` file in `~/.config/friday/tools/plugins/`. It gets discovered and loaded automatically — no config changes, no restart required. Built-in tools cover shell execution, clipboard read/write, desktop notifications, file read/write, web search, DE-specific commands, and memory.

### DE Abstraction

Friday detects whether you are running Hyprland or Cosmic and routes DE-specific commands (window management, screenshots, workspace switching) to the right backend automatically. The `[de] override` config key lets you pin a DE if detection misbehaves.

### Async Multithreading from the CLI

- `/btw <task>` — spawn a background task, get a response now, result delivered when ready
- `/parallel <t1> | <t2>` — run two prompts in parallel
- `/pipe <step1> >> <step2>` — chain outputs as inputs

### Always-On Daemon

```
./start.sh --daemon
```

Starts the backend as a persistent Unix socket server. Register the hotkey with `./start.sh --install-keybind` and invoke Friday anywhere on your desktop with Super+F.

---

## Project Structure

```
friday/
├── friday_core/            Rust async CLI, task manager, DE detection
│   └── src/
│       ├── main.rs
│       ├── client.rs       HTTP client for the Python backend
│       ├── commands.rs     /btw, /parallel, /pipe, provider commands
│       ├── de.rs           DE detection (Hyprland / Cosmic)
│       ├── launcher.rs     hotkey listener
│       ├── panel.rs        panel widget
│       ├── socket.rs       Unix socket daemon
│       └── task_manager.rs async background task pool
│
├── friday_ai/              Python FastAPI microservice
│   ├── server.py           FastAPI app + /chat endpoint
│   ├── router.py           provider selection logic
│   ├── agent.py            tool-calling agent loop
│   ├── memory.py           session history + MEMORY.md search
│   ├── identity.py         loads SOUL.md / USER.md / AGENTS.md
│   ├── config.py           config.toml loader
│   ├── tool_loader.py      auto-discovers core + plugin tools
│   ├── providers/
│   │   ├── ollama.py
│   │   ├── gemini.py
│   │   ├── claude.py
│   │   ├── openai_provider.py
│   │   └── web_search.py
│   └── tools/
│       ├── core/           10 built-in tools
│       └── plugins/        user-added tools (hot-reloadable)
│
├── config/                 defaults copied to ~/.config/friday/ on first run
│   ├── config.toml
│   ├── SOUL.md             Friday's personality
│   ├── USER.md             your profile
│   ├── AGENTS.md           agent behavior rules
│   └── BOOTSTRAP.md        first-run prompt
│
├── bin/
│   ├── friday-send         quick-send from any terminal or script
│   ├── friday-hotkey       hotkey invocation wrapper
│   └── friday-install-keybind
│
├── tests/                  279 tests (pytest)
├── start.sh
└── pyproject.toml
```

---

## Setup

### Prerequisites

- Arch Linux (or any systemd distro with Hyprland or Cosmic)
- Rust (stable) + Cargo
- Python 3.11+
- [Ollama](https://ollama.com/) for local inference (optional but recommended)

### Install

```bash
git clone https://github.com/Sh1v4mKum4r/friday.git
cd friday

# Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all-providers,dev]"

# Rust core
cd friday_core && cargo build --release && cd ..

# Pull a local model (optional)
ollama pull qwen2.5:7b
```

### Configure

On first run, `start.sh` copies the defaults to `~/.config/friday/`. Add API keys there:

```toml
# ~/.config/friday/config.toml

[providers]
ollama_model    = "qwen2.5:7b"
gemini_api_key  = "..."
claude_api_key  = "..."
openai_api_key  = "..."

[behavior]
provider_mode = "fallback"   # fallback | race | single
max_workers   = 4
```

---

## Usage

```bash
./start.sh                      # start backend + open CLI
./start.sh --daemon             # always-on background mode
./start.sh --cli-only           # terminal only (no hotkey/panel)
./start.sh --install-keybind    # register Super+F hotkey

friday-send "what time is it"   # one-shot from anywhere
```

### CLI Commands

| Command | Description |
|---|---|
| `/btw <task>` | Run a task in the background, continue chatting |
| `/parallel <a> \| <b>` | Run two prompts simultaneously |
| `/pipe <a> >> <b>` | Pipe output of one prompt into the next |
| `/ollama` `/gemini` `/claude` `/openai` | Pin provider for this message |
| `/search <query>` | Web search |
| `/memory` | Show memory summary |
| `/context` | Show current session context |
| `/session` | Start a new session |
| `/reload` | Reload tools and config without restart |

---

## Tests

```bash
pytest
# or with coverage
pytest --tb=short -q
```

279 tests covering agent logic, providers, router, tool loader, memory, identity, config, and the server.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Rust async runtime | tokio 1 |
| Rust HTTP client | reqwest 0.12 |
| Rust CLI parsing | clap 4 |
| Python web framework | FastAPI + uvicorn |
| Python HTTP client | httpx |
| Python validation | pydantic v2 |
| Local LLM inference | Ollama |
| Cloud LLMs | Gemini 2.5 Flash · Claude Sonnet · GPT-4o |

---

## Motivation

This project started as a personal productivity tool and became a study in systems integration: bridging a low-latency compiled core with a flexible Python inference layer, making the whole thing DE-aware, and building a memory system that actually improves over time. It is also an exercise in making AI assistants that feel like they know you rather than generic chatbots.

---

## License

MIT
