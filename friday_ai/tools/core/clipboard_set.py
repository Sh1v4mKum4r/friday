"""Clipboard write tool (Wayland)."""

import subprocess

name = "clipboard_set"
description = "Write text to the Wayland clipboard using wl-copy."


def run(content: str) -> str:
    """Write *content* to the Wayland clipboard via wl-copy.

    Returns a success message or an error string.
    """
    try:
        proc = subprocess.Popen(
            ["wl-copy"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = proc.communicate(input=content.encode(), timeout=5)
        if proc.returncode == 0:
            return "Clipboard updated successfully."
        return f"Error writing to clipboard (exit code {proc.returncode}): {stderr.decode()}"
    except FileNotFoundError:
        return "Error: wl-copy is not installed. Install wl-clipboard to use this tool."
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"
