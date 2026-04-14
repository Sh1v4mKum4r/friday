"""File read tool."""

from pathlib import Path

name = "file_read"
description = "Read the contents of a file. Output is truncated at 10,000 characters."

_MAX_CHARS = 10_000


def run(path: str) -> str:
    """Return the contents of the file at *path*, truncated to 10,000 characters.

    Returns an error string if the file is missing or is not a regular file.
    """
    p = Path(path).expanduser()
    try:
        if not p.exists():
            return f"Error: file not found: {path}"
        if not p.is_file():
            return f"Error: path is not a regular file: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > _MAX_CHARS:
            truncated = content[:_MAX_CHARS]
            return (
                truncated
                + f"\n\n[Output truncated at {_MAX_CHARS} characters. "
                f"File has {len(content)} total characters.]"
            )
        return content
    except PermissionError:
        return f"Error: permission denied reading file: {path}"
    except Exception as exc:  # noqa: BLE001
        return f"Error reading file: {exc}"
