"""Desktop environment command tool."""

import os
import subprocess

name = "de_command"
description = (
    "Execute a desktop environment command. Auto-detects Hyprland or Cosmic. "
    "For Hyprland pass a hyprctl sub-command (e.g. 'dispatch exec kitty'). "
    "For Cosmic pass a busctl method call argument string."
)

_COSMIC_BUSCTL_PREFIX = [
    "busctl",
    "call",
    "com.system76.CosmicComp",
    "/com/system76/CosmicComp",
    "com.system76.CosmicComp",
]


def _detect_de() -> str:
    """Return 'hyprland', 'cosmic', or 'unknown'."""
    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "hyprland" in xdg:
        return "hyprland"
    if "cosmic" in xdg:
        return "cosmic"

    # Fallback: check running processes
    for proc, de in [("Hyprland", "hyprland"), ("cosmic-comp", "cosmic")]:
        try:
            result = subprocess.run(
                ["pgrep", "-x", proc],
                capture_output=True,
                timeout=3,
            )
            if result.returncode == 0:
                return de
        except Exception:  # noqa: BLE001
            pass

    return "unknown"


def run(cmd: str) -> str:
    """Execute *cmd* on the detected desktop environment.

    For Hyprland, *cmd* is passed as arguments to ``hyprctl``.
    For Cosmic, *cmd* is appended to the busctl call prefix.
    """
    de = _detect_de()
    env = os.environ.copy()

    try:
        if de == "hyprland":
            args = ["hyprctl"] + cmd.split()
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
        elif de == "cosmic":
            args = _COSMIC_BUSCTL_PREFIX + cmd.split()
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
        else:
            return "Error: could not detect desktop environment (not Hyprland or Cosmic)."

        if result.returncode == 0:
            return result.stdout or "Command executed successfully."
        return (
            f"Error (exit code {result.returncode}):\n"
            f"{result.stderr or result.stdout}"
        )
    except FileNotFoundError as exc:
        return f"Error: required binary not found — {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"
