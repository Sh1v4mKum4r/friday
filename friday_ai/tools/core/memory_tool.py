"""Long-term memory save tool.

Writes directly to MEMORY.md instead of going through the MemoryStore class,
avoiding the module-namespace issue with dynamic tool loading.
"""

from pathlib import Path

name = "memory_save"
description = "Save a piece of information to Friday's long-term memory (MEMORY.md)."

_MEMORY_FILE = Path.home() / ".local" / "share" / "friday" / "memory" / "MEMORY.md"


def run(entry: str) -> str:
    """Append *entry* as a bullet point to MEMORY.md."""
    try:
        _MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = _MEMORY_FILE.read_text().rstrip() if _MEMORY_FILE.exists() else ""
        if existing:
            _MEMORY_FILE.write_text(f"{existing}\n- {entry}\n")
        else:
            _MEMORY_FILE.write_text(f"- {entry}\n")
        return f"Saved to memory: {entry}"
    except Exception as exc:
        return f"Error saving to memory: {exc}"
