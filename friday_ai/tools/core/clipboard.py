"""Clipboard read tool (Wayland)."""

import subprocess

name = "clipboard_get"
description = "Read the current Wayland clipboard contents using wl-paste."


def run() -> str:
    """Return the current clipboard text, or an error if wl-paste is unavailable."""
    try:
        result = subprocess.run(
            ["wl-paste"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout
        return f"Error reading clipboard (exit code {result.returncode}): {result.stderr}"
    except FileNotFoundError:
        return "Error: wl-paste is not installed. Install wl-clipboard to use this tool."
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"
