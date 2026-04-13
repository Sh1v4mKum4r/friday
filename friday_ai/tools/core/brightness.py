"""Brightness control tool using brightnessctl (works on any DE)."""

import subprocess

name = "brightness"
description = (
    "Control screen brightness. Examples: 'get' to show current, "
    "'set 50' for 50%, 'up' or 'down' to adjust by 10%, 'max' or 'min'."
)


def run(action: str = "get") -> str:
    """Control brightness.

    Parameters
    ----------
    action:
        'get' — current brightness
        'set <percent>' — set to exact percentage (0-100)
        'up' — increase by 10%
        'down' — decrease by 10%
        'max' — set to 100%
        'min' — set to 1% (not 0, to avoid black screen)
    """
    try:
        lower = action.strip().lower()

        if lower == "get":
            result = subprocess.run(
                ["brightnessctl", "info"], capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr}"

        elif lower.startswith("set "):
            percent = lower.split(None, 1)[1].rstrip("%")
            result = subprocess.run(
                ["brightnessctl", "set", f"{percent}%"],
                capture_output=True, text=True, timeout=5,
            )
            return f"Brightness set to {percent}%." if result.returncode == 0 else f"Error: {result.stderr}"

        elif lower == "up":
            result = subprocess.run(
                ["brightnessctl", "set", "+10%"],
                capture_output=True, text=True, timeout=5,
            )
            return "Brightness increased." if result.returncode == 0 else f"Error: {result.stderr}"

        elif lower == "down":
            result = subprocess.run(
                ["brightnessctl", "set", "10%-"],
                capture_output=True, text=True, timeout=5,
            )
            return "Brightness decreased." if result.returncode == 0 else f"Error: {result.stderr}"

        elif lower == "max":
            subprocess.run(["brightnessctl", "set", "100%"], capture_output=True, timeout=5)
            return "Brightness set to maximum."

        elif lower == "min":
            subprocess.run(["brightnessctl", "set", "1%"], capture_output=True, timeout=5)
            return "Brightness set to minimum (1%)."

        else:
            return "Usage: get, set <percent>, up, down, max, min"

    except FileNotFoundError:
        return "Error: brightnessctl not found. Install it: sudo pacman -S brightnessctl"
