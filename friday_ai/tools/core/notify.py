"""Desktop notification tool."""

import subprocess

name = "notify"
description = "Send a desktop notification via notify-send."


def run(message: str, title: str = "Friday") -> str:
    """Send a desktop notification with *title* and *message*.

    Returns a success message or an error string.
    """
    try:
        result = subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return "Notification sent."
        return f"Error sending notification (exit code {result.returncode}): {result.stderr}"
    except FileNotFoundError:
        return "Error: notify-send is not installed."
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"
