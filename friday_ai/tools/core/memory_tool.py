"""Long-term memory save tool.

Writes directly to MEMORY.md with dedup protection.
"""

from pathlib import Path

name = "memory_save"
description = "Save a piece of information to Friday's long-term memory (MEMORY.md). Do NOT save trivial things like math results."

_MEMORY_FILE = Path.home() / ".local" / "share" / "friday" / "memory" / "MEMORY.md"


def run(entry: str) -> str:
    """Append *entry* as a bullet point to MEMORY.md. Skips duplicates."""
    if not entry or not entry.strip():
        return "Error: cannot save empty entry."
    entry = entry.strip()

    # Skip trivial entries
    trivial = ["5 + 5", "2 + 2", "hello", "hi", "yes", "no", "ok"]
    if any(t in entry.lower() for t in trivial):
        return "Skipped: trivial entry not worth saving."

    try:
        _MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = _MEMORY_FILE.read_text() if _MEMORY_FILE.exists() else ""

        # Dedup: check if this entry (or something very similar) already exists
        existing_lower = existing.lower()
        entry_lower = entry.lower()
        for line in existing_lower.splitlines():
            line = line.lstrip("- ").strip()
            if not line:
                continue
            # Exact match or substring match
            if entry_lower == line or entry_lower in line or line in entry_lower:
                return f"Already in memory: {entry}"

        existing = existing.rstrip()
        if existing:
            _MEMORY_FILE.write_text(f"{existing}\n- {entry}\n")
        else:
            _MEMORY_FILE.write_text(f"- {entry}\n")
        return f"Saved to memory: {entry}"
    except Exception as exc:
        return f"Error saving to memory: {exc}"
