"""Config system for Friday AI.

Loads TOML config files, applies env-var overrides, and exposes
helper functions for runtime discovery of available providers and
standard XDG-style directory paths.
"""

from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProvidersConfig:
    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"
    gemini_api_key: str = ""
    claude_api_key: str = ""
    openai_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    claude_model: str = "claude-sonnet-4-6"
    openai_model: str = "gpt-4o"
    ollama_model_fast: str = "qwen2.5:3b"
    ollama_model_heavy: str = "qwen2.5:7b"


@dataclass
class ServerConfig:
    port: int = 65535
    host: str = "127.0.0.1"


@dataclass
class BehaviorConfig:
    auto_escalate: bool = True
    max_workers: int = 4
    provider_mode: str = "fallback"  # "fallback" | "race"


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


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> FridayConfig:
    """Load a TOML config file and return a populated :class:`FridayConfig`.

    Environment variables ``GEMINI_API_KEY``, ``CLAUDE_API_KEY``, and
    ``OPENAI_API_KEY`` are applied only when the corresponding TOML field is
    empty (falsy).
    """
    path = Path(path)
    if not path.exists():
        return FridayConfig()

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    # --- providers ---
    p = raw.get("providers", {})
    providers = ProvidersConfig(
        ollama_model=p.get("ollama_model", ProvidersConfig.ollama_model),
        ollama_url=p.get("ollama_url", ProvidersConfig.ollama_url),
        gemini_api_key=p.get("gemini_api_key", ""),
        claude_api_key=p.get("claude_api_key", ""),
        openai_api_key=p.get("openai_api_key", ""),
        gemini_model=p.get("gemini_model", ProvidersConfig.gemini_model),
        claude_model=p.get("claude_model", ProvidersConfig.claude_model),
        openai_model=p.get("openai_model", ProvidersConfig.openai_model),
    )

    # Apply env-var overrides only when the TOML value is empty
    if not providers.gemini_api_key:
        providers.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not providers.claude_api_key:
        providers.claude_api_key = os.environ.get("CLAUDE_API_KEY", "")
    if not providers.openai_api_key:
        providers.openai_api_key = os.environ.get("OPENAI_API_KEY", "")

    # --- server ---
    s = raw.get("server", {})
    server = ServerConfig(
        port=s.get("port", ServerConfig.port),
        host=s.get("host", ServerConfig.host),
    )

    # --- behavior ---
    b = raw.get("behavior", {})
    behavior = BehaviorConfig(
        auto_escalate=b.get("auto_escalate", BehaviorConfig.auto_escalate),
        max_workers=b.get("max_workers", BehaviorConfig.max_workers),
        provider_mode=b.get("provider_mode", BehaviorConfig.provider_mode),
    )

    # --- de ---
    d = raw.get("de", {})
    de = DEConfig(override=d.get("override", DEConfig.override))

    # --- voice ---
    v = raw.get("voice", {})
    voice = VoiceConfig(enabled=v.get("enabled", VoiceConfig.enabled))

    return FridayConfig(
        providers=providers,
        server=server,
        behavior=behavior,
        de=de,
        voice=voice,
    )


# ---------------------------------------------------------------------------
# Provider discovery
# ---------------------------------------------------------------------------


def get_available_providers(config: FridayConfig) -> list[str]:
    """Return a list of provider names that are usable with *config*.

    Rules
    -----
    - "ollama"      — always available.
    - "gemini"      — if ``gemini_api_key`` is set.
    - "gemini_cli"  — elif the ``gemini`` binary exists on PATH.
    - "claude"      — if ``claude_api_key`` is set.
    - "claude_cli"  — elif the ``claude`` binary exists on PATH.
    - "openai"      — if ``openai_api_key`` is set (no CLI fallback).
    """
    providers: list[str] = ["ollama"]

    p = config.providers

    # Gemini
    if p.gemini_api_key:
        providers.append("gemini")
    elif shutil.which("gemini"):
        providers.append("gemini_cli")

    # Claude
    if p.claude_api_key:
        providers.append("claude")
    elif shutil.which("claude"):
        providers.append("claude_cli")

    # OpenAI — no CLI fallback
    if p.openai_api_key:
        providers.append("openai")

    return providers


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def get_config_dir() -> Path:
    """Return ``~/.config/friday``."""
    return Path.home() / ".config" / "friday"


def get_data_dir() -> Path:
    """Return ``~/.local/share/friday``."""
    return Path.home() / ".local" / "share" / "friday"


def ensure_dirs() -> None:
    """Create config and data directories (including sub-dirs) if missing."""
    config_dir = get_config_dir()
    data_dir = get_data_dir()

    config_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "memory").mkdir(parents=True, exist_ok=True)
    (data_dir / "history").mkdir(parents=True, exist_ok=True)
