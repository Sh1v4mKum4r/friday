# Friday — AI System Assistant

## What Is This
Friday (Female Replacement Intelligent Digital Assistant Youth) is a personal AI system assistant for Arch Linux. It uses a **Rust core** for async task management and a **Python backend** for AI/LLM work.

## Current State (as of 2026-04-13)
Claude Code and the user are **redesigning the architecture**. A design spec is being written. Do NOT start implementing until the spec exists at `docs/superpowers/specs/` and has been approved.

## Architecture Redesign — Key Decisions Made

### Multi-Provider LLM Support
- **Primary:** Local LLM via Ollama (always available, free, offline)
- **Cloud escalation:** Gemini + Claude + OpenAI APIs (for complex tasks)
- **Routing:** Auto-detects task complexity and escalates, but user can force a provider with commands like `/cloud`, `/gemini`, `/claude`

### Desktop Environment Support
- **Primary DE:** Cosmic (cosmic-comp)
- **Secondary DE:** Hyprland (hyprctl)
- Friday needs a **DE abstraction layer** so tools work on both compositors
- Cosmic uses DBus/cosmic-comp protocols, Hyprland uses hyprctl socket

### Interface
- **CLI** — main terminal interface (Rust async with tokio)
- **Panel widget** — status indicator (Waybar for Hyprland, Cosmic panel applet for Cosmic)
- **Hotkey launcher** — quick one-shot commands via popup (Rofi/Wofi for Hyprland, Cosmic launcher for Cosmic)

### Persistence
- **Session history** — save/load recent conversations to local files
- **Memory system** — persistent knowledge about user preferences, projects, system state

### Existing Code
- `friday_core/` — Rust async CLI with `/btw` background tasks (talks to Python via HTTP)
- `server.py` — FastAPI microservice wrapping the AI agent
- `agent.py` — Agent with system + research sub-agents (NEEDS REWRITE: uses deprecated `google.generativeai`)
- `tools.py` — Shell exec, clipboard (wl-paste/wl-copy), notifications, hyprctl
- `start.sh` — Launcher that boots Python server + Rust CLI

### Known Bugs
- `server.py:22` — `status_id=400` should be `status_code=400`
- `agent.py` — uses deprecated `google.generativeai`, must migrate to `google.genai`
- Hardcoded `gemini-1.5-pro` model references

## Design Spec
**APPROVED.** Full spec at `docs/superpowers/specs/2026-04-13-friday-redesign-design.md`. Read it before doing anything.

## Your Tasks (Gemini CLI)
The implementation plan will assign specific tasks. Likely areas for you:
1. **DE abstraction layer** — make tools work on both Cosmic and Hyprland (you know Cosmic better)
2. **Tool plugins** — expand core tools, build the plugin discovery system
3. **Identity system** — SOUL.md, USER.md, BOOTSTRAP.md loader and first-run ritual
4. **Panel/launcher integration** — Cosmic panel applet + Cosmic launcher plugin

**Important technical constraints:**
- Pass Wayland env vars (`WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, `HYPRLAND_INSTANCE_SIGNATURE`) when executing DE commands
- Keep total tools under ~20 for reliable 7B model tool-calling
- Use `importlib.reload()` with proper cleanup for `/reload` hot-reloading
- Port 65535, configurable in config.toml

## Hardware Context
- Arch Linux, i5-10300H, 8GB RAM, GTX 1650 4GB VRAM
- Ollama for local inference (Qwen 2.5 7B or Mistral 7B Q4)
- NVMe storage, ~170GB free on /home
