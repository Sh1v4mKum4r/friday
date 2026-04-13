"""Long-term memory save tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from friday_ai.memory import MemoryStore

name = "memory_save"
description = "Save a piece of information to Friday's long-term memory (MEMORY.md)."

_memory_store: "MemoryStore | None" = None


def set_store(store: "MemoryStore") -> None:
    """Inject the :class:`~friday_ai.memory.MemoryStore` instance at runtime."""
    global _memory_store  # noqa: PLW0603
    _memory_store = store


def run(entry: str) -> str:
    """Append *entry* as a bullet point to long-term memory.

    Returns a success message, or an error if the memory store has not been
    initialised via :func:`set_store`.
    """
    if _memory_store is None:
        return "Error: memory store is not initialised. Call set_store() before using this tool."
    try:
        _memory_store.write_memory(entry)
        return f"Saved to memory: {entry}"
    except Exception as exc:  # noqa: BLE001
        return f"Error saving to memory: {exc}"
