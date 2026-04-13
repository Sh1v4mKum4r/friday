"""Screenshot tool using grim + slurp (works on any Wayland compositor)."""

import subprocess
import os
from datetime import datetime

name = "screenshot"
description = (
    "Take a screenshot. Modes: 'full' for entire screen, 'region' to select an area, "
    "'window' for the focused window. Saves to ~/Pictures/Screenshots/."
)


def _ensure_dir() -> str:
    path = os.path.expanduser("~/Pictures/Screenshots")
    os.makedirs(path, exist_ok=True)
    return path


def run(mode: str = "full") -> str:
    """Take a screenshot.

    Parameters
    ----------
    mode:
        'full' — entire screen
        'region' — select area with mouse (via slurp)
        'window' — focused window (via slurp -o on Hyprland, or full on Cosmic)
    """
    save_dir = _ensure_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = f"{save_dir}/screenshot_{timestamp}.png"

    try:
        if mode == "region":
            # slurp lets user select a region, works on any Wayland
            region = subprocess.run(
                ["slurp"], capture_output=True, text=True, timeout=30,
            )
            if region.returncode != 0:
                return "Cancelled."
            geometry = region.stdout.strip()
            subprocess.run(
                ["grim", "-g", geometry, filepath],
                capture_output=True, timeout=10,
            )
        elif mode == "window":
            # Use slurp to let user click a window
            region = subprocess.run(
                ["slurp"], capture_output=True, text=True, timeout=30,
            )
            if region.returncode != 0:
                return "Cancelled."
            geometry = region.stdout.strip()
            subprocess.run(
                ["grim", "-g", geometry, filepath],
                capture_output=True, timeout=10,
            )
        else:
            # Full screen
            subprocess.run(
                ["grim", filepath],
                capture_output=True, timeout=10,
            )

        if os.path.exists(filepath):
            # Copy to clipboard too
            subprocess.run(
                ["wl-copy", "--type", "image/png"],
                stdin=open(filepath, "rb"), timeout=5,
            )
            return f"Screenshot saved: {filepath} (also copied to clipboard)"
        return "Error: screenshot file not created"

    except FileNotFoundError as e:
        return f"Error: required tool not found — {e}. Install grim and slurp."
    except subprocess.TimeoutExpired:
        return "Error: screenshot timed out (did you forget to select a region?)"
