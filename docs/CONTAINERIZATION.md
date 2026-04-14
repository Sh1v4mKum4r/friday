# Friday — Containerization Guide

## Overview

This document covers how to containerize Friday for:
1. **Portable deployment** — run Friday on any machine
2. **Docker Compose** — one command to start everything
3. **CI/CD** — automated testing and builds
4. **Distribution** — share Friday as a container image

## Architecture in Containers

```
┌─────────────────────────────────────────────────┐
│              docker-compose.yml                   │
│                                                   │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  friday-backend   │  │      ollama          │  │
│  │  (Python FastAPI) │  │  (Local LLM engine)  │  │
│  │  Port: 65535      │←→│  Port: 11434         │  │
│  │                   │  │  Model: qwen2.5:7b   │  │
│  └──────────────────┘  └──────────────────────┘  │
│           ↑                                       │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  friday-core      │  │  friday-mcp          │  │
│  │  (Rust CLI/Daemon)│  │  (MCP servers)       │  │
│  │  Socket + Panel   │  │  11 servers          │  │
│  └──────────────────┘  └──────────────────────┘  │
│                                                   │
│  Volumes:                                         │
│    ~/.config/friday → /config                     │
│    ~/.local/share/friday → /data                  │
└─────────────────────────────────────────────────┘
```

## Container Strategy

### Option A: Single Container (Simple)

One container with Python backend + Ollama + tools. Best for personal use.

### Option B: Multi-Container (Production)

Separate containers for backend, Ollama, MCP servers. Best for scalability.

**Recommendation: Option B** — Ollama should be its own container for GPU passthrough and model management.

---

## Dockerfiles

### 1. Python Backend (`docker/Dockerfile.backend`)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System dependencies for tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wl-clipboard \
    libnotify-bin \
    tesseract-ocr \
    tesseract-ocr-eng \
    grim \
    slurp \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[all]"

# Application code
COPY friday_ai/ ./friday_ai/
COPY config/ ./config/
COPY mcp_servers/ ./mcp_servers/

# Config and data volumes
VOLUME ["/config", "/data"]

ENV FRIDAY_CONFIG_DIR=/config
ENV FRIDAY_DATA_DIR=/data

EXPOSE 65535

HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:65535/health || exit 1

CMD ["uvicorn", "friday_ai.server:app", \
     "--host", "0.0.0.0", \
     "--port", "65535", \
     "--log-level", "info"]
```

### 2. Rust Core (`docker/Dockerfile.core`)

```dockerfile
FROM rust:1.82-slim AS builder

WORKDIR /app
COPY friday_core/ ./friday_core/

WORKDIR /app/friday_core
RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libnotify-bin \
    socat \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/friday_core/target/release/friday_core /usr/local/bin/friday_core

ENTRYPOINT ["friday_core"]
CMD ["--daemon"]
```

### 3. MCP Servers (`docker/Dockerfile.mcp`)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir mcp httpx

COPY mcp_servers/ ./mcp_servers/

# Each MCP server runs as a separate process
# Use docker-compose to start specific ones
CMD ["python", "-m", "http.server", "8080"]
```

---

## Docker Compose

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  # ─── Ollama (GPU-accelerated LLM engine) ───
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
      retries: 3

  # ─── Pull models on first start ───
  ollama-init:
    image: ollama/ollama:latest
    container_name: friday-ollama-init
    depends_on:
      ollama:
        condition: service_healthy
    entrypoint: >
      sh -c "
        ollama pull qwen2.5:7b;
        ollama pull qwen2.5:3b;
        echo 'Models ready'
      "
    environment:
      - OLLAMA_HOST=ollama:11434
    restart: "no"

  # ─── Friday Backend (FastAPI) ───
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    container_name: friday-backend
    restart: unless-stopped
    ports:
      - "65535:65535"
    volumes:
      - ./config:/config:ro
      - friday_data:/data
    environment:
      - FRIDAY_CONFIG_DIR=/config
      - FRIDAY_DATA_DIR=/data
      - OLLAMA_HOST=ollama
      # API keys (optional, uncomment and set)
      # - GEMINI_API_KEY=
      # - CLAUDE_API_KEY=
      # - OPENAI_API_KEY=
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:65535/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  # ─── Friday Rust Core (Daemon + Socket) ───
  core:
    build:
      context: .
      dockerfile: docker/Dockerfile.core
    container_name: friday-core
    restart: unless-stopped
    network_mode: host  # Needs host network for socket + notifications
    volumes:
      - ./config:/config:ro
      - /run/user/1000:/run/user/1000  # For Unix socket
    environment:
      - XDG_RUNTIME_DIR=/run/user/1000
      - WAYLAND_DISPLAY=${WAYLAND_DISPLAY}
      - DISPLAY=${DISPLAY}
    depends_on:
      backend:
        condition: service_healthy

volumes:
  ollama_data:
    name: friday-ollama-data
  friday_data:
    name: friday-data
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FRIDAY_CONFIG_DIR` | `~/.config/friday` | Config directory (SOUL.md, config.toml, etc.) |
| `FRIDAY_DATA_DIR` | `~/.local/share/friday` | Data directory (memory, history, sessions) |
| `OLLAMA_HOST` | `localhost` | Ollama server hostname |
| `GEMINI_API_KEY` | (empty) | Google Gemini API key |
| `CLAUDE_API_KEY` | (empty) | Anthropic Claude API key |
| `OPENAI_API_KEY` | (empty) | OpenAI API key |

---

## Code Changes Required

### 1. Config — Support Environment Variables for Paths

File: `friday_ai/config.py`

```python
import os

def get_config_dir() -> Path:
    return Path(os.environ.get("FRIDAY_CONFIG_DIR",
                               Path.home() / ".config" / "friday"))

def get_data_dir() -> Path:
    return Path(os.environ.get("FRIDAY_DATA_DIR",
                               Path.home() / ".local" / "share" / "friday"))
```

### 2. Ollama URL — Support Container Networking

File: `config/config.toml`

```toml
[providers]
# In Docker: ollama_url = "http://ollama:11434"
# On host:   ollama_url = "http://localhost:11434"
ollama_url = "http://localhost:11434"
```

Override in Docker via environment or mounted config.

### 3. Tool Paths — Handle Missing Binaries Gracefully

Tools like `wl-copy`, `notify-send`, `hyprctl` won't exist inside a minimal container. Each tool should check for binary existence and return a clear error instead of crashing:

```python
# Already done in most tools, verify all have this pattern:
if not shutil.which("wl-paste"):
    return "Error: wl-paste not found (not available in container)"
```

### 4. MCP Server Paths — Use Relative Paths

File: `~/.config/friday/mcp_servers.json`

Container paths differ from host paths. Use a volume mount or environment variable for the MCP server script directory.

---

## Build & Run

### Quick Start

```bash
# Clone
git clone https://github.com/Sh1v4mKum4r/friday.git
cd friday

# Create Docker directory
mkdir -p docker

# Copy Dockerfiles (create from templates above)
# Then:

# Build everything
docker compose build

# Start everything
docker compose up -d

# Check status
docker compose ps
docker compose logs -f backend

# Test
curl http://localhost:65535/health
curl -X POST http://localhost:65535/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

### GPU Support

NVIDIA GPU passthrough requires:
```bash
# Install NVIDIA Container Toolkit
sudo pacman -S nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Without GPU

Remove the `deploy.resources` section from `ollama` in docker-compose.yml. Ollama will run on CPU (slower but works).

---

## Volume Mounts

| Host Path | Container Path | Purpose |
|---|---|---|
| `~/.config/friday/` | `/config` | SOUL.md, USER.md, config.toml, mcp_servers.json |
| `~/.local/share/friday/` | `/data` | Memory, history, sessions, backups |
| Ollama models | `ollama_data` volume | Persistent model storage |

---

## CI/CD Pipeline

### GitHub Actions — `.github/workflows/ci.yml`

```yaml
name: Friday CI

on:
  push:
    branches: [main, feat/*]
  pull_request:
    branches: [main]

jobs:
  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest --tb=short -q

  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cd friday_core && cargo check

  build-docker:
    runs-on: ubuntu-latest
    needs: [test-python, test-rust]
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build
      - run: |
          docker compose up -d ollama backend
          sleep 10
          curl -f http://localhost:65535/health
```

---

## Publishing

### Docker Hub

```bash
# Tag and push
docker build -f docker/Dockerfile.backend -t sh4d0w/friday-backend:latest .
docker build -f docker/Dockerfile.core -t sh4d0w/friday-core:latest .
docker push sh4d0w/friday-backend:latest
docker push sh4d0w/friday-core:latest
```

### GitHub Container Registry

```bash
docker build -f docker/Dockerfile.backend -t ghcr.io/sh1v4mkum4r/friday-backend:latest .
docker push ghcr.io/sh1v4mkum4r/friday-backend:latest
```

---

## Security Considerations

1. **API keys** — Never bake into images. Use environment variables or Docker secrets.
2. **Tool execution** — `run_shell` tool can execute arbitrary commands. In a container, limit with:
   ```yaml
   security_opt:
     - no-new-privileges:true
   read_only: true
   tmpfs:
     - /tmp
   ```
3. **Network** — Only expose port 65535 to localhost, not 0.0.0.0 in production.
4. **GPU access** — Only the Ollama container needs GPU. Backend and core don't.

---

## Limitations in Container

| Feature | Container Status | Reason |
|---|---|---|
| CLI tools (brightness, volume, media) | Limited | No access to host hardware |
| Desktop control (de_command) | Not available | No Wayland/X11 in container |
| Screenshot, OCR | Not available | No display server |
| Mouse/keyboard control | Not available | No input devices |
| Notifications (notify-send) | Needs host network | Desktop notification bus |
| Unix socket (friday-send) | Needs host network | /run/user access |
| Clipboard | Not available | No Wayland clipboard |
| Ollama GPU | Works with nvidia-container-toolkit | GPU passthrough |

**Recommendation:** Run the backend and Ollama in containers, but keep the Rust core and desktop tools on the host for full functionality.

---

## Hybrid Setup (Recommended)

```
HOST MACHINE:
  ├── friday-core (Rust binary, native)
  ├── friday-tui (native terminal)
  ├── friday-send (native script)
  ├── Desktop tools (brightness, volume, etc.)
  └── Connects to containerized backend ↓

DOCKER:
  ├── friday-backend (Python FastAPI)
  ├── ollama (with GPU passthrough)
  └── MCP servers (optional)
```

This gives you:
- Full desktop integration (tools, notifications, clipboard, DE control)
- Isolated backend (easy to update, portable, reproducible)
- GPU-accelerated Ollama (managed separately from host packages)
- Portable config via volume mounts
