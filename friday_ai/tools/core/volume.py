"""Volume control tool using wpctl/PipeWire (works on any DE)."""

import subprocess

name = "volume"
description = (
    "Control system volume. Examples: 'get' for current level, "
    "'set 50' for 50%, 'up' or 'down' by 5%, 'mute', 'unmute', 'toggle'."
)


def _wpctl(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["wpctl"] + args, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: wpctl not found. Is PipeWire installed?"


def run(action: str = "get") -> str:
    """Control volume.

    Parameters
    ----------
    action:
        'get' — show current volume
        'set <percent>' — set volume (0-100)
        'up' — increase by 5%
        'down' — decrease by 5%
        'mute' — mute audio
        'unmute' — unmute audio
        'toggle' — toggle mute
    """
    lower = action.strip().lower()

    if lower == "get":
        output = _wpctl(["get-volume", "@DEFAULT_AUDIO_SINK@"])
        return output if output else "Could not get volume."

    elif lower.startswith("set "):
        percent = lower.split(None, 1)[1].rstrip("%")
        try:
            val = float(percent) / 100
        except ValueError:
            return "Error: invalid percentage"
        return _wpctl(["set-volume", "@DEFAULT_AUDIO_SINK@", str(val)])
        return f"Volume set to {percent}%."

    elif lower == "up":
        _wpctl(["set-volume", "@DEFAULT_AUDIO_SINK@", "5%+"])
        return "Volume increased."

    elif lower == "down":
        _wpctl(["set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"])
        return "Volume decreased."

    elif lower == "mute":
        _wpctl(["set-mute", "@DEFAULT_AUDIO_SINK@", "1"])
        return "Audio muted."

    elif lower == "unmute":
        _wpctl(["set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
        return "Audio unmuted."

    elif lower == "toggle":
        _wpctl(["set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
        return "Mute toggled."

    else:
        return "Usage: get, set <percent>, up, down, mute, unmute, toggle"
