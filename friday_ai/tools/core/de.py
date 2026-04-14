"""Desktop environment command tool.

Supports both Hyprland (via hyprctl) and Cosmic (via cosmic-randr, dbus, xdg-utils).
Auto-detects the active compositor at runtime.
"""

import os
import subprocess
import shutil

name = "de_command"
description = (
    "Control the desktop environment — manage windows, workspaces, and settings. "
    "Examples: 'focus left', 'workspace 3', 'move window right', 'fullscreen', "
    "'list windows', 'launch kitty'. Works on both Hyprland and Cosmic."
)

# -----------------------------------------------------------------------
# DE detection (cached after first call)
# -----------------------------------------------------------------------

_cached_de: str | None = None


def _detect_de() -> str:
    global _cached_de
    if _cached_de is not None:
        return _cached_de

    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "hyprland" in xdg:
        _cached_de = "hyprland"
    elif "cosmic" in xdg:
        _cached_de = "cosmic"
    else:
        # Fallback: check running processes
        for proc, de in [("Hyprland", "hyprland"), ("cosmic-comp", "cosmic")]:
            try:
                result = subprocess.run(
                    ["pgrep", "-x", proc], capture_output=True, timeout=3,
                )
                if result.returncode == 0:
                    _cached_de = de
                    return _cached_de
            except Exception:
                pass
        _cached_de = "unknown"

    return _cached_de


def _wayland_env() -> dict:
    """Return os.environ with essential Wayland variables ensured."""
    env = os.environ.copy()
    # These are needed when the Python backend runs as a service
    for var in ("WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "HYPRLAND_INSTANCE_SIGNATURE"):
        if var not in env:
            # Try to read from /proc of the compositor
            try:
                procs = subprocess.run(
                    ["pgrep", "-x", "Hyprland" if _detect_de() == "hyprland" else "cosmic-comp"],
                    capture_output=True, text=True, timeout=3,
                )
                if procs.returncode == 0:
                    pid = procs.stdout.strip().split("\n")[0]
                    environ_file = f"/proc/{pid}/environ"
                    if os.path.exists(environ_file):
                        with open(environ_file, "rb") as f:
                            env_data = f.read()
                        for entry in env_data.split(b"\x00"):
                            if entry.startswith(var.encode() + b"="):
                                env[var] = entry.decode().split("=", 1)[1]
            except Exception:
                pass
    return env


# -----------------------------------------------------------------------
# Command helpers
# -----------------------------------------------------------------------

def _run(args: list[str], env: dict) -> str:
    """Run a subprocess and return stdout or error."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=10, env=env,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "Done."
        return f"Error (exit {result.returncode}): {(result.stderr or result.stdout).strip()}"
    except FileNotFoundError:
        return f"Error: {args[0]} not found"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out"


# -----------------------------------------------------------------------
# Hyprland commands via hyprctl
# -----------------------------------------------------------------------

_HYPR_ALIASES = {
    "focus left": "dispatch movefocus l",
    "focus right": "dispatch movefocus r",
    "focus up": "dispatch movefocus u",
    "focus down": "dispatch movefocus d",
    "move window left": "dispatch movewindow l",
    "move window right": "dispatch movewindow r",
    "move window up": "dispatch movewindow u",
    "move window down": "dispatch movewindow d",
    "fullscreen": "dispatch fullscreen 0",
    "float": "dispatch togglefloating",
    "list windows": "clients",
    "list workspaces": "workspaces",
    "active window": "activewindow",
}


def _hyprland(cmd: str, env: dict) -> str:
    # Check aliases first
    alias = _HYPR_ALIASES.get(cmd.lower())
    if alias:
        return _run(["hyprctl"] + alias.split(), env)

    # Workspace switch: "workspace N"
    if cmd.lower().startswith("workspace "):
        num = cmd.split(None, 1)[1]
        return _run(["hyprctl", "dispatch", "workspace", num], env)

    # Launch app: "launch <app>"
    if cmd.lower().startswith("launch "):
        app = cmd.split(None, 1)[1]
        return _run(["hyprctl", "dispatch", "exec", app], env)

    # Pass through as raw hyprctl command
    return _run(["hyprctl"] + cmd.split(), env)


# -----------------------------------------------------------------------
# Cosmic commands via cosmic-randr, busctl, and xdg-utils
# -----------------------------------------------------------------------

# Cosmic doesn't have a single hyprctl-like CLI. It uses:
# - cosmic-randr for display management
# - DBus com.system76.CosmicComp for compositor control
# - xdg-utils for launching apps
# - xdotool/wlrctl for window management (if available)

def _cosmic(cmd: str, env: dict) -> str:
    lower = cmd.lower()

    # Workspace switch: "workspace N"
    if lower.startswith("workspace "):
        num = cmd.split(None, 1)[1]
        if num.isdigit():
            # Use wtype to simulate Super+N
            return _run(["wtype", "-M", "logo", "-k", num, "-m", "logo"], env)
        return f"Error: invalid workspace number '{num}'"

    # Launch app: "launch <app>"
    if lower.startswith("launch "):
        app = cmd.split(None, 1)[1]
        if shutil.which("cosmic-app-launcher"):
            return _run(["cosmic-app-launcher", "--", app], env)
        return _run(["xdg-open", app] if "/" in app else ["gio", "launch", app], env)

    # Window focus
    if lower.startswith("focus "):
        direction = cmd.split(None, 1)[1].lower()
        key_map = {"left": "Left", "right": "Right", "up": "Up", "down": "Down"}
        if direction in key_map:
            return _run(["wtype", "-M", "logo", "-k", key_map[direction], "-m", "logo"], env)
        return f"Error: unknown focus direction '{direction}'"

    # Window move
    if lower.startswith("move window "):
        direction = cmd.split(None, 2)[2].lower()
        key_map = {"left": "Left", "right": "Right", "up": "Up", "down": "Down"}
        if direction in key_map:
            return _run(["wtype", "-M", "logo", "-M", "shift", "-k", key_map[direction], "-m", "shift", "-m", "logo"], env)
        return f"Error: unknown move direction '{direction}'"

    # Fullscreen / Float / Close
    if lower == "fullscreen":
        return _run(["wtype", "-M", "logo", "-k", "F11", "-m", "logo"], env)
    if lower == "float":
        return _run(["wtype", "-M", "logo", "-k", "g", "-m", "logo"], env)
    if lower == "close":
        return _run(["wtype", "-M", "logo", "-k", "q", "-m", "logo"], env)

    # Volume / Brightness via CosmicSettingsDaemon (Real DBus)
    if lower == "volume up":
        return _cosmic_settings_daemon("VolumeUp", "", env)
    if lower == "volume down":
        return _cosmic_settings_daemon("VolumeDown", "", env)
    if lower == "brightness up":
        return _cosmic_settings_daemon("IncreaseDisplayBrightness", "", env)
    if lower == "brightness down":
        return _cosmic_settings_daemon("DecreaseDisplayBrightness", "", env)

    # List windows / workspaces — try wlrctl if available
    if lower in ("list windows", "clients", "list workspaces", "workspaces"):
        if shutil.which("wlrctl"):
            return _run(["wlrctl", "toplevel" if "window" in lower else "workspace", "list"], env)
        return "Error: wlrctl not installed. Install it for listing on Cosmic."

    # Fallback: try as raw busctl call if it looks like one
    if "." in cmd:
        return _cosmic_dbus(cmd, "", env)

    return f"Error: unknown Cosmic command '{cmd}'"


def _cosmic_dbus(method: str, args: str, env: dict) -> str:
    """Call a method on com.system76.CosmicComp via busctl."""
    # Note: com.system76.CosmicComp might be missing on some versions
    cmd_parts = [
        "busctl", "--user", "call",
        "com.system76.CosmicComp",
        "/com/system76/CosmicComp",
        "com.system76.CosmicComp",
        method,
    ]
    if args:
        cmd_parts.extend(args.split())

    return _run(cmd_parts, env)


def _cosmic_settings_daemon(method: str, args: str, env: dict) -> str:
    """Call a method on com.system76.CosmicSettingsDaemon via busctl."""
    cmd_parts = [
        "busctl", "--user", "call",
        "com.system76.CosmicSettingsDaemon",
        "/com/system76/CosmicSettingsDaemon",
        "com.system76.CosmicSettingsDaemon",
        method,
    ]
    if args:
        cmd_parts.extend(args.split())

    return _run(cmd_parts, env)


# -----------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------

def run(cmd: str) -> str:
    """Execute a desktop command on the detected DE."""
    de = _detect_de()
    env = _wayland_env()

    if de == "hyprland":
        return _hyprland(cmd, env)
    elif de == "cosmic":
        return _cosmic(cmd, env)
    else:
        return f"Error: unsupported desktop environment (detected: {de}). Supported: hyprland, cosmic."
