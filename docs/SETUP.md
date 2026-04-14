# Friday — Complete Setup Guide

This guide covers setting up Friday from scratch on a new Arch Linux machine, and containerizing it with Docker.

---

## Part 1: Fresh Install (Bare Metal)

### Prerequisites

```
- Linux (any distro) with Wayland compositor (Cosmic, Hyprland, Sway, GNOME Wayland)
- Python 3.11+
- Rust toolchain (for building friday_core)
- NVIDIA GPU (optional, for fast local LLM — CPU works too)
```

### Step 1: System Dependencies

Pick your distro:

**Arch Linux / Manjaro:**
```bash
sudo pacman -S python git rust cargo curl socat \
    wtype ydotool grim slurp tesseract tesseract-data-eng \
    brightnessctl playerctl libnotify wl-clipboard \
    python-gobject webkit2gtk-4.1
# Optional (AUR)
yay -S googler wlrctl
```

**Ubuntu / Debian / Pop!_OS:**
```bash
sudo apt update && sudo apt install -y \
    python3 python3-venv python3-pip git curl socat \
    build-essential pkg-config libssl-dev \
    wtype ydotool grim slurp tesseract-ocr tesseract-ocr-eng \
    brightnessctl playerctl libnotify-bin wl-clipboard \
    python3-gi gir1.2-webkit2-4.1
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

**Fedora / RHEL:**
```bash
sudo dnf install -y \
    python3 python3-pip git curl socat \
    rust cargo gcc openssl-devel \
    wtype ydotool grim slurp tesseract tesseract-langpack-eng \
    brightnessctl playerctl libnotify wl-clipboard \
    python3-gobject webkit2gtk4.1
```

**openSUSE:**
```bash
sudo zypper install -y \
    python3 python3-pip git curl socat \
    rust cargo gcc libopenssl-devel \
    wtype ydotool grim slurp tesseract-ocr tesseract-ocr-traineddata-english \
    brightnessctl playerctl libnotify-tools wl-clipboard \
    python3-gobject typelib-1_0-WebKit2-4_1
```

**NixOS (flake):**
```bash
# Add to your configuration.nix or use nix-shell:
nix-shell -p python3 rustc cargo curl socat \
    wtype ydotool grim slurp tesseract \
    brightnessctl playerctl libnotify wl-clipboard
```

**All distros — enable ydotool:**
```bash
sudo systemctl enable --now ydotool
sudo usermod -aG input $USER  # re-login required
```

**Note:** Some tools are Wayland-only (wtype, grim, slurp, wl-clipboard). If you're on X11, Friday's desktop tools will have limited functionality. The core chat, LLM, and MCP features work on any Linux.

### Step 2: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama pull qwen2.5:3b  # faster fallback
```

### Step 3: Clone Friday

```bash
cd ~/Projects
git clone https://github.com/Sh1v4mKum4r/friday.git
cd friday
git checkout feat/friday-redesign
```

### Step 4: Python Environment

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install pywebview mcp httpx textual
```

The `--system-site-packages` flag is needed for GTK/pywebview support.

### Step 5: Build Rust Core

```bash
cd friday_core
cargo build --release
cd ..
```

### Step 6: First-Run Config

```bash
./start.sh  # auto-copies config files to ~/.config/friday/
# Press Ctrl+C after it starts
```

Or manually:

```bash
mkdir -p ~/.config/friday/tools/plugins
mkdir -p ~/.local/share/friday/{memory,history,backups}
cp config/config.toml ~/.config/friday/
cp config/SOUL.md ~/.config/friday/
cp config/USER.md ~/.config/friday/
cp config/AGENTS.md ~/.config/friday/
```

### Step 7: Configure

```bash
# Edit config
nvim ~/.config/friday/config.toml

# Key settings:
# [providers]
# ollama_model = "qwen2.5:7b"        # local model
# ollama_model_fast = "qwen2.5:7b"   # for chat/system
# ollama_model_heavy = "qwen2.5:7b"  # for complex tasks
# gemini_api_key = ""                 # optional
# claude_api_key = ""                 # optional
# openai_api_key = ""                # optional
# serpapi_key = ""                    # for Google AI search
#
# [behavior]
# provider_mode = "fallback"          # fallback | race | google
# auto_escalate = true
# max_workers = 4
#
# [server]
# port = 65535
```

### Step 8: Add to PATH

```bash
# Add to ~/.zshrc or ~/.bashrc:
export PATH="$HOME/Projects/friday/bin:$PATH"
eval "$(friday completions)"

# Or symlink:
for cmd in friday friday-tui friday-send friday-gui friday-chrome-bridge; do
    ln -sf ~/Projects/friday/bin/$cmd ~/.local/bin/$cmd
done
```

### Step 9: Keybind (Super+F)

Pick your DE:

**Cosmic:**
Edit `~/.config/cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom`:
```ron
(
    modifiers: [Super],
    key: "f",
): Spawn("/home/YOUR_USER/Projects/friday/bin/friday-hotkey"),
```

**Hyprland:**
Add to `~/.config/hypr/hyprland.conf`:
```
bind = SUPER, F, exec, ~/Projects/friday/bin/friday-hotkey
```

**Sway:**
Add to `~/.config/sway/config`:
```
bindsym $mod+f exec ~/Projects/friday/bin/friday-hotkey
```

**GNOME (Wayland):**
```bash
# Settings → Keyboard → Shortcuts → Custom
# Name: Friday AI
# Command: /home/YOUR_USER/Projects/friday/bin/friday-hotkey
# Shortcut: Super+F
```

**KDE Plasma:**
```bash
# System Settings → Shortcuts → Custom Shortcuts → Add
# Trigger: Super+F
# Action: ~/Projects/friday/bin/friday-hotkey
```

**Any DE (generic):**
```bash
friday-install-keybind  # auto-detects and installs
```

### Step 10: Autostart (Optional)

```bash
# Create autostart entry
cat > ~/.config/autostart/friday-daemon.desktop << EOF
[Desktop Entry]
Type=Application
Name=Friday AI Daemon
Exec=$HOME/Projects/friday/start.sh --daemon
Terminal=false
EOF

# System tray icon
cat > ~/.config/autostart/friday-tray.desktop << EOF
[Desktop Entry]
Type=Application
Name=Friday AI Tray
Exec=$HOME/Projects/friday/bin/friday-tray
Terminal=false
EOF
```

### Step 11: Verify

```bash
friday doctor    # should show all green
friday status    # backend online, providers listed
friday-send "hello"  # should respond
```

---

## Part 2: Docker Containerization

### Architecture

```
HOST (your desktop):
├── friday (CLI)           ← native, for PATH commands
├── friday-tui             ← native, terminal UI
├── friday-send            ← native, talks to containerized backend
├── friday-gui             ← native, floating window
├── Desktop tools          ← native (brightness, volume, etc.)
└── Connects to ↓

DOCKER:
├── friday-backend         ← Python FastAPI (port 65535)
├── ollama                 ← GPU-accelerated LLM (port 11434)
└── (optional) mcp servers
```

### Directory Structure

```
friday/
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.core
│   └── docker-compose.yml
├── friday_ai/             ← mounted into backend container
├── config/                ← mounted as /config
└── ...
```

### Dockerfile.backend

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps for tools that work in container
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "."

COPY friday_ai/ ./friday_ai/
COPY config/ ./config/
COPY mcp_servers/ ./mcp_servers/

VOLUME ["/config", "/data"]

ENV FRIDAY_CONFIG_DIR=/config
ENV FRIDAY_DATA_DIR=/data

EXPOSE 65535

HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:65535/health || exit 1

CMD ["uvicorn", "friday_ai.server:app", \
     "--host", "0.0.0.0", "--port", "65535"]
```

### docker-compose.yml

```yaml
version: "3.9"

services:
  ollama:
    image: ollama/ollama:latest
    container_name: friday-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s

  ollama-init:
    image: ollama/ollama:latest
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      - OLLAMA_HOST=ollama:11434
    entrypoint: sh -c "ollama pull qwen2.5:7b && ollama pull qwen2.5:3b"
    restart: "no"

  backend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    container_name: friday-backend
    restart: unless-stopped
    ports:
      - "65535:65535"
    volumes:
      - ${HOME}/.config/friday:/config:ro
      - ${HOME}/.local/share/friday:/data
    environment:
      - FRIDAY_CONFIG_DIR=/config
      - FRIDAY_DATA_DIR=/data
      - OLLAMA_HOST=ollama
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
      - CLAUDE_API_KEY=${CLAUDE_API_KEY:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - SERPAPI_KEY=${SERPAPI_KEY:-}
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:65535/health"]
      interval: 30s
      timeout: 5s

volumes:
  ollama_data:
```

### Build & Run

```bash
# Create docker directory
mkdir -p docker
# Copy Dockerfiles from above

# Build
cd docker
docker compose build

# Start
docker compose up -d

# Check
docker compose ps
curl http://localhost:65535/health

# Pull models (first time)
docker compose run --rm ollama-init

# Logs
docker compose logs -f backend
```

### Host-Side Setup (CLI + Desktop Tools)

The `friday` CLI, TUI, and desktop tools run natively on the host. They talk to the containerized backend via `http://localhost:65535`.

```bash
# Ensure config points to localhost (default)
grep ollama_url ~/.config/friday/config.toml
# Should be: ollama_url = "http://localhost:11434"

# Test
friday status
friday-send "hello"
friday doctor
```

### Without GPU (CPU-only)

Remove the `deploy.resources` block from `ollama` in docker-compose.yml:

```yaml
  ollama:
    image: ollama/ollama:latest
    # Remove deploy section entirely
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
```

Ollama will use CPU. Slower (~30-60s per response) but works.

### Environment Variables

Create `.env` in the docker directory:

```bash
GEMINI_API_KEY=
CLAUDE_API_KEY=
OPENAI_API_KEY=
SERPAPI_KEY=your-key-here
```

---

## Part 3: Quick Reference

### Commands

```
friday                    Help menu
friday start --daemon     Start everything
friday stop               Stop everything
friday status             Check what's running
friday doctor             Diagnose issues
friday send <prompt>      Quick prompt
friday send search <q>    Google AI search
friday tui                Terminal UI
friday gui                Floating window
friday mode fallback      Local-first mode
friday mode race          Cloud race mode
friday mode google        Google AI mode
friday tools              List tools
friday mcp                List MCP servers
friday models             Manage Ollama models
friday memory             View/manage memories
friday config edit        Edit config
friday backup             Backup everything
friday update             Self-update
```

### File Locations

```
~/.config/friday/
├── config.toml           # main config
├── SOUL.md               # AI personality
├── USER.md               # user profile
├── AGENTS.md             # worker rules
├── mcp_servers.json      # MCP server registry
└── tools/plugins/        # custom tool plugins

~/.local/share/friday/
├── memory/
│   ├── MEMORY.md         # long-term memory
│   └── YYYY-MM-DD.md     # daily logs
├── history/              # conversation sessions
└── backups/              # friday backup output

~/Projects/friday/
├── friday_ai/            # Python backend
├── friday_core/          # Rust CLI/daemon
├── mcp_servers/          # 11 MCP servers
├── bin/                  # CLI scripts
├── config/               # default configs
└── docs/                 # documentation
```

### Ports

```
65535    Friday backend (FastAPI)
11434    Ollama (local LLM)
```

### Provider Priority

```
Fallback: Ollama → Claude CLI → Gemini CLI → Google AI → Browser
Race:     Chat/System → Ollama | Complex/Search → Cloud race
Google:   Everything → Google AI API
```
