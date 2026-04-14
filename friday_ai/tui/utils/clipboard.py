"""Clipboard abstraction for Wayland (wl-copy) and X11 (xclip/xsel)."""

from __future__ import annotations

import asyncio
import os
import shutil


def detect_clipboard_cmd() -> list[str] | None:
    """Detect the available clipboard command."""
    if os.environ.get("WAYLAND_DISPLAY"):
        if shutil.which("wl-copy"):
            return ["wl-copy"]

    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard"]
        if shutil.which("xsel"):
            return ["xsel", "--clipboard", "--input"]

    return None


async def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    cmd = detect_clipboard_cmd()
    if cmd is None:
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=text.encode())
        return proc.returncode == 0
    except OSError:
        return False
