#!/usr/bin/env python3
"""Friday floating chat window using pywebview.

Opens a native, frameless, always-on-top window with the Friday chat UI.
"""

import subprocess
import sys
import os
import signal

PORT = 65535
URL = f"http://127.0.0.1:{PORT}"


def check_backend():
    """Return True if the Friday backend is reachable."""
    try:
        import urllib.request
        urllib.request.urlopen(f"{URL}/health", timeout=3)
        return True
    except Exception:
        return False


def start_backend():
    """Start the Friday daemon in the background."""
    subprocess.Popen(
        ["/home/sh4d0w/Projects/friday/start.sh", "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    import time
    for _ in range(10):
        time.sleep(1)
        if check_backend():
            return True
    return False


def main():
    import webview

    # Ensure backend is running
    if not check_backend():
        if not start_backend():
            subprocess.run(["notify-send", "Friday", "Failed to start backend."])
            sys.exit(1)

    # Create the floating window
    window = webview.create_window(
        title="Friday",
        url=URL,
        width=480,
        height=650,
        resizable=True,
        on_top=True,
        frameless=False,
        easy_drag=True,
        background_color="#0f0f14",
    )

    # Start the webview (blocks until window is closed)
    webview.start(gui="gtk", debug=False)


if __name__ == "__main__":
    main()
