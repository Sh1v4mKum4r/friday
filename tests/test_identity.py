"""Tests for friday_ai/identity.py — written before implementation (TDD)."""
import tempfile
from pathlib import Path

import pytest

from friday_ai.identity import (
    Identity,
    build_system_prompt,
    delete_bootstrap,
    load_identity,
    update_identity_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config_dir(
    tmp: Path,
    soul: str = "",
    user: str = "",
    agents: str = "",
    bootstrap: str | None = None,
) -> Path:
    """Populate a temp directory with identity files and return its Path."""
    config_dir = tmp / "config"
    config_dir.mkdir()

    if soul:
        (config_dir / "SOUL.md").write_text(soul)
    if user:
        (config_dir / "USER.md").write_text(user)
    if agents:
        (config_dir / "AGENTS.md").write_text(agents)
    if bootstrap is not None:
        (config_dir / "BOOTSTRAP.md").write_text(bootstrap)

    return config_dir


# ---------------------------------------------------------------------------
# 1. load_identity — all files present
# ---------------------------------------------------------------------------


class TestLoadIdentityAllPresent:
    def test_returns_identity_dataclass(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = make_config_dir(
                Path(tmp),
                soul="You are Friday.",
                user="User is a developer.",
                agents="Workers obey rules.",
                bootstrap="First run ritual.",
            )
            identity = load_identity(config_dir)
        assert isinstance(identity, Identity)

    def test_soul_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = make_config_dir(Path(tmp), soul="My soul content.")
            identity = load_identity(config_dir)
        assert identity.soul == "My soul content."

    def test_user_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = make_config_dir(Path(tmp), user="User info here.")
            identity = load_identity(config_dir)
        assert identity.user == "User info here."

    def test_agents_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = make_config_dir(Path(tmp), agents="Agent rules here.")
            identity = load_identity(config_dir)
        assert identity.agents == "Agent rules here."

    def test_bootstrap_loaded_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = make_config_dir(Path(tmp), bootstrap="Bootstrap ritual.")
            identity = load_identity(config_dir)
        assert identity.bootstrap == "Bootstrap ritual."


# ---------------------------------------------------------------------------
# 2. load_identity — missing files return empty strings (None for bootstrap)
# ---------------------------------------------------------------------------


class TestLoadIdentityMissingFiles:
    def test_soul_empty_string_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            identity = load_identity(config_dir)
        assert identity.soul == ""

    def test_user_empty_string_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            identity = load_identity(config_dir)
        assert identity.user == ""

    def test_agents_empty_string_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            identity = load_identity(config_dir)
        assert identity.agents == ""

    def test_bootstrap_none_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            identity = load_identity(config_dir)
        assert identity.bootstrap is None

    def test_nonexistent_config_dir_returns_empty_identity(self):
        """load_identity on a nonexistent directory should still return empty Identity."""
        nonexistent = Path("/tmp/nonexistent_friday_config_xyz_abc_123")
        identity = load_identity(nonexistent)
        assert identity.soul == ""
        assert identity.user == ""
        assert identity.agents == ""
        assert identity.bootstrap is None


# ---------------------------------------------------------------------------
# 3. build_system_prompt — includes soul, user, and tools
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def _make_identity(self, **kwargs):
        defaults = dict(soul="Soul text.", user="User text.", agents="Agent text.", bootstrap=None)
        defaults.update(kwargs)
        return Identity(**defaults)

    def test_includes_soul_content(self):
        identity = self._make_identity(soul="I am Friday, your AI.")
        prompt = build_system_prompt(identity, tools_desc="no tools")
        assert "I am Friday, your AI." in prompt

    def test_includes_user_content(self):
        identity = self._make_identity(user="User is a VIT student.")
        prompt = build_system_prompt(identity, tools_desc="no tools")
        assert "User is a VIT student." in prompt

    def test_includes_tools_desc(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="tool: search_web")
        assert "tool: search_web" in prompt

    def test_includes_agents_content(self):
        identity = self._make_identity(agents="Workers must be precise.")
        prompt = build_system_prompt(identity, tools_desc="")
        assert "Workers must be precise." in prompt

    def test_personality_section_label(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="")
        assert "Personality" in prompt

    def test_about_the_user_section_label(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="")
        assert "About the User" in prompt

    def test_worker_rules_section_label(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="")
        assert "Worker Rules" in prompt

    def test_available_tools_section_label(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="some tool")
        assert "Available Tools" in prompt

    def test_memory_context_included_when_provided(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="", memory_context="past memory item")
        assert "past memory item" in prompt
        assert "Memory Context" in prompt

    def test_memory_context_section_absent_when_empty(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="", memory_context="")
        assert "Memory Context" not in prompt

    def test_returns_string(self):
        identity = self._make_identity()
        prompt = build_system_prompt(identity, tools_desc="")
        assert isinstance(prompt, str)


# ---------------------------------------------------------------------------
# 4. Bootstrap detection — FIRST RUN section when BOOTSTRAP.md exists
# ---------------------------------------------------------------------------


class TestBootstrapDetection:
    def test_first_run_section_present_when_bootstrap_set(self):
        identity = Identity(
            soul="Soul.", user="User.", agents="Agents.", bootstrap="Do the first-run thing."
        )
        prompt = build_system_prompt(identity, tools_desc="")
        assert "FIRST RUN" in prompt
        assert "Do the first-run thing." in prompt

    def test_first_run_section_absent_when_bootstrap_none(self):
        identity = Identity(soul="Soul.", user="User.", agents="Agents.", bootstrap=None)
        prompt = build_system_prompt(identity, tools_desc="")
        assert "FIRST RUN" not in prompt

    def test_first_run_section_absent_when_bootstrap_empty_string(self):
        """An empty bootstrap string should not produce a FIRST RUN section."""
        identity = Identity(soul="Soul.", user="User.", agents="Agents.", bootstrap="")
        prompt = build_system_prompt(identity, tools_desc="")
        assert "FIRST RUN" not in prompt


# ---------------------------------------------------------------------------
# 5. update_identity_file — writes content to path
# ---------------------------------------------------------------------------


class TestUpdateIdentityFile:
    def test_creates_file_with_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SOUL.md"
            update_identity_file(path, "New soul content.")
            assert path.read_text() == "New soul content."

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "USER.md"
            path.write_text("Old content.")
            update_identity_file(path, "Updated content.")
            assert path.read_text() == "Updated content."

    def test_creates_parent_dirs_if_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "dir" / "SOUL.md"
            update_identity_file(path, "Nested soul.")
            assert path.read_text() == "Nested soul."

    def test_empty_content_writes_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENTS.md"
            update_identity_file(path, "")
            assert path.read_text() == ""


# ---------------------------------------------------------------------------
# 6. delete_bootstrap — removes BOOTSTRAP.md if present
# ---------------------------------------------------------------------------


class TestDeleteBootstrap:
    def test_removes_bootstrap_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            bootstrap = config_dir / "BOOTSTRAP.md"
            bootstrap.write_text("First run.")
            delete_bootstrap(config_dir)
            assert not bootstrap.exists()

    def test_no_error_when_bootstrap_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            # BOOTSTRAP.md does not exist — should not raise
            delete_bootstrap(config_dir)

    def test_other_files_not_affected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            soul = config_dir / "SOUL.md"
            soul.write_text("Soul here.")
            bootstrap = config_dir / "BOOTSTRAP.md"
            bootstrap.write_text("Bootstrap.")
            delete_bootstrap(config_dir)
            assert soul.exists()
            assert soul.read_text() == "Soul here."
