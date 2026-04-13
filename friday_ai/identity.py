"""Identity system for Friday AI.

Loads personality and context files (SOUL.md, USER.md, AGENTS.md,
BOOTSTRAP.md) from a config directory and assembles them into a
structured system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class Identity:
    soul: str
    user: str
    agents: str
    bootstrap: str | None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_identity(config_dir: Path) -> Identity:
    """Read identity files from *config_dir* and return an :class:`Identity`.

    Missing files return empty strings for ``soul``, ``user``, and
    ``agents``, and ``None`` for ``bootstrap``.
    """

    def _read(filename: str) -> str:
        path = config_dir / filename
        try:
            return path.read_text()
        except (FileNotFoundError, OSError):
            return ""

    soul = _read("SOUL.md")
    user = _read("USER.md")
    agents = _read("AGENTS.md")

    bootstrap_path = config_dir / "BOOTSTRAP.md"
    try:
        bootstrap: str | None = bootstrap_path.read_text()
    except (FileNotFoundError, OSError):
        bootstrap = None

    return Identity(soul=soul, user=user, agents=agents, bootstrap=bootstrap)


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def build_system_prompt(
    identity: Identity,
    tools_desc: str,
    memory_context: str = "",
) -> str:
    """Assemble a system prompt from identity sections, tools, and memory.

    Sections included:
    - **Personality** — from ``identity.soul``
    - **About the User** — from ``identity.user``
    - **Worker Rules** — from ``identity.agents``
    - **Available Tools** — from ``tools_desc``
    - **Memory Context** — from ``memory_context`` (omitted when empty)
    - **FIRST RUN** — from ``identity.bootstrap`` (omitted when None or empty)
    """
    sections: list[str] = []

    sections.append(f"# Personality\n\n{identity.soul}")
    sections.append(f"# About the User\n\n{identity.user}")
    sections.append(f"# Worker Rules\n\n{identity.agents}")
    sections.append(f"# Available Tools\n\n{tools_desc}")

    if memory_context:
        sections.append(f"# Memory Context\n\n{memory_context}")

    if identity.bootstrap:
        sections.append(f"# FIRST RUN\n\n{identity.bootstrap}")

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def update_identity_file(path: Path, content: str) -> None:
    """Write *content* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def delete_bootstrap(config_dir: Path) -> None:
    """Delete BOOTSTRAP.md from *config_dir* if it exists."""
    bootstrap = config_dir / "BOOTSTRAP.md"
    try:
        bootstrap.unlink()
    except FileNotFoundError:
        pass
