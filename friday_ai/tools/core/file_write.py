"""File write tool."""

from pathlib import Path

name = "file_write"
description = "Write text content to a file, creating parent directories as needed."


def run(path: str, content: str) -> str:
    """Write *content* to the file at *path*.

    Parent directories are created automatically if they do not exist.
    Returns a success message or an error string.
    """
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {path}."
    except PermissionError:
        return f"Error: permission denied writing to: {path}"
    except Exception as exc:  # noqa: BLE001
        return f"Error writing file: {exc}"
