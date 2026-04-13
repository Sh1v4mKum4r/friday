"""Media control tool using playerctl (works on any DE)."""

import subprocess

name = "media"
description = (
    "Control media playback. Actions: 'play', 'pause', 'toggle' (play/pause), "
    "'next', 'previous', 'stop', 'status', 'info' (current track)."
)


def _playerctl(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["playerctl"] + args, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: playerctl not found. Install it: sudo pacman -S playerctl"


def run(action: str = "status") -> str:
    """Control media playback.

    Parameters
    ----------
    action:
        'play', 'pause', 'toggle', 'next', 'previous', 'stop', 'status', 'info'
    """
    lower = action.strip().lower()

    if lower == "play":
        return _playerctl(["play"]) or "Playing."

    elif lower == "pause":
        return _playerctl(["pause"]) or "Paused."

    elif lower == "toggle":
        return _playerctl(["play-pause"]) or "Toggled."

    elif lower == "next":
        return _playerctl(["next"]) or "Skipped to next."

    elif lower in ("previous", "prev"):
        return _playerctl(["previous"]) or "Went to previous."

    elif lower == "stop":
        return _playerctl(["stop"]) or "Stopped."

    elif lower == "status":
        return _playerctl(["status"])

    elif lower == "info":
        title = _playerctl(["metadata", "title"])
        artist = _playerctl(["metadata", "artist"])
        status = _playerctl(["status"])
        if "Error" in title:
            return "No media playing."
        return f"{status}: {artist} — {title}"

    else:
        return "Usage: play, pause, toggle, next, previous, stop, status, info"
