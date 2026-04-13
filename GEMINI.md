# Friday — AI System Assistant

## What Is This
Friday (Female Replacement Intelligent Digital Assistant Youth) is a personal AI system assistant for Arch Linux. Hybrid Rust + Python architecture: Rust core for async task management, Python FastAPI backend for AI/LLM logic.

## Current State (2026-04-13)
**Phase 1 is COMPLETE.** 279 tests passing. Rust compiles clean. Integration tested.

Project renamed from `jarvis` → `friday`. Directory: `~/Projects/friday`.

### What's built
- Multi-provider LLM: Ollama (local) → Claude CLI → Gemini CLI → Web Search (fallback chain)
- Provider racing: fire all simultaneously, return fastest (`provider_mode = "race"`)
- Rust async CLI with /btw, /parallel, /pipe, force provider commands
- Plugin tool system (9 core tools, hot-reloadable)
- DE abstraction (Cosmic + Hyprland auto-detect)
- OpenClaw-inspired identity: SOUL.md, USER.md, AGENTS.md, BOOTSTRAP.md
- Active learning memory: MEMORY.md + daily logs + keyword search across past sessions
- Always-on Unix socket daemon + friday-send + hotkey launcher
- All models configurable in config.toml

### Key files
- `friday_ai/server.py` — FastAPI app (port 65535)
- `friday_ai/router.py` — provider selection, fallback chain, racing
- `friday_ai/agent.py` — prompt construction, tool-call loop (max 5 rounds)
- `friday_ai/providers/` — Ollama, Gemini (API+CLI), Claude (API+CLI), OpenAI, web search
- `friday_ai/tools/core/` — 9 tool plugins
- `friday_core/src/` — Rust CLI, task manager, DE detection, socket daemon
- `config/` — default identity files + config.toml

## Your Tasks (Gemini CLI)

Focus on **Cosmic DE polish and extension**:

### Task A: Polish DE Abstraction Layer
File: `friday_ai/tools/core/de.py`
- Cosmic path uses generic `busctl call` — needs real cosmic-comp DBus methods
- Test workspace switching, window focus, window move on Cosmic
- Hyprland path works (`hyprctl {cmd}`) but verify
- Ensure Wayland env vars (`WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, `HYPRLAND_INSTANCE_SIGNATURE`) are passed

### Task B: Cosmic Panel Applet
File: `friday_core/src/panel.rs`
- Currently stub (Waybar JSON only)
- Build Cosmic panel applet using `libcosmic` (Rust), or a simpler script integration
- Show: online/offline, active workers, current provider

### Task C: Cosmic Launcher Integration
File: `friday_core/src/launcher.rs`
- Currently falls back to Rofi for Cosmic
- Investigate Cosmic's launcher/dialog system
- Use native Cosmic dialog if available, else Rofi fallback

### Task D: Additional Tool Plugins (optional)
Directory: `friday_ai/tools/core/` or `~/.config/friday/tools/plugins/`
- Screenshot (using `grim` for Wayland)
- Bluetooth toggle
- Audio/volume control (`wpctl` / `pactl`)
- System info (CPU temp, RAM, battery)

### Constraints
- Keep total tools under ~20 for 7B model reliability
- Port 65535, configurable in config.toml
- Full spec: `docs/superpowers/specs/2026-04-13-friday-redesign-design.md`

## Hardware
- Arch Linux, i5-10300H, 8GB RAM, GTX 1650 4GB VRAM
- Ollama with Qwen 2.5 7B Q4
- NVMe, ~170GB free on /home
