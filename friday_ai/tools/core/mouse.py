"""Mouse control tool using ydotool (works on any Wayland compositor).

Requires: ydotool + ydotoold daemon running
Install: sudo pacman -S ydotool && sudo systemctl enable --now ydotool
"""

import subprocess

name = "mouse"
description = (
    "Control the mouse cursor. Actions: "
    "'move <x> <y>' to move to coordinates, "
    "'click' or 'click right' or 'click middle', "
    "'doubleclick', "
    "'drag <x1> <y1> <x2> <y2>' to drag from one point to another, "
    "'scroll up/down <amount>', "
    "'position' to get current cursor position."
)


def _ydotool(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["ydotool"] + args, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "Done."
        return f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: ydotool not found. Install: sudo pacman -S ydotool && sudo systemctl enable --now ydotool"


def run(action: str) -> str:
    """Control the mouse.

    Parameters
    ----------
    action:
        'move <x> <y>' — move cursor to absolute position
        'click' — left click at current position
        'click right' — right click
        'click middle' — middle click
        'doubleclick' — double left click
        'drag <x1> <y1> <x2> <y2>' — click-drag from (x1,y1) to (x2,y2)
        'scroll up [amount]' — scroll up (default 3)
        'scroll down [amount]' — scroll down (default 3)
        'position' — print current cursor position
    """
    parts = action.strip().lower().split()
    cmd = parts[0] if parts else ""

    if cmd == "move" and len(parts) >= 3:
        x, y = parts[1], parts[2]
        # ydotool mousemove uses absolute positioning with --absolute
        return _ydotool(["mousemove", "--absolute", "-x", x, "-y", y])

    elif cmd == "click":
        if len(parts) >= 2 and parts[1] == "right":
            return _ydotool(["click", "0xC0", "0x01"])  # right button
        elif len(parts) >= 2 and parts[1] == "middle":
            return _ydotool(["click", "0xC0", "0x04"])  # middle button
        else:
            return _ydotool(["click", "0xC0"])  # left button

    elif cmd == "doubleclick":
        _ydotool(["click", "0xC0"])
        return _ydotool(["click", "0xC0"])

    elif cmd == "drag" and len(parts) >= 5:
        x1, y1, x2, y2 = parts[1], parts[2], parts[3], parts[4]
        # Move to start, press, move to end, release
        _ydotool(["mousemove", "--absolute", "-x", x1, "-y", y1])
        _ydotool(["mousedown", "0x00"])  # press left
        _ydotool(["mousemove", "--absolute", "-x", x2, "-y", y2])
        return _ydotool(["mouseup", "0x00"])  # release left

    elif cmd == "scroll":
        direction = parts[1] if len(parts) > 1 else "down"
        amount = parts[2] if len(parts) > 2 else "3"
        try:
            amt = int(amount)
        except ValueError:
            amt = 3
        if direction == "up":
            return _ydotool(["mousemove", "--wheel", "-y", str(amt)])
        else:
            return _ydotool(["mousemove", "--wheel", "-y", str(-amt)])

    elif cmd == "position":
        # ydotool doesn't have a "get position" command
        # Use slurp as a workaround — or read from /dev/input
        try:
            result = subprocess.run(
                ["slurp", "-p", "-f", "%x %y"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return f"Cursor position: {result.stdout.strip()}"
            return "Could not get cursor position. Click somewhere with slurp to read position."
        except FileNotFoundError:
            return "Error: slurp not found (needed for position reading)"

    else:
        return (
            "Usage: move <x> <y>, click [right|middle], doubleclick, "
            "drag <x1> <y1> <x2> <y2>, scroll up/down [amount], position"
        )
