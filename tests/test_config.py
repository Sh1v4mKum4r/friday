"""Tests for friday_ai/config.py — written before implementation (TDD)."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from friday_ai.config import (
    BehaviorConfig,
    DEConfig,
    FridayConfig,
    ProvidersConfig,
    ServerConfig,
    VoiceConfig,
    ensure_dirs,
    get_available_providers,
    get_config_dir,
    get_data_dir,
    load_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_TOML = """\
[providers]
ollama_model = "qwen2.5:7b"
ollama_url = "http://localhost:11434"
gemini_api_key = ""
claude_api_key = ""
openai_api_key = ""
gemini_model = "gemini-2.5-flash"
claude_model = "claude-sonnet-4-6"
openai_model = "gpt-4o"

[server]
port = 65535
host = "127.0.0.1"

[behavior]
auto_escalate = true
max_workers = 4
provider_mode = "fallback"

[de]
override = ""

[voice]
enabled = false
"""


def write_toml(content: str) -> str:
    """Write *content* to a NamedTemporaryFile and return its path (file is NOT deleted on close)."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False)
    f.write(content)
    f.flush()
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# 1. Load config from TOML — verify all fields parsed correctly
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_friday_config(self):
        path = write_toml(MINIMAL_TOML)
        try:
            cfg = load_config(path)
            assert isinstance(cfg, FridayConfig)
        finally:
            os.unlink(path)

    def test_providers_section(self):
        path = write_toml(MINIMAL_TOML)
        try:
            cfg = load_config(path)
            assert isinstance(cfg.providers, ProvidersConfig)
            assert cfg.providers.ollama_model == "qwen2.5:7b"
            assert cfg.providers.ollama_url == "http://localhost:11434"
            assert cfg.providers.gemini_api_key == ""
            assert cfg.providers.claude_api_key == ""
            assert cfg.providers.openai_api_key == ""
        finally:
            os.unlink(path)

    def test_server_section(self):
        path = write_toml(MINIMAL_TOML)
        try:
            cfg = load_config(path)
            assert isinstance(cfg.server, ServerConfig)
            assert cfg.server.port == 65535
            assert cfg.server.host == "127.0.0.1"
        finally:
            os.unlink(path)

    def test_behavior_section(self):
        path = write_toml(MINIMAL_TOML)
        try:
            cfg = load_config(path)
            assert isinstance(cfg.behavior, BehaviorConfig)
            assert cfg.behavior.auto_escalate is True
            assert cfg.behavior.max_workers == 4
        finally:
            os.unlink(path)

    def test_de_section(self):
        path = write_toml(MINIMAL_TOML)
        try:
            cfg = load_config(path)
            assert isinstance(cfg.de, DEConfig)
            assert cfg.de.override == ""
        finally:
            os.unlink(path)

    def test_voice_section(self):
        path = write_toml(MINIMAL_TOML)
        try:
            cfg = load_config(path)
            assert isinstance(cfg.voice, VoiceConfig)
            assert cfg.voice.enabled is False
        finally:
            os.unlink(path)

    def test_with_api_keys_set(self):
        toml = MINIMAL_TOML.replace('gemini_api_key = ""', 'gemini_api_key = "g-abc"')
        toml = toml.replace('claude_api_key = ""', 'claude_api_key = "sk-ant-xyz"')
        toml = toml.replace('openai_api_key = ""', 'openai_api_key = "sk-oai-123"')
        path = write_toml(toml)
        try:
            cfg = load_config(path)
            assert cfg.providers.gemini_api_key == "g-abc"
            assert cfg.providers.claude_api_key == "sk-ant-xyz"
            assert cfg.providers.openai_api_key == "sk-oai-123"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 2. Environment variable override for API keys
# ---------------------------------------------------------------------------


class TestEnvVarOverrides:
    """When a field is empty in TOML, the env var must fill it in."""

    def test_gemini_api_key_from_env(self):
        path = write_toml(MINIMAL_TOML)
        try:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "env-gemini-key"}):
                cfg = load_config(path)
            assert cfg.providers.gemini_api_key == "env-gemini-key"
        finally:
            os.unlink(path)

    def test_claude_api_key_from_env(self):
        path = write_toml(MINIMAL_TOML)
        try:
            with patch.dict(os.environ, {"CLAUDE_API_KEY": "env-claude-key"}):
                cfg = load_config(path)
            assert cfg.providers.claude_api_key == "env-claude-key"
        finally:
            os.unlink(path)

    def test_openai_api_key_from_env(self):
        path = write_toml(MINIMAL_TOML)
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "env-openai-key"}):
                cfg = load_config(path)
            assert cfg.providers.openai_api_key == "env-openai-key"
        finally:
            os.unlink(path)

    def test_toml_value_takes_precedence_over_env(self):
        """Non-empty TOML value must NOT be overwritten by env var."""
        toml = MINIMAL_TOML.replace('gemini_api_key = ""', 'gemini_api_key = "toml-key"')
        path = write_toml(toml)
        try:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "env-should-not-win"}):
                cfg = load_config(path)
            assert cfg.providers.gemini_api_key == "toml-key"
        finally:
            os.unlink(path)

    def test_env_var_not_set_leaves_field_empty(self):
        path = write_toml(MINIMAL_TOML)
        try:
            env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY")}
            with patch.dict(os.environ, env, clear=True):
                cfg = load_config(path)
            assert cfg.providers.gemini_api_key == ""
            assert cfg.providers.claude_api_key == ""
            assert cfg.providers.openai_api_key == ""
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 3. get_available_providers — correct providers based on config
# ---------------------------------------------------------------------------


class TestGetAvailableProviders:
    def _cfg(self, gemini_key="", claude_key="", openai_key="") -> FridayConfig:
        toml = MINIMAL_TOML
        toml = toml.replace('gemini_api_key = ""', f'gemini_api_key = "{gemini_key}"')
        toml = toml.replace('claude_api_key = ""', f'claude_api_key = "{claude_key}"')
        toml = toml.replace('openai_api_key = ""', f'openai_api_key = "{openai_key}"')
        path = write_toml(toml)
        try:
            return load_config(path)
        finally:
            os.unlink(path)

    def test_ollama_always_included(self):
        cfg = self._cfg()
        with patch("shutil.which", return_value=None):
            providers = get_available_providers(cfg)
        assert "ollama" in providers

    def test_gemini_with_api_key(self):
        cfg = self._cfg(gemini_key="real-key")
        providers = get_available_providers(cfg)
        assert "gemini" in providers
        assert "gemini_cli" not in providers

    def test_gemini_cli_fallback_when_binary_exists(self):
        cfg = self._cfg()  # no key

        def fake_which(name):
            return "/usr/bin/gemini" if name == "gemini" else None

        with patch("shutil.which", side_effect=fake_which):
            providers = get_available_providers(cfg)
        assert "gemini_cli" in providers
        assert "gemini" not in providers

    def test_gemini_absent_when_no_key_and_no_binary(self):
        cfg = self._cfg()
        with patch("shutil.which", return_value=None):
            providers = get_available_providers(cfg)
        assert "gemini" not in providers
        assert "gemini_cli" not in providers

    def test_claude_with_api_key(self):
        cfg = self._cfg(claude_key="sk-ant-real")
        providers = get_available_providers(cfg)
        assert "claude" in providers
        assert "claude_cli" not in providers

    def test_claude_cli_fallback_when_binary_exists(self):
        cfg = self._cfg()

        def fake_which(name):
            return "/usr/local/bin/claude" if name == "claude" else None

        with patch("shutil.which", side_effect=fake_which):
            providers = get_available_providers(cfg)
        assert "claude_cli" in providers
        assert "claude" not in providers

    def test_claude_absent_when_no_key_and_no_binary(self):
        cfg = self._cfg()
        with patch("shutil.which", return_value=None):
            providers = get_available_providers(cfg)
        assert "claude" not in providers
        assert "claude_cli" not in providers

    def test_openai_with_api_key(self):
        cfg = self._cfg(openai_key="sk-oai-real")
        providers = get_available_providers(cfg)
        assert "openai" in providers

    def test_openai_absent_when_no_key(self):
        cfg = self._cfg()
        providers = get_available_providers(cfg)
        assert "openai" not in providers

    def test_all_providers_present(self):
        cfg = self._cfg(gemini_key="g", claude_key="c", openai_key="o")
        providers = get_available_providers(cfg)
        assert "ollama" in providers
        assert "gemini" in providers
        assert "claude" in providers
        assert "openai" in providers


# ---------------------------------------------------------------------------
# 4. Directory helpers
# ---------------------------------------------------------------------------


class TestDirectoryHelpers:
    def test_get_config_dir(self):
        d = get_config_dir()
        assert d == Path.home() / ".config" / "friday"

    def test_get_data_dir(self):
        d = get_data_dir()
        assert d == Path.home() / ".local" / "share" / "friday"

    def test_ensure_dirs_creates_directories(self, tmp_path):
        with (
            patch("friday_ai.config.get_config_dir", return_value=tmp_path / "config"),
            patch("friday_ai.config.get_data_dir", return_value=tmp_path / "data"),
        ):
            ensure_dirs()
        assert (tmp_path / "config").is_dir()
        assert (tmp_path / "data" / "memory").is_dir()
        assert (tmp_path / "data" / "history").is_dir()
