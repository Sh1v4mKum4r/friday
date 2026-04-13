"""Memory system for Friday AI.

Manages three persistence layers:
- MEMORY.md       — long-term bullet-point facts Friday has learned
- YYYY-MM-DD.md   — daily interaction logs (stored in memory/)
- session-*.json  — full conversation history (stored in history/)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class MemoryStore:
    """Persistent memory for Friday, backed by flat files under *data_dir*.

    Directory layout::

        data_dir/
            memory/
                MEMORY.md          ← long-term facts
                YYYY-MM-DD.md      ← daily logs
            history/
                session-YYYY-MM-DD_HH-MM-SS.json
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.memory_dir = data_dir / "memory"
        self.history_dir = data_dir / "history"
        self.memory_file = self.memory_dir / "MEMORY.md"

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Long-term memory (MEMORY.md)
    # ------------------------------------------------------------------

    def read_memory(self) -> str:
        """Return the full contents of MEMORY.md, or "" if it doesn't exist."""
        try:
            return self.memory_file.read_text()
        except (FileNotFoundError, OSError):
            return ""

    def write_memory(self, entry: str) -> None:
        """Append ``- {entry}`` as a new bullet line to MEMORY.md."""
        with self.memory_file.open("a") as fh:
            fh.write(f"- {entry}\n")

    def forget_memory(self, keyword: str) -> None:
        """Remove all lines from MEMORY.md that contain *keyword* (case-insensitive)."""
        if not self.memory_file.exists():
            return

        lower_kw = keyword.lower()
        lines = self.memory_file.read_text().splitlines(keepends=True)
        kept = [line for line in lines if lower_kw not in line.lower()]
        self.memory_file.write_text("".join(kept))

    def list_memory(self) -> list[str]:
        """Return bullet-point entries from MEMORY.md as a list, stripped of the ``- `` prefix."""
        contents = self.read_memory()
        items: list[str] = []
        for line in contents.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(stripped[2:])
        return items

    def clear_memory(self) -> None:
        """Empty MEMORY.md (creates it if absent)."""
        self.memory_file.write_text("")

    # ------------------------------------------------------------------
    # Daily logs (memory/YYYY-MM-DD.md)
    # ------------------------------------------------------------------

    def append_daily_log(self, entry: str) -> None:
        """Append a timestamped *entry* to today's daily log file.

        Creates the file with a ``# YYYY-MM-DD`` header if it is new.
        """
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"{today}.md"

        if not log_file.exists():
            log_file.write_text(f"# {today}\n\n")

        timestamp = now.strftime("%H:%M:%S")
        with log_file.open("a") as fh:
            fh.write(f"[{timestamp}] {entry}\n")

    def _today_log_path(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.memory_dir / f"{today}.md"

    # ------------------------------------------------------------------
    # Session history (history/session-*.json)
    # ------------------------------------------------------------------

    def save_session(self, messages: list[dict]) -> Path:
        """Save *messages* as JSON to a timestamped file in *history_dir*.

        Returns the :class:`~pathlib.Path` of the written file.
        """
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"session-{timestamp_str}.json"
        path = self.history_dir / filename

        payload = {
            "timestamp": now.isoformat(),
            "messages": messages,
        }
        path.write_text(json.dumps(payload, indent=2))
        return path

    def load_latest_session(self) -> list[dict] | None:
        """Return messages from the most recent session file, or ``None`` if none exist."""
        session_files = sorted(self.history_dir.glob("session-*.json"))
        if not session_files:
            return None

        latest = session_files[-1]
        data = json.loads(latest.read_text())
        return data["messages"]

    # ------------------------------------------------------------------
    # Prompt context assembly
    # ------------------------------------------------------------------

    def get_context_for_prompt(self) -> str:
        """Combine MEMORY.md and today's daily log into a context string.

        Returns an empty string when both sources are empty/missing.
        Sections are labelled ``## Memory`` and ``## Today's Log``.
        """
        sections: list[str] = []

        memory_text = self.read_memory().strip()
        if memory_text:
            sections.append(f"## Memory\n\n{memory_text}")

        log_path = self._today_log_path()
        if log_path.exists():
            log_text = log_path.read_text().strip()
            if log_text:
                sections.append(f"## Today's Log\n\n{log_text}")

        return "\n\n".join(sections)
