"""Keyboard control tool using wtype + ydotool (works on any Wayland compositor).

Requires: wtype (for typing text), ydotool (for key combos)
Install: sudo pacman -S wtype ydotool
"""

import subprocess
import time

name = "keyboard"
description = (
    "Control the keyboard. Actions: "
    "'type <text>' to type text, "
    "'press <key>' to press a single key (enter, tab, escape, etc.), "
    "'combo <keys>' for key combinations (ctrl+c, alt+tab, super+f, ctrl+shift+t), "
    "'hold <key> <duration>' to hold a key."
)

# Map human-readable key names to wtype/ydotool key names
_WTYPE_KEYS = {
    "enter": "Return", "return": "Return",
    "tab": "Tab",
    "escape": "Escape", "esc": "Escape",
    "backspace": "BackSpace",
    "delete": "Delete", "del": "Delete",
    "space": "space",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "home": "Home", "end": "End",
    "pageup": "Prior", "pagedown": "Next",
    "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4",
    "f5": "F5", "f6": "F6", "f7": "F7", "f8": "F8",
    "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
}

_MODIFIER_MAP = {
    "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "super": "logo", "win": "logo", "meta": "logo",
}


def run(action: str) -> str:
    """Control the keyboard.

    Parameters
    ----------
    action:
        'type <text>' — type text as if from keyboard
        'press <key>' — press and release a key (enter, tab, escape, f1-f12, etc.)
        'combo <keys>' — press key combination (ctrl+c, alt+tab, ctrl+shift+t)
        'hold <key> <seconds>' — hold a key for N seconds
    """
    parts = action.strip().split(None, 1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "type":
        if not arg:
            return "Usage: type <text>"
        return _type_text(arg)

    elif cmd == "press":
        if not arg:
            return "Usage: press <key> (e.g. enter, tab, escape, f1)"
        return _press_key(arg.strip().lower())

    elif cmd == "combo":
        if not arg:
            return "Usage: combo <keys> (e.g. ctrl+c, alt+tab, ctrl+shift+t)"
        return _key_combo(arg.strip().lower())

    elif cmd == "hold":
        hold_parts = arg.strip().split()
        key = hold_parts[0] if hold_parts else ""
        duration = float(hold_parts[1]) if len(hold_parts) > 1 else 1.0
        if not key:
            return "Usage: hold <key> <seconds>"
        return _hold_key(key.lower(), duration)

    else:
        return (
            "Usage: type <text>, press <key>, combo <keys>, hold <key> <seconds>\n"
            "Keys: enter, tab, escape, backspace, delete, space, up/down/left/right, f1-f12\n"
            "Combos: ctrl+c, alt+tab, super+f, ctrl+shift+t"
        )


def _type_text(text: str) -> str:
    """Type text using wtype."""
    try:
        result = subprocess.run(
            ["wtype", "--", text],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return f"Typed {len(text)} characters."
        return f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: wtype not found. Install: sudo pacman -S wtype"


def _press_key(key: str) -> str:
    """Press a single key using wtype."""
    wtype_key = _WTYPE_KEYS.get(key, key)
    try:
        result = subprocess.run(
            ["wtype", "-k", wtype_key],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return f"Pressed {key}."
        return f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: wtype not found. Install: sudo pacman -S wtype"


def _key_combo(combo: str) -> str:
    """Press a key combination using wtype modifiers."""
    keys = [k.strip() for k in combo.split("+")]
    if len(keys) < 2:
        return f"Error: combo needs at least 2 keys (got: {combo})"

    modifiers = []
    final_key = None

    for key in keys:
        if key in _MODIFIER_MAP:
            modifiers.append(_MODIFIER_MAP[key])
        else:
            final_key = _WTYPE_KEYS.get(key, key)

    if final_key is None:
        return f"Error: no non-modifier key in combo: {combo}"

    # Build wtype command with -M (modifier down) and -m (modifier up)
    cmd = ["wtype"]
    for mod in modifiers:
        cmd.extend(["-M", mod])
    cmd.extend(["-k", final_key])
    for mod in reversed(modifiers):
        cmd.extend(["-m", mod])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f"Pressed {combo}."
        return f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: wtype not found. Install: sudo pacman -S wtype"


def _hold_key(key: str, duration: float) -> str:
    """Hold a key for a duration using ydotool."""
    # wtype doesn't support hold, use ydotool for this
    wtype_key = _WTYPE_KEYS.get(key, key)
    try:
        # ydotool key --down
        subprocess.run(
            ["ydotool", "key", "--down", wtype_key],
            capture_output=True, timeout=5,
        )
        time.sleep(min(duration, 10))  # cap at 10 seconds
        subprocess.run(
            ["ydotool", "key", "--up", wtype_key],
            capture_output=True, timeout=5,
        )
        return f"Held {key} for {duration}s."
    except FileNotFoundError:
        return "Error: ydotool not found. Install: sudo pacman -S ydotool"
