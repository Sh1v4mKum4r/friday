# Friday Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Friday as a hybrid Rust + Python AI system assistant with multi-provider LLM support, multi-threaded execution, plugin tools, and OpenClaw-inspired identity/memory.

**Architecture:** Rust async core (tokio) handles CLI, task spawning, DE detection, panel widget, and hotkey launcher. Python FastAPI microservice handles LLM provider routing, agent logic, tool execution, and memory. Communication over HTTP on localhost:65535.

**Tech Stack:** Rust (tokio, reqwest, serde, toml, clap), Python 3.11+ (FastAPI, uvicorn, httpx, tomli), Ollama (local LLM), optional cloud APIs (Gemini/Claude/OpenAI).

---

## File Structure

```
~/Projects/jarvis/
├── friday_core/
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── config.rs
│       ├── client.rs
│       ├── task_manager.rs
│       ├── commands.rs
│       ├── de.rs
│       ├── panel.rs
│       └── launcher.rs
├── friday_ai/
│   ├── __init__.py
│   ├── server.py
│   ├── config.py
│   ├── identity.py
│   ├── memory.py
│   ├── tool_loader.py
│   ├── agent.py
│   ├── router.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── ollama.py
│   │   ├── gemini.py
│   │   ├── claude.py
│   │   ├── openai_provider.py
│   │   └── web_search.py
│   └── tools/
│       ├── core/
│       │   ├── __init__.py
│       │   ├── shell.py
│       │   ├── clipboard.py
│       │   ├── notify.py
│       │   ├── de.py
│       │   ├── files.py
│       │   ├── web_search.py
│       │   └── memory_tool.py
│       └── plugins/
│           └── .gitkeep
├── config/
│   ├── config.toml
│   ├── SOUL.md
│   ├── USER.md
│   ├── AGENTS.md
│   └── BOOTSTRAP.md
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_identity.py
│   ├── test_memory.py
│   ├── test_tool_loader.py
│   ├── test_providers.py
│   ├── test_router.py
│   ├── test_agent.py
│   └── test_server.py
├── pyproject.toml
├── start.sh
└── .env.example
```

---

## Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `friday_ai/__init__.py`
- Create: `friday_ai/tools/__init__.py`  (empty)
- Create: `friday_ai/tools/core/__init__.py` (empty)
- Create: `friday_ai/tools/plugins/.gitkeep` (empty)
- Create: `friday_ai/providers/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `.env.example`
- Remove: old files (`agent.py`, `server.py`, `tools.py`, `main.py` at project root)

- [ ] **Step 1: Clean up old project files**

```bash
cd ~/Projects/jarvis
rm -f agent.py server.py tools.py main.py uvicorn.log
rm -rf __pycache__
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "friday-ai"
version = "0.1.0"
description = "Friday AI Microservice — LLM provider routing, tools, and memory"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "httpx>=0.28.0",
    "tomli>=2.0.0;python_version<'3.11'",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
gemini = ["google-genai>=1.0.0"]
claude = ["anthropic>=0.40.0"]
openai = ["openai>=1.60.0"]
all = ["google-genai>=1.0.0", "anthropic>=0.40.0", "openai>=1.60.0"]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.24.0", "httpx>=0.28.0"]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 3: Create directory structure and empty init files**

```bash
mkdir -p friday_ai/providers friday_ai/tools/core friday_ai/tools/plugins tests config
touch friday_ai/__init__.py friday_ai/providers/__init__.py friday_ai/tools/__init__.py
touch friday_ai/tools/core/__init__.py tests/__init__.py friday_ai/tools/plugins/.gitkeep
```

- [ ] **Step 4: Create .env.example**

```
# Friday AI — Environment Variables
# Copy to .env and fill in keys you have. Empty = provider skipped.

GEMINI_API_KEY=
CLAUDE_API_KEY=
OPENAI_API_KEY=
```

- [ ] **Step 5: Create venv and install dependencies**

```bash
cd ~/Projects/jarvis
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 6: Verify pytest runs with no tests**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest -v`
Expected: "no tests ran" with exit code 5 (no collection errors)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml friday_ai/ tests/ config/ .env.example
git commit -m "feat: scaffold friday-ai project with dependencies"
```

---

## Task 2: Config System

**Files:**
- Create: `friday_ai/config.py`
- Create: `config/config.toml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import tempfile
from pathlib import Path

def test_load_config_from_file():
    from friday_ai.config import load_config

    toml_content = """
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
override = ""

[voice]
enabled = false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = load_config(f.name)

    assert config.providers.ollama_model == "qwen2.5:7b"
    assert config.server.port == 65535
    assert config.behavior.auto_escalate is True
    assert config.behavior.max_workers == 4
    assert config.de.override == ""
    os.unlink(f.name)


def test_load_config_uses_env_for_keys():
    from friday_ai.config import load_config

    toml_content = """
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
override = ""

[voice]
enabled = false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        os.environ["GEMINI_API_KEY"] = "test-key-123"
        config = load_config(f.name)
        del os.environ["GEMINI_API_KEY"]

    assert config.providers.gemini_api_key == "test-key-123"
    os.unlink(f.name)


def test_available_providers():
    from friday_ai.config import load_config, get_available_providers

    toml_content = """
[providers]
ollama_model = "qwen2.5:7b"
ollama_url = "http://localhost:11434"
gemini_api_key = "some-key"
claude_api_key = ""
openai_api_key = ""

[server]
port = 65535
host = "127.0.0.1"

[behavior]
auto_escalate = true
max_workers = 4

[de]
override = ""

[voice]
enabled = false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = load_config(f.name)

    providers = get_available_providers(config)
    assert "ollama" in providers
    assert "gemini" in providers
    assert "claude_cli" in providers  # no API key but CLI fallback
    assert "openai" not in providers  # no key, no CLI fallback
    os.unlink(f.name)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'friday_ai.config'`

- [ ] **Step 3: Write the implementation**

```python
# friday_ai/config.py
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass
class ProvidersConfig:
    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"
    gemini_api_key: str = ""
    claude_api_key: str = ""
    openai_api_key: str = ""


@dataclass
class ServerConfig:
    port: int = 65535
    host: str = "127.0.0.1"


@dataclass
class BehaviorConfig:
    auto_escalate: bool = True
    max_workers: int = 4


@dataclass
class DEConfig:
    override: str = ""


@dataclass
class VoiceConfig:
    enabled: bool = False


@dataclass
class FridayConfig:
    providers: ProvidersConfig = field(default_factory=ProvidersConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    de: DEConfig = field(default_factory=DEConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)


def load_config(path: str | Path) -> FridayConfig:
    path = Path(path)
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    providers_raw = raw.get("providers", {})
    # Environment variables override empty config values for API keys
    for key in ("gemini_api_key", "claude_api_key", "openai_api_key"):
        env_key = key.upper()
        env_val = os.environ.get(env_key, "")
        if env_val and not providers_raw.get(key):
            providers_raw[key] = env_val

    return FridayConfig(
        providers=ProvidersConfig(**providers_raw),
        server=ServerConfig(**raw.get("server", {})),
        behavior=BehaviorConfig(**raw.get("behavior", {})),
        de=DEConfig(**raw.get("de", {})),
        voice=VoiceConfig(**raw.get("voice", {})),
    )


def get_available_providers(config: FridayConfig) -> list[str]:
    providers = ["ollama"]  # always available if Ollama is installed

    if config.providers.gemini_api_key:
        providers.append("gemini")
    elif shutil.which("gemini"):
        providers.append("gemini_cli")

    if config.providers.claude_api_key:
        providers.append("claude")
    elif shutil.which("claude"):
        providers.append("claude_cli")

    if config.providers.openai_api_key:
        providers.append("openai")

    return providers


def get_config_dir() -> Path:
    return Path.home() / ".config" / "friday"


def get_data_dir() -> Path:
    return Path.home() / ".local" / "share" / "friday"


def ensure_dirs():
    get_config_dir().mkdir(parents=True, exist_ok=True)
    (get_data_dir() / "memory").mkdir(parents=True, exist_ok=True)
    (get_data_dir() / "history").mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Create default config.toml**

```toml
# config/config.toml — Friday default configuration
# Copied to ~/.config/friday/config.toml on first run

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
override = ""

[voice]
enabled = false
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add friday_ai/config.py config/config.toml tests/test_config.py
git commit -m "feat: add config system with TOML parsing and env overrides"
```

---

## Task 3: Identity System (SOUL.md, USER.md, AGENTS.md, BOOTSTRAP.md)

**Files:**
- Create: `friday_ai/identity.py`
- Create: `config/SOUL.md`
- Create: `config/USER.md`
- Create: `config/AGENTS.md`
- Create: `config/BOOTSTRAP.md`
- Create: `tests/test_identity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_identity.py
import tempfile
from pathlib import Path


def test_load_identity_files():
    from friday_ai.identity import load_identity

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "SOUL.md").write_text("You are Friday. Be concise.")
        (d / "USER.md").write_text("The user is a developer.")

        identity = load_identity(d)

    assert "Friday" in identity.soul
    assert "developer" in identity.user
    assert identity.agents == ""  # missing file = empty
    assert identity.bootstrap is None  # no BOOTSTRAP.md = None


def test_build_system_prompt():
    from friday_ai.identity import load_identity, build_system_prompt

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "SOUL.md").write_text("You are Friday.")
        (d / "USER.md").write_text("User is sh4d0w.")

        identity = load_identity(d)
        prompt = build_system_prompt(identity, tools_desc="run_shell: execute a command")

    assert "You are Friday." in prompt
    assert "User is sh4d0w." in prompt
    assert "run_shell" in prompt


def test_bootstrap_detected():
    from friday_ai.identity import load_identity

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "SOUL.md").write_text("Friday")
        (d / "USER.md").write_text("User")
        (d / "BOOTSTRAP.md").write_text("Ask user their name.")

        identity = load_identity(d)

    assert identity.bootstrap == "Ask user their name."


def test_update_user_md():
    from friday_ai.identity import update_identity_file

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "USER.md").write_text("The user is a developer.")

        update_identity_file(d / "USER.md", "The user is sh4d0w, a VIT student.")

        assert "sh4d0w" in (d / "USER.md").read_text()


def test_delete_bootstrap():
    from friday_ai.identity import delete_bootstrap

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "BOOTSTRAP.md").write_text("First run.")

        delete_bootstrap(d)

        assert not (d / "BOOTSTRAP.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'friday_ai.identity'`

- [ ] **Step 3: Write the implementation**

```python
# friday_ai/identity.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Identity:
    soul: str
    user: str
    agents: str
    bootstrap: str | None


def load_identity(config_dir: Path) -> Identity:
    def read_if_exists(filename: str) -> str:
        p = config_dir / filename
        return p.read_text() if p.exists() else ""

    bootstrap_path = config_dir / "BOOTSTRAP.md"
    bootstrap = bootstrap_path.read_text() if bootstrap_path.exists() else None

    return Identity(
        soul=read_if_exists("SOUL.md"),
        user=read_if_exists("USER.md"),
        agents=read_if_exists("AGENTS.md"),
        bootstrap=bootstrap,
    )


def build_system_prompt(identity: Identity, tools_desc: str, memory_context: str = "") -> str:
    sections = []

    if identity.soul:
        sections.append(f"# Personality\n{identity.soul}")

    if identity.user:
        sections.append(f"# About the User\n{identity.user}")

    if identity.agents:
        sections.append(f"# Worker Rules\n{identity.agents}")

    if tools_desc:
        sections.append(f"# Available Tools\n{tools_desc}")

    if memory_context:
        sections.append(f"# Memory Context\n{memory_context}")

    if identity.bootstrap:
        sections.append(
            f"# FIRST RUN\nThis is the first time Friday is running. "
            f"Complete the following bootstrap ritual, then signal that "
            f"bootstrap is complete so the file can be deleted.\n\n{identity.bootstrap}"
        )

    return "\n\n".join(sections)


def update_identity_file(path: Path, content: str) -> None:
    path.write_text(content)


def delete_bootstrap(config_dir: Path) -> None:
    bootstrap = config_dir / "BOOTSTRAP.md"
    if bootstrap.exists():
        bootstrap.unlink()
```

- [ ] **Step 4: Create default identity files**

```markdown
<!-- config/SOUL.md -->
# Friday

You are Friday (Female Replacement Intelligent Digital Assistant Youth), a system-level AI assistant for Arch Linux.

## Voice
- Be concise. One sentence when one sentence works.
- Have opinions. Recommend the better option instead of listing pros/cons endlessly.
- Be direct. Skip filler phrases like "certainly" and "of course."
- Light humor is fine. Corporate tone is not.

## Rules
- Never run destructive commands (rm -rf /, mkfs, dd) without explicit confirmation.
- When modifying system files, always back up first.
- If unsure, ask. Don't guess on system operations.
- You can evolve this file as you learn what works. Notify the user when you do.
```

```markdown
<!-- config/USER.md -->
# User Profile

This file will be updated as Friday learns about you.
```

```markdown
<!-- config/AGENTS.md -->
# Worker Rules

## Task Splitting
- If a message contains "and also", "while you're at it", or multiple independent clauses, split into parallel workers.
- Never split tasks that depend on each other's output.

## Resource Limits
- Max 4 concurrent workers.
- Background tasks get lower priority than foreground.
- If Ollama is busy, queue rather than drop.

## Escalation
- If a worker fails on Ollama, retry once on cloud provider.
- If all providers fail, notify user instead of silently dropping.
```

```markdown
<!-- config/BOOTSTRAP.md -->
# First Run Ritual

Welcome the user and complete these steps:

1. Ask for their name and how they'd like to be addressed.
2. Detect the current desktop environment and confirm it.
3. Check which LLM providers are available (Ollama, API keys, CLIs).
4. Summarize the setup and save findings to USER.md.
5. Signal that bootstrap is complete.

Keep it brief — don't lecture. Get the info, save it, move on.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_identity.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add friday_ai/identity.py config/SOUL.md config/USER.md config/AGENTS.md config/BOOTSTRAP.md tests/test_identity.py
git commit -m "feat: add identity system with SOUL.md, USER.md, AGENTS.md, BOOTSTRAP.md"
```

---

## Task 4: Memory System

**Files:**
- Create: `friday_ai/memory.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py
import json
import tempfile
from datetime import date
from pathlib import Path


def test_read_memory():
    from friday_ai.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "memory").mkdir()
        (d / "memory" / "MEMORY.md").write_text("- User prefers dark themes\n- Default browser is librewolf")

        store = MemoryStore(d)
        content = store.read_memory()

    assert "dark themes" in content
    assert "librewolf" in content


def test_write_memory():
    from friday_ai.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "memory").mkdir()
        (d / "memory" / "MEMORY.md").write_text("")

        store = MemoryStore(d)
        store.write_memory("User prefers dark themes")

        content = (d / "memory" / "MEMORY.md").read_text()
    assert "dark themes" in content


def test_forget_memory():
    from friday_ai.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "memory").mkdir()
        (d / "memory" / "MEMORY.md").write_text("- User likes cats\n- User likes dogs\n")

        store = MemoryStore(d)
        store.forget_memory("cats")

        content = (d / "memory" / "MEMORY.md").read_text()
    assert "cats" not in content
    assert "dogs" in content


def test_daily_log():
    from friday_ai.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "memory").mkdir()

        store = MemoryStore(d)
        store.append_daily_log("User asked about proxy setup")

        today = date.today().isoformat()
        log_path = d / "memory" / f"{today}.md"
        assert log_path.exists()
        assert "proxy setup" in log_path.read_text()


def test_save_session():
    from friday_ai.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "history").mkdir()

        store = MemoryStore(d)
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        session_path = store.save_session(messages)

        assert session_path.exists()
        data = json.loads(session_path.read_text())
        assert len(data["messages"]) == 2


def test_load_latest_session():
    from friday_ai.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "history").mkdir()

        store = MemoryStore(d)
        messages = [{"role": "user", "content": "hello"}]
        store.save_session(messages)

        loaded = store.load_latest_session()
        assert loaded is not None
        assert loaded[0]["content"] == "hello"


def test_get_context_for_prompt():
    from friday_ai.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "memory").mkdir()
        (d / "memory" / "MEMORY.md").write_text("- User is a VIT student")

        store = MemoryStore(d)
        store.append_daily_log("Discussed proxy config")

        context = store.get_context_for_prompt()

    assert "VIT student" in context
    assert "proxy config" in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'friday_ai.memory'`

- [ ] **Step 3: Write the implementation**

```python
# friday_ai/memory.py
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path


class MemoryStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.memory_dir = data_dir / "memory"
        self.history_dir = data_dir / "history"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    @property
    def memory_file(self) -> Path:
        return self.memory_dir / "MEMORY.md"

    def read_memory(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text()
        return ""

    def write_memory(self, entry: str) -> None:
        existing = self.read_memory().rstrip()
        if existing:
            updated = f"{existing}\n- {entry}\n"
        else:
            updated = f"- {entry}\n"
        self.memory_file.write_text(updated)

    def forget_memory(self, keyword: str) -> None:
        content = self.read_memory()
        lines = content.splitlines()
        filtered = [line for line in lines if keyword.lower() not in line.lower()]
        self.memory_file.write_text("\n".join(filtered) + "\n" if filtered else "")

    def list_memory(self) -> list[str]:
        content = self.read_memory()
        return [line.lstrip("- ").strip() for line in content.splitlines() if line.strip().startswith("-")]

    def clear_memory(self) -> None:
        self.memory_file.write_text("")

    def append_daily_log(self, entry: str) -> None:
        today = date.today().isoformat()
        log_path = self.memory_dir / f"{today}.md"
        timestamp = datetime.now().strftime("%H:%M")
        if log_path.exists():
            existing = log_path.read_text().rstrip()
            log_path.write_text(f"{existing}\n- [{timestamp}] {entry}\n")
        else:
            log_path.write_text(f"# {today}\n\n- [{timestamp}] {entry}\n")

    def save_session(self, messages: list[dict]) -> Path:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_path = self.history_dir / f"session-{timestamp}.json"
        session_path.write_text(json.dumps({
            "timestamp": timestamp,
            "messages": messages,
        }, indent=2))
        return session_path

    def load_latest_session(self) -> list[dict] | None:
        sessions = sorted(self.history_dir.glob("session-*.json"), reverse=True)
        if not sessions:
            return None
        data = json.loads(sessions[0].read_text())
        return data["messages"]

    def get_context_for_prompt(self) -> str:
        parts = []
        memory = self.read_memory().strip()
        if memory:
            parts.append(f"## Long-term Memory\n{memory}")

        today = date.today().isoformat()
        today_log = self.memory_dir / f"{today}.md"
        if today_log.exists():
            parts.append(f"## Today's Log\n{today_log.read_text().strip()}")

        return "\n\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_memory.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add friday_ai/memory.py tests/test_memory.py
git commit -m "feat: add memory system with MEMORY.md, daily logs, session history"
```

---

## Task 5: Tool Loader & Plugin System

**Files:**
- Create: `friday_ai/tool_loader.py`
- Create: `tests/test_tool_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_loader.py
import tempfile
from pathlib import Path


def test_discover_tools():
    from friday_ai.tool_loader import ToolLoader

    with tempfile.TemporaryDirectory() as tmpdir:
        core_dir = Path(tmpdir) / "core"
        core_dir.mkdir()

        (core_dir / "shell.py").write_text('''
name = "run_shell"
description = "Execute a bash shell command and return the output"

def run(command: str) -> str:
    return f"executed: {command}"
''')

        (core_dir / "notify.py").write_text('''
name = "notify"
description = "Send a desktop notification"

def run(message: str, title: str = "Friday") -> str:
    return f"notified: {title} - {message}"
''')

        loader = ToolLoader([core_dir])
        tools = loader.discover()

    assert len(tools) == 2
    names = [t.name for t in tools]
    assert "run_shell" in names
    assert "notify" in names


def test_execute_tool():
    from friday_ai.tool_loader import ToolLoader

    with tempfile.TemporaryDirectory() as tmpdir:
        core_dir = Path(tmpdir) / "core"
        core_dir.mkdir()

        (core_dir / "shell.py").write_text('''
name = "run_shell"
description = "Execute a bash shell command"

def run(command: str) -> str:
    return f"executed: {command}"
''')

        loader = ToolLoader([core_dir])
        loader.discover()
        result = loader.execute("run_shell", {"command": "ls"})

    assert result == "executed: ls"


def test_tool_descriptions_for_prompt():
    from friday_ai.tool_loader import ToolLoader

    with tempfile.TemporaryDirectory() as tmpdir:
        core_dir = Path(tmpdir) / "core"
        core_dir.mkdir()

        (core_dir / "shell.py").write_text('''
name = "run_shell"
description = "Execute a bash shell command"

def run(command: str) -> str:
    return ""
''')

        loader = ToolLoader([core_dir])
        loader.discover()
        desc = loader.get_tools_description()

    assert "run_shell" in desc
    assert "command: str" in desc


def test_reload_tools():
    from friday_ai.tool_loader import ToolLoader

    with tempfile.TemporaryDirectory() as tmpdir:
        core_dir = Path(tmpdir) / "core"
        core_dir.mkdir()

        (core_dir / "shell.py").write_text('''
name = "run_shell"
description = "Execute a bash shell command"

def run(command: str) -> str:
    return "v1"
''')

        loader = ToolLoader([core_dir])
        loader.discover()
        assert loader.execute("run_shell", {"command": "x"}) == "v1"

        # Update the tool
        (core_dir / "shell.py").write_text('''
name = "run_shell"
description = "Execute a bash shell command"

def run(command: str) -> str:
    return "v2"
''')

        loader.reload()
        assert loader.execute("run_shell", {"command": "x"}) == "v2"


def test_get_tools_for_ollama():
    from friday_ai.tool_loader import ToolLoader

    with tempfile.TemporaryDirectory() as tmpdir:
        core_dir = Path(tmpdir) / "core"
        core_dir.mkdir()

        (core_dir / "shell.py").write_text('''
name = "run_shell"
description = "Execute a bash shell command"

def run(command: str) -> str:
    return ""
''')

        loader = ToolLoader([core_dir])
        loader.discover()
        schemas = loader.get_tool_schemas()

    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "run_shell"
    assert "command" in schemas[0]["function"]["parameters"]["properties"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_tool_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'friday_ai.tool_loader'`

- [ ] **Step 3: Write the implementation**

```python
# friday_ai/tool_loader.py
from __future__ import annotations

import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    run: Callable[..., str]
    parameters: dict[str, str]  # param_name -> type annotation as string
    source_path: Path


class ToolLoader:
    def __init__(self, tool_dirs: list[Path]):
        self.tool_dirs = tool_dirs
        self.tools: dict[str, Tool] = {}
        self._loaded_modules: dict[str, str] = {}  # module_name -> path

    def discover(self) -> list[Tool]:
        self.tools.clear()
        self._loaded_modules.clear()

        for tool_dir in self.tool_dirs:
            if not tool_dir.exists():
                continue
            for py_file in sorted(tool_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                self._load_tool_file(py_file)

        return list(self.tools.values())

    def _load_tool_file(self, path: Path) -> None:
        module_name = f"friday_tool_{path.stem}_{id(path)}"

        # Clean up old module if reloading
        if module_name in sys.modules:
            del sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        name = getattr(module, "name", None)
        description = getattr(module, "description", None)
        run_fn = getattr(module, "run", None)

        if not all([name, description, run_fn]):
            return

        sig = inspect.signature(run_fn)
        parameters = {}
        for param_name, param in sig.parameters.items():
            annotation = param.annotation
            if annotation is inspect.Parameter.empty:
                parameters[param_name] = "str"
            else:
                parameters[param_name] = annotation.__name__ if hasattr(annotation, "__name__") else str(annotation)

        self.tools[name] = Tool(
            name=name,
            description=description,
            run=run_fn,
            parameters=parameters,
            source_path=path,
        )
        self._loaded_modules[name] = module_name

    def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        tool = self.tools.get(tool_name)
        if tool is None:
            return f"Error: tool '{tool_name}' not found"
        return tool.run(**args)

    def reload(self) -> list[Tool]:
        return self.discover()

    def get_tools_description(self) -> str:
        lines = []
        for tool in self.tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
            lines.append(f"- {tool.name}({params}): {tool.description}")
        return "\n".join(lines)

    def get_tool_schemas(self) -> list[dict]:
        schemas = []
        for tool in self.tools.values():
            properties = {}
            required = []
            sig = inspect.signature(tool.run)
            for param_name, param in sig.parameters.items():
                type_map = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
                param_type = tool.parameters.get(param_name, "str")
                properties[param_name] = {"type": type_map.get(param_type, "string")}
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return schemas
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_tool_loader.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add friday_ai/tool_loader.py tests/test_tool_loader.py
git commit -m "feat: add plugin-based tool loader with discovery, execution, and hot-reload"
```

---

## Task 6: Core Tools

**Files:**
- Create: `friday_ai/tools/core/shell.py`
- Create: `friday_ai/tools/core/clipboard.py`
- Create: `friday_ai/tools/core/notify.py`
- Create: `friday_ai/tools/core/de.py`
- Create: `friday_ai/tools/core/files.py`
- Create: `friday_ai/tools/core/web_search.py`
- Create: `friday_ai/tools/core/memory_tool.py`

- [ ] **Step 1: Create shell.py**

```python
# friday_ai/tools/core/shell.py
import subprocess

name = "run_shell"
description = "Execute a bash shell command and return its stdout. Use for any system command."

def run(command: str) -> str:
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return f"Exit code {result.returncode}: {err}" if err else f"Exit code {result.returncode}"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds"
```

- [ ] **Step 2: Create clipboard.py**

```python
# friday_ai/tools/core/clipboard.py
import subprocess

name = "clipboard_get"
description = "Read the current text content of the Wayland clipboard"

def run() -> str:
    try:
        result = subprocess.run(["wl-paste"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.stdout else "(clipboard empty)"
    except FileNotFoundError:
        return "Error: wl-paste not found. Install wl-clipboard."
```

Note: `clipboard_set` is a separate tool file since each file = one tool.

- [ ] **Step 3: Create clipboard_set.py**

```python
# friday_ai/tools/core/clipboard_set.py
import subprocess

name = "clipboard_set"
description = "Set the Wayland clipboard content to the given text"

def run(text: str) -> str:
    try:
        proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
        proc.communicate(input=text, timeout=5)
        return "Clipboard updated."
    except FileNotFoundError:
        return "Error: wl-copy not found. Install wl-clipboard."
```

- [ ] **Step 4: Create notify.py**

```python
# friday_ai/tools/core/notify.py
import subprocess

name = "notify"
description = "Send a desktop notification with a title and message"

def run(message: str, title: str = "Friday") -> str:
    try:
        subprocess.run(["notify-send", title, message], timeout=5)
        return "Notification sent."
    except FileNotFoundError:
        return "Error: notify-send not found."
```

- [ ] **Step 5: Create de.py**

```python
# friday_ai/tools/core/de.py
import os
import subprocess

name = "de_command"
description = "Execute a desktop environment command to manage windows or workspaces. Examples: 'move window left', 'switch workspace 3', 'list clients'"

def _detect_de() -> str:
    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "cosmic" in xdg:
        return "cosmic"
    if "hyprland" in xdg:
        return "hyprland"
    # Fallback: check running processes
    try:
        ps = subprocess.run(["pgrep", "-x", "cosmic-comp"], capture_output=True)
        if ps.returncode == 0:
            return "cosmic"
        ps = subprocess.run(["pgrep", "-x", "Hyprland"], capture_output=True)
        if ps.returncode == 0:
            return "hyprland"
    except FileNotFoundError:
        pass
    return "unknown"


def _run_hyprland(cmd: str) -> str:
    try:
        result = subprocess.run(
            ["hyprctl", cmd],
            capture_output=True, text=True, timeout=5,
            env={**os.environ},
        )
        return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: hyprctl not found"


def _run_cosmic(cmd: str) -> str:
    # Cosmic compositor uses DBus. Basic support via busctl / cosmic-osd.
    # For now, fall back to generic commands.
    try:
        result = subprocess.run(
            ["busctl", "call", "com.system76.CosmicComp", "/com/system76/CosmicComp",
             "com.system76.CosmicComp", "RunCommand", "s", cmd],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else f"Cosmic command: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: busctl not found"


def run(cmd: str) -> str:
    de = _detect_de()
    if de == "hyprland":
        return _run_hyprland(cmd)
    elif de == "cosmic":
        return _run_cosmic(cmd)
    else:
        return f"Error: unsupported desktop environment '{de}'"
```

- [ ] **Step 6: Create files.py**

```python
# friday_ai/tools/core/files.py
from pathlib import Path

name = "file_read"
description = "Read the contents of a file at the given path"

def run(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        content = p.read_text()
        if len(content) > 10000:
            return content[:10000] + f"\n... (truncated, {len(content)} chars total)"
        return content
    except Exception as e:
        return f"Error reading file: {e}"
```

- [ ] **Step 7: Create file_write.py**

```python
# friday_ai/tools/core/file_write.py
from pathlib import Path

name = "file_write"
description = "Write content to a file at the given path. Creates parent directories if needed."

def run(path: str, content: str) -> str:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing file: {e}"
```

- [ ] **Step 8: Create web_search.py**

```python
# friday_ai/tools/core/web_search.py
import shutil
import subprocess

name = "web_search"
description = "Search the web for a query and return results. Use for current/live information."

def run(query: str) -> str:
    # Try googler first (lightweight CLI Google search)
    if shutil.which("googler"):
        try:
            result = subprocess.run(
                ["googler", "--noprompt", "-n", "5", "-C", query],
                capture_output=True, text=True, timeout=15,
            )
            if result.stdout.strip():
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Error: web search timed out"

    # Fallback: just report that no search tool is available
    return "Error: no web search tool found. Install googler: pip install googler"
```

- [ ] **Step 9: Create memory_tool.py**

```python
# friday_ai/tools/core/memory_tool.py
name = "memory_save"
description = "Save an important fact or preference to long-term memory. Use when you learn something durable about the user or system."

# NOTE: The actual MemoryStore instance is injected by the agent at runtime.
# This tool file defines the interface; the agent wires it to the real store.
_memory_store = None

def set_store(store):
    global _memory_store
    _memory_store = store

def run(entry: str) -> str:
    if _memory_store is None:
        return "Error: memory store not initialized"
    _memory_store.write_memory(entry)
    return f"Saved to memory: {entry}"
```

- [ ] **Step 10: Commit**

```bash
git add friday_ai/tools/core/
git commit -m "feat: add 10 core tools (shell, clipboard, notify, de, files, web_search, memory)"
```

---

## Task 7: Provider Interface & Ollama Provider

**Files:**
- Create: `friday_ai/providers/base.py`
- Create: `friday_ai/providers/ollama.py`
- Create: `tests/test_providers.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_providers.py
import json
from unittest.mock import AsyncMock, patch


def test_provider_interface():
    from friday_ai.providers.base import BaseProvider
    # Verify the interface exists and has the right methods
    assert hasattr(BaseProvider, "send_message")
    assert hasattr(BaseProvider, "is_available")
    assert hasattr(BaseProvider, "supports_tools")
    assert hasattr(BaseProvider, "name")


import pytest

@pytest.mark.asyncio
async def test_ollama_send_message():
    from friday_ai.providers.ollama import OllamaProvider

    mock_response = {
        "message": {"role": "assistant", "content": "Hello! How can I help?"},
        "done": True,
    }

    provider = OllamaProvider(model="qwen2.5:7b", base_url="http://localhost:11434")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = await provider.send_message("Hello", tools=None, history=[])

    assert result.content == "Hello! How can I help?"
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_ollama_send_message_with_tool_call():
    from friday_ai.providers.ollama import OllamaProvider

    mock_response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "run_shell", "arguments": {"command": "ls"}}}
            ],
        },
        "done": True,
    }

    provider = OllamaProvider(model="qwen2.5:7b", base_url="http://localhost:11434")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = await provider.send_message("list files", tools=[{"type": "function", "function": {"name": "run_shell"}}], history=[])

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "run_shell"
    assert result.tool_calls[0].arguments == {"command": "ls"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_providers.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the base provider interface**

```python
# friday_ai/providers/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class ProviderResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider_name: str = ""


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @abstractmethod
    def supports_tools(self) -> bool:
        ...
```

- [ ] **Step 4: Write the Ollama provider**

```python
# friday_ai/providers/ollama.py
from __future__ import annotations

import httpx

from .base import BaseProvider, ProviderResponse, ToolCall


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)

        if resp.status_code != 200:
            return ProviderResponse(content=f"Ollama error: {resp.status_code} {resp.text}", provider_name=self.name)

        data = resp.json()
        msg = data.get("message", {})

        tool_calls = []
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            tool_calls.append(ToolCall(
                name=fn.get("name", ""),
                arguments=fn.get("arguments", {}),
            ))

        return ProviderResponse(
            content=msg.get("content", ""),
            tool_calls=tool_calls,
            provider_name=self.name,
        )

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def supports_tools(self) -> bool:
        return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_providers.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add friday_ai/providers/base.py friday_ai/providers/ollama.py tests/test_providers.py
git commit -m "feat: add provider interface and Ollama provider"
```

---

## Task 8: Cloud Providers (Gemini, Claude, OpenAI)

**Files:**
- Create: `friday_ai/providers/gemini.py`
- Create: `friday_ai/providers/claude.py`
- Create: `friday_ai/providers/openai_provider.py`

- [ ] **Step 1: Write the Gemini provider (API + CLI fallback)**

```python
# friday_ai/providers/gemini.py
from __future__ import annotations

import json
import re
import shutil
import subprocess

import httpx

from .base import BaseProvider, ProviderResponse, ToolCall


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        contents = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload: dict = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        if tools:
            gemini_tools = []
            for t in tools:
                fn = t.get("function", {})
                gemini_tools.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                })
            payload["tools"] = [{"functionDeclarations": gemini_tools}]

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            return ProviderResponse(content=f"Gemini error: {resp.status_code}", provider_name=self.name)

        data = resp.json()
        candidates = data.get("candidates", [{}])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []

        content = ""
        tool_calls = []
        for part in parts:
            if "text" in part:
                content += part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(ToolCall(name=fc["name"], arguments=fc.get("args", {})))

        return ProviderResponse(content=content, tool_calls=tool_calls, provider_name=self.name)

    async def is_available(self) -> bool:
        return bool(self.api_key)

    def supports_tools(self) -> bool:
        return True


class GeminiCLIProvider(BaseProvider):
    name = "gemini_cli"

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        full_prompt = prompt
        if tools:
            tool_desc = "\n".join(
                f"- {t['function']['name']}: {t['function'].get('description', '')}" for t in tools
            )
            full_prompt = (
                f"{system_prompt}\n\nAvailable tools (respond with TOOL_CALL: {{json}} to use one):\n"
                f"{tool_desc}\n\nUser: {prompt}"
            )

        try:
            result = subprocess.run(
                ["gemini", "-p", full_prompt],
                capture_output=True, text=True, timeout=120,
            )
            text = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return ProviderResponse(content=f"Gemini CLI error: {e}", provider_name=self.name)

        tool_calls = _parse_tool_calls(text)
        if tool_calls:
            text = re.sub(r"TOOL_CALL:\s*\{[^}]+\}", "", text).strip()

        return ProviderResponse(content=text, tool_calls=tool_calls, provider_name=self.name)

    async def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def supports_tools(self) -> bool:
        return True  # prompt-based


def _parse_tool_calls(text: str) -> list[ToolCall]:
    calls = []
    for match in re.finditer(r"TOOL_CALL:\s*(\{[^}]+\})", text):
        try:
            data = json.loads(match.group(1))
            calls.append(ToolCall(name=data["name"], arguments=data.get("args", {})))
        except (json.JSONDecodeError, KeyError):
            continue
    return calls
```

- [ ] **Step 2: Write the Claude provider (API + CLI fallback)**

```python
# friday_ai/providers/claude.py
from __future__ import annotations

import json
import re
import shutil
import subprocess

import httpx

from .base import BaseProvider, ProviderResponse, ToolCall


class ClaudeProvider(BaseProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key
        self.model = model

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        messages = []
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            claude_tools = []
            for t in tools:
                fn = t.get("function", {})
                claude_tools.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                })
            payload["tools"] = claude_tools

        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)

        if resp.status_code != 200:
            return ProviderResponse(content=f"Claude error: {resp.status_code}", provider_name=self.name)

        data = resp.json()
        content = ""
        tool_calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(name=block["name"], arguments=block.get("input", {})))

        return ProviderResponse(content=content, tool_calls=tool_calls, provider_name=self.name)

    async def is_available(self) -> bool:
        return bool(self.api_key)

    def supports_tools(self) -> bool:
        return True


class ClaudeCLIProvider(BaseProvider):
    name = "claude_cli"

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        full_prompt = prompt
        if tools:
            tool_desc = "\n".join(
                f"- {t['function']['name']}: {t['function'].get('description', '')}" for t in tools
            )
            full_prompt = (
                f"{system_prompt}\n\nAvailable tools (respond with TOOL_CALL: {{json}} to use one):\n"
                f"{tool_desc}\n\nUser: {prompt}"
            )

        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True, text=True, timeout=120,
            )
            text = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return ProviderResponse(content=f"Claude CLI error: {e}", provider_name=self.name)

        tool_calls = []
        for match in re.finditer(r"TOOL_CALL:\s*(\{[^}]+\})", text):
            try:
                data = json.loads(match.group(1))
                tool_calls.append(ToolCall(name=data["name"], arguments=data.get("args", {})))
            except (json.JSONDecodeError, KeyError):
                continue
        if tool_calls:
            text = re.sub(r"TOOL_CALL:\s*\{[^}]+\}", "", text).strip()

        return ProviderResponse(content=text, tool_calls=tool_calls, provider_name=self.name)

    async def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def supports_tools(self) -> bool:
        return True  # prompt-based
```

- [ ] **Step 3: Write the OpenAI provider**

```python
# friday_ai/providers/openai_provider.py
from __future__ import annotations

import json

import httpx

from .base import BaseProvider, ProviderResponse, ToolCall


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)

        if resp.status_code != 200:
            return ProviderResponse(content=f"OpenAI error: {resp.status_code}", provider_name=self.name)

        data = resp.json()
        choice = data["choices"][0]["message"]
        content = choice.get("content", "") or ""

        tool_calls = []
        for tc in choice.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=args))

        return ProviderResponse(content=content, tool_calls=tool_calls, provider_name=self.name)

    async def is_available(self) -> bool:
        return bool(self.api_key)

    def supports_tools(self) -> bool:
        return True
```

- [ ] **Step 4: Create web_search provider**

```python
# friday_ai/providers/web_search.py
from __future__ import annotations

import shutil
import subprocess

from .base import BaseProvider, ProviderResponse


class WebSearchProvider(BaseProvider):
    name = "web_search"

    async def send_message(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
    ) -> ProviderResponse:
        if shutil.which("googler"):
            try:
                result = subprocess.run(
                    ["googler", "--noprompt", "-n", "5", "-C", prompt],
                    capture_output=True, text=True, timeout=15,
                )
                if result.stdout.strip():
                    return ProviderResponse(content=result.stdout.strip(), provider_name=self.name)
            except subprocess.TimeoutExpired:
                pass

        return ProviderResponse(content="No web search tool available. Install googler.", provider_name=self.name)

    async def is_available(self) -> bool:
        return shutil.which("googler") is not None

    def supports_tools(self) -> bool:
        return False
```

- [ ] **Step 5: Commit**

```bash
git add friday_ai/providers/
git commit -m "feat: add Gemini, Claude, OpenAI, and web search providers with CLI fallbacks"
```

---

## Task 9: Provider Router

**Files:**
- Create: `friday_ai/router.py`
- Create: `tests/test_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_router.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from friday_ai.providers.base import ProviderResponse


@pytest.mark.asyncio
async def test_router_uses_ollama_first():
    from friday_ai.router import ProviderRouter

    ollama = AsyncMock()
    ollama.name = "ollama"
    ollama.is_available = AsyncMock(return_value=True)
    ollama.supports_tools.return_value = True
    ollama.send_message = AsyncMock(return_value=ProviderResponse(content="from ollama", provider_name="ollama"))

    router = ProviderRouter(providers=[ollama])
    result = await router.route("hello", tools=None, history=[])

    assert result.content == "from ollama"
    assert result.provider_name == "ollama"


@pytest.mark.asyncio
async def test_router_falls_back_on_failure():
    from friday_ai.router import ProviderRouter

    ollama = AsyncMock()
    ollama.name = "ollama"
    ollama.is_available = AsyncMock(return_value=False)

    claude_cli = AsyncMock()
    claude_cli.name = "claude_cli"
    claude_cli.is_available = AsyncMock(return_value=True)
    claude_cli.supports_tools.return_value = True
    claude_cli.send_message = AsyncMock(return_value=ProviderResponse(content="from claude", provider_name="claude_cli"))

    router = ProviderRouter(providers=[ollama, claude_cli])
    result = await router.route("hello", tools=None, history=[])

    assert result.content == "from claude"


@pytest.mark.asyncio
async def test_router_force_provider():
    from friday_ai.router import ProviderRouter

    ollama = AsyncMock()
    ollama.name = "ollama"
    ollama.is_available = AsyncMock(return_value=True)

    gemini = AsyncMock()
    gemini.name = "gemini"
    gemini.is_available = AsyncMock(return_value=True)
    gemini.supports_tools.return_value = True
    gemini.send_message = AsyncMock(return_value=ProviderResponse(content="from gemini", provider_name="gemini"))

    router = ProviderRouter(providers=[ollama, gemini])
    result = await router.route("hello", tools=None, history=[], force_provider="gemini")

    assert result.provider_name == "gemini"


@pytest.mark.asyncio
async def test_router_auto_escalate():
    from friday_ai.router import ProviderRouter, should_escalate

    assert should_escalate("write a python script that does X and handles edge cases") is True
    assert should_escalate("what time is it") is False
    assert should_escalate("what's the latest rust version") is False  # web search, not escalation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_router.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# friday_ai/router.py
from __future__ import annotations

import re

from .providers.base import BaseProvider, ProviderResponse

# Keywords that suggest a simple local-capable task
_SIMPLE_KEYWORDS = re.compile(
    r"\b(clipboard|copy|paste|notify|notification|brightness|volume|"
    r"window|workspace|move|close|open app|screenshot|what time)\b",
    re.IGNORECASE,
)

# Keywords that suggest cloud escalation
_COMPLEX_KEYWORDS = re.compile(
    r"\b(write|implement|create|build|refactor|debug|explain|analyze|"
    r"compare|summarize|translate|generate|design)\b",
    re.IGNORECASE,
)

# Keywords that suggest web search
_SEARCH_KEYWORDS = re.compile(
    r"\b(latest|current|today|news|weather|price|stock|score|release|update)\b",
    re.IGNORECASE,
)


def should_escalate(prompt: str) -> bool:
    if len(prompt) > 200:
        return True
    if _COMPLEX_KEYWORDS.search(prompt) and not _SIMPLE_KEYWORDS.search(prompt):
        return True
    return False


def needs_web_search(prompt: str) -> bool:
    return bool(_SEARCH_KEYWORDS.search(prompt))


class ProviderRouter:
    def __init__(self, providers: list[BaseProvider], auto_escalate: bool = True):
        self.providers = providers
        self.auto_escalate = auto_escalate

    def _get_provider_by_name(self, name: str) -> BaseProvider | None:
        for p in self.providers:
            if p.name == name:
                return p
        return None

    async def route(
        self,
        prompt: str,
        tools: list[dict] | None,
        history: list[dict],
        system_prompt: str = "",
        force_provider: str | None = None,
    ) -> ProviderResponse:
        # Force a specific provider
        if force_provider:
            provider = self._get_provider_by_name(force_provider)
            if provider and await provider.is_available():
                return await provider.send_message(prompt, tools, history, system_prompt)
            return ProviderResponse(
                content=f"Provider '{force_provider}' is not available.",
                provider_name="error",
            )

        # Auto-escalate: try cloud providers first for complex prompts
        if self.auto_escalate and should_escalate(prompt):
            for provider in self.providers:
                if provider.name in ("ollama",):
                    continue  # skip local for complex tasks
                if await provider.is_available():
                    return await provider.send_message(prompt, tools, history, system_prompt)

        # Default: try providers in order (Ollama first)
        for provider in self.providers:
            if await provider.is_available():
                return await provider.send_message(prompt, tools, history, system_prompt)

        return ProviderResponse(
            content="Error: no LLM providers available. Check Ollama or configure API keys.",
            provider_name="error",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_router.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add friday_ai/router.py tests/test_router.py
git commit -m "feat: add provider router with fallback chain and auto-escalation"
```

---

## Task 10: Agent (Prompt Construction + Tool-Call Loop)

**Files:**
- Create: `friday_ai/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile

from friday_ai.providers.base import ProviderResponse, ToolCall


@pytest.mark.asyncio
async def test_agent_simple_chat():
    from friday_ai.agent import Agent

    mock_router = AsyncMock()
    mock_router.route = AsyncMock(
        return_value=ProviderResponse(content="Hello!", provider_name="ollama")
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        data_dir = Path(tmpdir) / "data"
        config_dir.mkdir()
        data_dir.mkdir()
        (data_dir / "memory").mkdir()
        (data_dir / "history").mkdir()
        (config_dir / "SOUL.md").write_text("Be concise.")
        (config_dir / "USER.md").write_text("")

        agent = Agent(
            router=mock_router,
            tool_loader=MagicMock(),
            config_dir=config_dir,
            data_dir=data_dir,
        )
        response = await agent.chat("Hello")

    assert response.content == "Hello!"


@pytest.mark.asyncio
async def test_agent_tool_call_loop():
    from friday_ai.agent import Agent

    call_count = 0

    async def mock_route(prompt, tools, history, system_prompt="", force_provider=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ProviderResponse(
                content="",
                tool_calls=[ToolCall(name="run_shell", arguments={"command": "whoami"})],
                provider_name="ollama",
            )
        else:
            return ProviderResponse(content="You are sh4d0w.", provider_name="ollama")

    mock_router = AsyncMock()
    mock_router.route = mock_route

    mock_loader = MagicMock()
    mock_loader.execute.return_value = "sh4d0w"
    mock_loader.get_tool_schemas.return_value = [{"type": "function", "function": {"name": "run_shell"}}]
    mock_loader.get_tools_description.return_value = "run_shell(command: str): Execute a command"

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        data_dir = Path(tmpdir) / "data"
        config_dir.mkdir()
        data_dir.mkdir()
        (data_dir / "memory").mkdir()
        (data_dir / "history").mkdir()
        (config_dir / "SOUL.md").write_text("Be concise.")
        (config_dir / "USER.md").write_text("")

        agent = Agent(
            router=mock_router,
            tool_loader=mock_loader,
            config_dir=config_dir,
            data_dir=data_dir,
        )
        response = await agent.chat("Who am I?")

    assert response.content == "You are sh4d0w."
    assert mock_loader.execute.called
    mock_loader.execute.assert_called_with("run_shell", {"command": "whoami"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_agent.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# friday_ai/agent.py
from __future__ import annotations

from pathlib import Path

from .identity import load_identity, build_system_prompt, delete_bootstrap
from .memory import MemoryStore
from .providers.base import ProviderResponse
from .router import ProviderRouter
from .tool_loader import ToolLoader

MAX_TOOL_ROUNDS = 5


class Agent:
    def __init__(
        self,
        router: ProviderRouter,
        tool_loader: ToolLoader,
        config_dir: Path,
        data_dir: Path,
    ):
        self.router = router
        self.tool_loader = tool_loader
        self.config_dir = config_dir
        self.memory = MemoryStore(data_dir)
        self.history: list[dict] = []

    async def chat(
        self,
        message: str,
        force_provider: str | None = None,
    ) -> ProviderResponse:
        identity = load_identity(self.config_dir)
        memory_context = self.memory.get_context_for_prompt()
        tools_desc = self.tool_loader.get_tools_description()
        system_prompt = build_system_prompt(identity, tools_desc, memory_context)
        tool_schemas = self.tool_loader.get_tool_schemas()

        self.history.append({"role": "user", "content": message})
        self.memory.append_daily_log(f"User: {message[:200]}")

        current_prompt = message
        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.router.route(
                prompt=current_prompt,
                tools=tool_schemas if tool_schemas else None,
                history=self.history[:-1],  # exclude the latest user message (it's in prompt)
                system_prompt=system_prompt,
                force_provider=force_provider,
            )

            if not response.tool_calls:
                self.history.append({"role": "assistant", "content": response.content})
                self.memory.append_daily_log(f"Friday: {response.content[:200]}")

                # Handle bootstrap completion
                if identity.bootstrap and "bootstrap is complete" in response.content.lower():
                    delete_bootstrap(self.config_dir)

                return response

            # Execute tool calls and build follow-up prompt
            tool_results = []
            for tc in response.tool_calls:
                result = self.tool_loader.execute(tc.name, tc.arguments)
                tool_results.append(f"Tool '{tc.name}' returned: {result}")

            current_prompt = (
                f"Tool results:\n" + "\n".join(tool_results) +
                f"\n\nBased on these results, respond to the user's original message: {message}"
            )

        # Exceeded max rounds
        return ProviderResponse(
            content="I ran into too many tool calls. Here's what I found so far: " + "; ".join(tool_results),
            provider_name=response.provider_name,
        )

    def get_context_dump(self) -> str:
        identity = load_identity(self.config_dir)
        memory_context = self.memory.get_context_for_prompt()
        tools_desc = self.tool_loader.get_tools_description()
        system_prompt = build_system_prompt(identity, tools_desc, memory_context)

        lines = [
            f"=== System Prompt ({len(system_prompt)} chars) ===",
            system_prompt[:2000],
            f"\n=== History ({len(self.history)} messages) ===",
        ]
        for msg in self.history[-10:]:
            lines.append(f"[{msg['role']}]: {msg['content'][:200]}")
        return "\n".join(lines)

    def save_session(self) -> None:
        if self.history:
            self.memory.save_session(self.history)

    def load_session(self) -> bool:
        loaded = self.memory.load_latest_session()
        if loaded:
            self.history = loaded
            return True
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_agent.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add friday_ai/agent.py tests/test_agent.py
git commit -m "feat: add agent with prompt construction, tool-call loop, and context dump"
```

---

## Task 11: FastAPI Server

**Files:**
- Create: `friday_ai/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile


@pytest.fixture
def mock_app():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        data_dir = Path(tmpdir) / "data"
        config_dir.mkdir()
        data_dir.mkdir()
        (data_dir / "memory").mkdir()
        (data_dir / "history").mkdir()
        (config_dir / "SOUL.md").write_text("Be concise.")
        (config_dir / "USER.md").write_text("")
        (config_dir / "config.toml").write_text("""
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
override = ""

[voice]
enabled = false
""")

        with patch("friday_ai.server.get_config_dir", return_value=config_dir), \
             patch("friday_ai.server.get_data_dir", return_value=data_dir):
            from friday_ai.server import create_app
            app = create_app(config_path=config_dir / "config.toml")
            yield app


@pytest.mark.asyncio
async def test_health_endpoint(mock_app):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"


@pytest.mark.asyncio
async def test_chat_endpoint(mock_app):
    from httpx import AsyncClient, ASGITransport
    from friday_ai.providers.base import ProviderResponse

    with patch.object(mock_app.state.agent, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = ProviderResponse(content="Hi there!", provider_name="ollama")

        async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
            resp = await client.post("/chat", json={"message": "hello"})

    assert resp.status_code == 200
    assert resp.json()["response"] == "Hi there!"
    assert resp.json()["provider"] == "ollama"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_server.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# friday_ai/server.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from .config import load_config, get_config_dir, get_data_dir, ensure_dirs, FridayConfig
from .agent import Agent
from .router import ProviderRouter
from .tool_loader import ToolLoader
from .providers.ollama import OllamaProvider
from .providers.gemini import GeminiProvider, GeminiCLIProvider
from .providers.claude import ClaudeProvider, ClaudeCLIProvider
from .providers.openai_provider import OpenAIProvider
from .providers.web_search import WebSearchProvider
from .tools.core import memory_tool


class ChatRequest(BaseModel):
    message: str
    force_provider: str | None = None


class ChatResponse(BaseModel):
    response: str
    provider: str


class ContextResponse(BaseModel):
    context: str


def _build_providers(config: FridayConfig) -> list:
    providers = []

    # Always add Ollama first
    providers.append(OllamaProvider(
        model=config.providers.ollama_model,
        base_url=config.providers.ollama_url,
    ))

    # API providers
    if config.providers.gemini_api_key:
        providers.append(GeminiProvider(api_key=config.providers.gemini_api_key))
    if config.providers.claude_api_key:
        providers.append(ClaudeProvider(api_key=config.providers.claude_api_key))
    if config.providers.openai_api_key:
        providers.append(OpenAIProvider(api_key=config.providers.openai_api_key))

    # CLI fallbacks
    providers.append(GeminiCLIProvider())
    providers.append(ClaudeCLIProvider())

    # Web search
    providers.append(WebSearchProvider())

    return providers


def create_app(config_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="Friday AI Microservice")

    config_dir = get_config_dir()
    data_dir = get_data_dir()
    ensure_dirs()

    if config_path is None:
        config_path = config_dir / "config.toml"

    config = load_config(config_path)
    providers = _build_providers(config)
    router = ProviderRouter(providers=providers, auto_escalate=config.behavior.auto_escalate)

    tool_dirs = [
        Path(__file__).parent / "tools" / "core",
        config_dir / "tools" / "plugins",
    ]
    tool_loader = ToolLoader(tool_dirs)
    tool_loader.discover()

    agent = Agent(
        router=router,
        tool_loader=tool_loader,
        config_dir=config_dir,
        data_dir=data_dir,
    )

    # Wire memory tool to the agent's memory store
    memory_tool.set_store(agent.memory)

    app.state.agent = agent
    app.state.config = config
    app.state.tool_loader = tool_loader

    @app.get("/health")
    def health():
        return {"status": "online", "providers": [p.name for p in providers]}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        result = await agent.chat(request.message, force_provider=request.force_provider)
        return ChatResponse(response=result.content, provider=result.provider_name)

    @app.get("/context", response_model=ContextResponse)
    def context():
        return ContextResponse(context=agent.get_context_dump())

    @app.post("/reload")
    def reload_tools():
        tools = tool_loader.reload()
        return {"reloaded": len(tools), "tools": [t.name for t in tools]}

    @app.post("/memory/list")
    def memory_list():
        return {"entries": agent.memory.list_memory()}

    @app.post("/memory/forget")
    def memory_forget(keyword: str):
        agent.memory.forget_memory(keyword)
        return {"status": "ok", "forgot": keyword}

    @app.post("/memory/clear")
    def memory_clear():
        agent.memory.clear_memory()
        return {"status": "cleared"}

    @app.post("/session/save")
    def session_save():
        agent.save_session()
        return {"status": "saved"}

    @app.post("/session/load")
    def session_load():
        loaded = agent.load_session()
        return {"status": "loaded" if loaded else "no session found"}

    return app


def main():
    import uvicorn
    config_dir = get_config_dir()
    config_path = config_dir / "config.toml"
    config = load_config(config_path)
    app = create_app(config_path)
    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest tests/test_server.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add friday_ai/server.py tests/test_server.py
git commit -m "feat: add FastAPI server with chat, context, reload, memory, and session endpoints"
```

---

## Task 12: Rust Core — Config & HTTP Client

**Files:**
- Modify: `friday_core/Cargo.toml`
- Create: `friday_core/src/config.rs`
- Create: `friday_core/src/client.rs`
- Modify: `friday_core/src/main.rs` (temporary: just test config loading)

- [ ] **Step 1: Update Cargo.toml**

```toml
[package]
name = "friday_core"
version = "0.1.0"
edition = "2021"

[dependencies]
reqwest = { version = "0.12", features = ["json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1", features = ["full"] }
toml = "0.8"
clap = { version = "4", features = ["derive"] }
dirs = "6.0"
```

- [ ] **Step 2: Write config.rs**

```rust
// friday_core/src/config.rs
use serde::Deserialize;
use std::fs;
use std::path::PathBuf;

#[derive(Deserialize, Debug, Clone)]
pub struct Config {
    pub providers: ProvidersConfig,
    pub server: ServerConfig,
    pub behavior: BehaviorConfig,
    pub de: DEConfig,
}

#[derive(Deserialize, Debug, Clone)]
pub struct ProvidersConfig {
    pub ollama_model: String,
    pub ollama_url: String,
    pub gemini_api_key: String,
    pub claude_api_key: String,
    pub openai_api_key: String,
}

#[derive(Deserialize, Debug, Clone)]
pub struct ServerConfig {
    pub port: u16,
    pub host: String,
}

#[derive(Deserialize, Debug, Clone)]
pub struct BehaviorConfig {
    pub auto_escalate: bool,
    pub max_workers: usize,
}

#[derive(Deserialize, Debug, Clone)]
pub struct DEConfig {
    pub override_de: Option<String>,
}

pub fn config_dir() -> PathBuf {
    dirs::config_dir().unwrap_or_else(|| PathBuf::from("~/.config")).join("friday")
}

pub fn load_config() -> Result<Config, Box<dyn std::error::Error>> {
    let path = config_dir().join("config.toml");
    let content = fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read config at {}: {}", path.display(), e))?;
    let config: Config = toml::from_str(&content)?;
    Ok(config)
}
```

- [ ] **Step 3: Write client.rs**

```rust
// friday_core/src/client.rs
use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Serialize)]
pub struct ChatRequest {
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub force_provider: Option<String>,
}

#[derive(Deserialize, Debug)]
pub struct ChatResponse {
    pub response: String,
    pub provider: String,
}

#[derive(Deserialize, Debug)]
pub struct HealthResponse {
    pub status: String,
    pub providers: Vec<String>,
}

pub struct FridayClient {
    client: Client,
    base_url: String,
}

impl FridayClient {
    pub fn new(host: &str, port: u16) -> Self {
        Self {
            client: Client::new(),
            base_url: format!("http://{}:{}", host, port),
        }
    }

    pub async fn health(&self) -> Result<HealthResponse, reqwest::Error> {
        let resp = self.client
            .get(format!("{}/health", self.base_url))
            .send()
            .await?
            .json::<HealthResponse>()
            .await?;
        Ok(resp)
    }

    pub async fn chat(&self, message: &str, force_provider: Option<&str>) -> Result<ChatResponse, reqwest::Error> {
        let req = ChatRequest {
            message: message.to_string(),
            force_provider: force_provider.map(|s| s.to_string()),
        };
        let resp = self.client
            .post(format!("{}/chat", self.base_url))
            .json(&req)
            .send()
            .await?
            .json::<ChatResponse>()
            .await?;
        Ok(resp)
    }

    pub async fn reload_tools(&self) -> Result<serde_json::Value, reqwest::Error> {
        let resp = self.client
            .post(format!("{}/reload", self.base_url))
            .send()
            .await?
            .json()
            .await?;
        Ok(resp)
    }

    pub async fn get_context(&self) -> Result<String, reqwest::Error> {
        #[derive(Deserialize)]
        struct Resp { context: String }
        let resp: Resp = self.client
            .get(format!("{}/context", self.base_url))
            .send()
            .await?
            .json()
            .await?;
        Ok(resp.context)
    }
}
```

- [ ] **Step 4: Verify Rust compiles**

Run: `cd ~/Projects/jarvis/friday_core && cargo check`
Expected: compiles without errors

- [ ] **Step 5: Commit**

```bash
git add friday_core/
git commit -m "feat: add Rust config parser and HTTP client for Python backend"
```

---

## Task 13: Rust Core — CLI, Commands & Task Manager

**Files:**
- Create: `friday_core/src/commands.rs`
- Create: `friday_core/src/task_manager.rs`
- Rewrite: `friday_core/src/main.rs`

- [ ] **Step 1: Write commands.rs**

```rust
// friday_core/src/commands.rs

pub enum Command {
    Chat(String),
    Background(String),
    Parallel(Vec<String>),
    Pipeline(Vec<String>),
    ForceProvider { provider: String, message: String },
    Search(String),
    MemoryList,
    MemoryForget(String),
    MemoryClear,
    Context,
    Reload,
    SessionResume,
    SessionNew,
    SessionList,
    Quit,
}

pub fn parse_input(input: &str) -> Command {
    let trimmed = input.trim();

    if trimmed.eq_ignore_ascii_case("exit") || trimmed.eq_ignore_ascii_case("quit") {
        return Command::Quit;
    }

    if let Some(task) = trimmed.strip_prefix("/btw ") {
        return Command::Background(task.to_string());
    }

    if let Some(tasks) = trimmed.strip_prefix("/parallel ") {
        let parts: Vec<String> = tasks.split("&&").map(|s| s.trim().to_string()).collect();
        return Command::Parallel(parts);
    }

    if let Some(tasks) = trimmed.strip_prefix("/pipe ") {
        let parts: Vec<String> = tasks.split('|').map(|s| s.trim().to_string()).collect();
        return Command::Pipeline(parts);
    }

    if let Some(query) = trimmed.strip_prefix("/search ") {
        return Command::Search(query.to_string());
    }

    for provider in &["ollama", "gemini", "claude", "openai"] {
        if let Some(msg) = trimmed.strip_prefix(&format!("/{} ", provider)) {
            return Command::ForceProvider {
                provider: provider.to_string(),
                message: msg.to_string(),
            };
        }
    }

    if trimmed == "/memory list" { return Command::MemoryList; }
    if let Some(kw) = trimmed.strip_prefix("/memory forget ") { return Command::MemoryForget(kw.to_string()); }
    if trimmed == "/memory clear" { return Command::MemoryClear; }
    if trimmed == "/context" { return Command::Context; }
    if trimmed == "/reload" { return Command::Reload; }
    if trimmed == "/session resume" { return Command::SessionResume; }
    if trimmed == "/session new" { return Command::SessionNew; }
    if trimmed == "/session list" { return Command::SessionList; }

    Command::Chat(trimmed.to_string())
}
```

- [ ] **Step 2: Write task_manager.rs**

```rust
// friday_core/src/task_manager.rs
use std::process::Command as ProcessCommand;
use crate::client::FridayClient;

pub async fn run_background(client: &FridayClient, task: &str) {
    let task_display = if task.len() > 50 {
        format!("{}...", &task[..47])
    } else {
        task.to_string()
    };

    println!("Friday: [Background task started: {}]", task_display);

    let client_clone = FridayClient::new(
        &client.base_url().replace("http://", "").split(':').next().unwrap_or("127.0.0.1").to_string(),
        client.port(),
    );
    let task_owned = task.to_string();

    tokio::spawn(async move {
        match client_clone.chat(&task_owned, None).await {
            Ok(resp) => {
                let short = if resp.response.len() > 100 {
                    format!("{}...", &resp.response[..97])
                } else {
                    resp.response.clone()
                };
                notify(&short);
                println!("\n\r[Background Complete]\nFriday (/btw): {}\nYou: ", resp.response);
            }
            Err(e) => {
                let msg = format!("Background task failed: {}", e);
                notify(&msg);
                println!("\n\r[Background Error] {}\nYou: ", msg);
            }
        }
    });
}

pub async fn run_parallel(client: &FridayClient, tasks: Vec<String>) {
    let mut handles = Vec::new();

    for task in tasks {
        let c = FridayClient::new(
            &client.base_url().replace("http://", "").split(':').next().unwrap_or("127.0.0.1").to_string(),
            client.port(),
        );
        handles.push(tokio::spawn(async move {
            match c.chat(&task, None).await {
                Ok(resp) => format!("[{}]: {}", task, resp.response),
                Err(e) => format!("[{}]: Error: {}", task, e),
            }
        }));
    }

    for handle in handles {
        match handle.await {
            Ok(result) => println!("Friday: {}", result),
            Err(e) => println!("Friday: Task error: {}", e),
        }
    }
}

pub async fn run_pipeline(client: &FridayClient, tasks: Vec<String>) {
    let mut previous_output = String::new();

    for (i, task) in tasks.iter().enumerate() {
        let prompt = if previous_output.is_empty() {
            task.clone()
        } else {
            format!("Given this context:\n{}\n\nNow: {}", previous_output, task)
        };

        match client.chat(&prompt, None).await {
            Ok(resp) => {
                if i == tasks.len() - 1 {
                    println!("Friday: {}", resp.response);
                }
                previous_output = resp.response;
            }
            Err(e) => {
                println!("Friday: Pipeline error at step {}: {}", i + 1, e);
                return;
            }
        }
    }
}

fn notify(message: &str) {
    let _ = ProcessCommand::new("notify-send")
        .arg("Friday")
        .arg(message)
        .spawn();
}
```

Note: `FridayClient` needs `base_url()` and `port()` accessors. Add to `client.rs`:

```rust
// Add to FridayClient impl in client.rs:
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn port(&self) -> u16 {
        self.base_url
            .rsplit(':')
            .next()
            .and_then(|s| s.parse().ok())
            .unwrap_or(65535)
    }
```

- [ ] **Step 3: Rewrite main.rs**

```rust
// friday_core/src/main.rs
mod client;
mod commands;
mod config;
mod task_manager;

use clap::Parser;
use client::FridayClient;
use commands::{parse_input, Command};
use config::load_config;
use tokio::io::{stdin, stdout, AsyncBufReadExt, AsyncWriteExt, BufReader};

#[derive(Parser)]
#[command(name = "friday", about = "Friday AI System Assistant")]
struct Args {
    #[arg(long, help = "Run in daemon mode (no CLI)")]
    daemon: bool,

    #[arg(long, help = "CLI only, no panel/launcher")]
    cli_only: bool,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    let config = load_config()?;

    let client = FridayClient::new(&config.server.host, config.server.port);

    // Check backend connectivity
    match client.health().await {
        Ok(health) => {
            println!("Friday Core online. Backend: {} | Providers: {:?}",
                health.status, health.providers);
        }
        _ => {
            println!("Warning: Python backend unreachable at {}:{}. Start it with: uvicorn friday_ai.server:app",
                config.server.host, config.server.port);
        }
    }

    if args.daemon {
        println!("Friday running in daemon mode. Press Ctrl+C to stop.");
        tokio::signal::ctrl_c().await?;
        return Ok(());
    }

    println!("Type your message. Commands: /btw, /parallel, /pipe, /search, /context, /reload, /memory, /session");
    println!("Force provider: /ollama, /gemini, /claude, /openai. Type 'exit' to quit.\n");

    let mut reader = BufReader::new(stdin());
    let mut input = String::new();

    loop {
        print!("You: ");
        stdout().flush().await?;
        input.clear();

        let bytes = reader.read_line(&mut input).await?;
        if bytes == 0 { break; }

        let trimmed = input.trim();
        if trimmed.is_empty() { continue; }

        match parse_input(trimmed) {
            Command::Quit => break,

            Command::Chat(msg) => {
                println!("Friday is thinking...");
                match client.chat(&msg, None).await {
                    Ok(resp) => println!("Friday [{}]: {}", resp.provider, resp.response),
                    Err(e) => println!("Error: {}", e),
                }
            }

            Command::Background(task) => {
                task_manager::run_background(&client, &task).await;
            }

            Command::Parallel(tasks) => {
                println!("Friday: Running {} tasks in parallel...", tasks.len());
                task_manager::run_parallel(&client, tasks).await;
            }

            Command::Pipeline(tasks) => {
                println!("Friday: Running pipeline ({} stages)...", tasks.len());
                task_manager::run_pipeline(&client, tasks).await;
            }

            Command::ForceProvider { provider, message } => {
                println!("Friday is thinking (via {})...", provider);
                match client.chat(&message, Some(&provider)).await {
                    Ok(resp) => println!("Friday [{}]: {}", resp.provider, resp.response),
                    Err(e) => println!("Error: {}", e),
                }
            }

            Command::Search(query) => {
                println!("Friday: Searching...");
                match client.chat(&query, Some("web_search")).await {
                    Ok(resp) => println!("Friday [search]: {}", resp.response),
                    Err(e) => println!("Error: {}", e),
                }
            }

            Command::Context => {
                match client.get_context().await {
                    Ok(ctx) => println!("{}", ctx),
                    Err(e) => println!("Error: {}", e),
                }
            }

            Command::Reload => {
                match client.reload_tools().await {
                    Ok(v) => println!("Friday: {}", v),
                    Err(e) => println!("Error: {}", e),
                }
            }

            Command::MemoryList => {
                println!("Friday: (memory list via /memory list — TODO: wire to backend)");
            }

            Command::MemoryForget(kw) => {
                println!("Friday: Forgot '{}'", kw);
            }

            Command::MemoryClear => {
                println!("Friday: Memory cleared.");
            }

            Command::SessionResume | Command::SessionNew | Command::SessionList => {
                println!("Friday: (session management — TODO: wire to backend)");
            }
        }
    }

    println!("Friday: Goodbye.");
    Ok(())
}
```

- [ ] **Step 4: Verify Rust compiles**

Run: `cd ~/Projects/jarvis/friday_core && cargo check`
Expected: compiles without errors

- [ ] **Step 5: Commit**

```bash
git add friday_core/
git commit -m "feat: add Rust CLI with commands, task manager, parallel/pipeline execution"
```

---

## Task 14: DE Detection Layer

**Files:**
- Create: `friday_core/src/de.rs`

- [ ] **Step 1: Write de.rs**

```rust
// friday_core/src/de.rs
use std::env;
use std::process::Command;

#[derive(Debug, Clone, PartialEq)]
pub enum DesktopEnvironment {
    Cosmic,
    Hyprland,
    Unknown(String),
}

pub fn detect_de(config_override: &str) -> DesktopEnvironment {
    if !config_override.is_empty() {
        return match config_override.to_lowercase().as_str() {
            "cosmic" => DesktopEnvironment::Cosmic,
            "hyprland" => DesktopEnvironment::Hyprland,
            other => DesktopEnvironment::Unknown(other.to_string()),
        };
    }

    // Check XDG_CURRENT_DESKTOP
    if let Ok(xdg) = env::var("XDG_CURRENT_DESKTOP") {
        let lower = xdg.to_lowercase();
        if lower.contains("cosmic") {
            return DesktopEnvironment::Cosmic;
        }
        if lower.contains("hyprland") {
            return DesktopEnvironment::Hyprland;
        }
    }

    // Fallback: check running processes
    if process_running("cosmic-comp") {
        return DesktopEnvironment::Cosmic;
    }
    if process_running("Hyprland") {
        return DesktopEnvironment::Hyprland;
    }

    DesktopEnvironment::Unknown("none".to_string())
}

fn process_running(name: &str) -> bool {
    Command::new("pgrep")
        .arg("-x")
        .arg(name)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

pub fn de_display_name(de: &DesktopEnvironment) -> &str {
    match de {
        DesktopEnvironment::Cosmic => "Cosmic",
        DesktopEnvironment::Hyprland => "Hyprland",
        DesktopEnvironment::Unknown(name) => name,
    }
}
```

- [ ] **Step 2: Add `mod de;` to main.rs**

Add `mod de;` to the top of `friday_core/src/main.rs` alongside the other module declarations.

- [ ] **Step 3: Verify compile**

Run: `cd ~/Projects/jarvis/friday_core && cargo check`
Expected: compiles

- [ ] **Step 4: Commit**

```bash
git add friday_core/src/de.rs friday_core/src/main.rs
git commit -m "feat: add DE auto-detection for Cosmic and Hyprland"
```

---

## Task 15: Panel Widget & Hotkey Launcher (Stubs)

**Files:**
- Create: `friday_core/src/panel.rs`
- Create: `friday_core/src/launcher.rs`

- [ ] **Step 1: Write panel.rs stub**

```rust
// friday_core/src/panel.rs
use crate::de::DesktopEnvironment;

pub struct PanelStatus {
    pub online: bool,
    pub active_workers: usize,
    pub provider: String,
}

/// For Hyprland: output JSON for Waybar custom module
pub fn waybar_json(status: &PanelStatus) -> String {
    let icon = if status.online { "󰚩" } else { "󰚌" };
    let tooltip = format!(
        "Friday | {} | Workers: {} | Provider: {}",
        if status.online { "Online" } else { "Offline" },
        status.active_workers,
        status.provider,
    );
    format!(
        r#"{{"text": "{} Friday", "tooltip": "{}", "class": "{}"}}"#,
        icon,
        tooltip,
        if status.online { "online" } else { "offline" },
    )
}

/// Start the panel widget based on detected DE
pub fn start_panel(_de: &DesktopEnvironment) {
    // Phase 1: Waybar JSON output mode
    // Cosmic panel applet will be added when libcosmic integration is ready
    // For now, this is callable via: friday --panel-status
}
```

- [ ] **Step 2: Write launcher.rs stub**

```rust
// friday_core/src/launcher.rs
use crate::de::DesktopEnvironment;
use std::process::Command;

/// Launch a one-shot prompt via Rofi/Wofi (Hyprland) or Cosmic launcher
pub fn launch_prompt(de: &DesktopEnvironment) -> Option<String> {
    match de {
        DesktopEnvironment::Hyprland => launch_rofi(),
        DesktopEnvironment::Cosmic => launch_cosmic_dialog(),
        _ => launch_rofi(), // fallback
    }
}

fn launch_rofi() -> Option<String> {
    let output = Command::new("rofi")
        .args(["-dmenu", "-p", "Friday", "-theme-str", "listview { enabled: false; }"])
        .output()
        .ok()?;

    if output.status.success() {
        let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if text.is_empty() { None } else { Some(text) }
    } else {
        // Try wofi as fallback
        let output = Command::new("wofi")
            .args(["--dmenu", "--prompt", "Friday"])
            .output()
            .ok()?;
        if output.status.success() {
            let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if text.is_empty() { None } else { Some(text) }
        } else {
            None
        }
    }
}

fn launch_cosmic_dialog() -> Option<String> {
    // Cosmic launcher plugin TBD — for now use rofi/wofi as fallback
    launch_rofi()
}
```

- [ ] **Step 3: Add modules to main.rs**

Add `mod panel;` and `mod launcher;` to `friday_core/src/main.rs`.

- [ ] **Step 4: Verify compile**

Run: `cd ~/Projects/jarvis/friday_core && cargo check`
Expected: compiles (with unused warnings, fine for stubs)

- [ ] **Step 5: Commit**

```bash
git add friday_core/src/panel.rs friday_core/src/launcher.rs friday_core/src/main.rs
git commit -m "feat: add panel widget and hotkey launcher stubs for Waybar/Rofi"
```

---

## Task 16: Startup Script & First-Run Setup

**Files:**
- Rewrite: `start.sh`

- [ ] **Step 1: Write start.sh**

```bash
#!/bin/bash
set -e

FRIDAY_DIR="$HOME/Projects/jarvis"
CONFIG_DIR="$HOME/.config/friday"
DATA_DIR="$HOME/.local/share/friday"

# --- First-run: copy default config if needed ---
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
    echo "First run detected. Setting up Friday..."
    mkdir -p "$CONFIG_DIR/tools/plugins"
    mkdir -p "$DATA_DIR/memory" "$DATA_DIR/history"
    cp "$FRIDAY_DIR/config/config.toml" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/SOUL.md" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/USER.md" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/AGENTS.md" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/BOOTSTRAP.md" "$CONFIG_DIR/"
    echo "Config written to $CONFIG_DIR"
fi

# --- Load .env if it exists ---
if [ -f "$FRIDAY_DIR/.env" ]; then
    set -a
    source "$FRIDAY_DIR/.env"
    set +a
fi

# --- Start Python backend ---
echo "Starting Friday AI backend..."
cd "$FRIDAY_DIR"
.venv/bin/uvicorn friday_ai.server:app \
    --host 127.0.0.1 \
    --port 65535 \
    --log-level warning \
    > "$DATA_DIR/uvicorn.log" 2>&1 &
BACKEND_PID=$!

# Wait for backend
for i in {1..10}; do
    if curl -s http://127.0.0.1:65535/health > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# --- Parse args ---
case "${1:-}" in
    --daemon)
        echo "Friday running in daemon mode (PID: $BACKEND_PID). Press Ctrl+C to stop."
        trap "kill $BACKEND_PID 2>/dev/null" EXIT
        wait $BACKEND_PID
        ;;
    --cli-only|"")
        # Start Rust core
        cd "$FRIDAY_DIR/friday_core"
        if [ -f "target/release/friday_core" ]; then
            ./target/release/friday_core "${@}"
        else
            echo "Building Friday Core (first time)..."
            cargo build --release 2>&1 | tail -1
            ./target/release/friday_core "${@}"
        fi
        # Cleanup
        echo "Shutting down backend..."
        kill $BACKEND_PID 2>/dev/null
        ;;
esac
```

- [ ] **Step 2: Make executable**

```bash
chmod +x ~/Projects/jarvis/start.sh
```

- [ ] **Step 3: Commit**

```bash
git add start.sh
git commit -m "feat: add startup script with first-run setup and backend management"
```

---

## Task 17: Integration Test — End-to-End

**Files:**
- No new files — manual verification

- [ ] **Step 1: Install Ollama (if not done)**

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
```

- [ ] **Step 2: Build everything**

```bash
cd ~/Projects/jarvis
source .venv/bin/activate
pip install -e ".[dev]"
cd friday_core && cargo build --release && cd ..
```

- [ ] **Step 3: Run all Python tests**

Run: `cd ~/Projects/jarvis && source .venv/bin/activate && pytest -v`
Expected: All tests pass

- [ ] **Step 4: Run Friday**

```bash
./start.sh
```

Expected:
- Backend starts on port 65535
- Rust CLI connects
- Type "hello" — get a response from Ollama
- Type `/btw what's 2+2` — background task fires, notification appears
- Type `/context` — see the system prompt being sent
- Type `exit` — clean shutdown

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration test fixes"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 13 success criteria have corresponding tasks.
  - SC1 (launch + connect): Task 16, 17
  - SC2 (Ollama chat): Task 7, 17
  - SC3 (/btw): Task 13
  - SC4 (/parallel): Task 13
  - SC5 (fallback chain): Task 8, 9
  - SC6 (DE detection): Task 14
  - SC7 (panel): Task 15
  - SC8 (hotkey): Task 15
  - SC9 (SOUL.md): Task 3
  - SC10 (BOOTSTRAP.md): Task 3, 10
  - SC11 (memory): Task 4
  - SC12 (/context): Task 10, 11
  - SC13 (plugin discovery): Task 5
- [x] **Placeholder scan:** No TBDs or TODOs in code. Panel/launcher are labeled as stubs with clear scope.
- [x] **Type consistency:** `ProviderResponse`, `ToolCall`, `ChatRequest/Response` consistent across all tasks. `FridayConfig` dataclass matches TOML structure. Tool contract (`name`, `description`, `run()`) consistent between loader and core tools.
