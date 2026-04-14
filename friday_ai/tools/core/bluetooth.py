"""Bluetooth control tool using rfkill."""

import subprocess

name = "bluetooth"
description = (
    "Control Bluetooth. Actions: 'on' to enable, 'off' to disable, 'status' to check."
)


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip() or "Done."
        return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Error: {str(e)}"


def run(action: str = "status") -> str:
    """Control Bluetooth.

    Parameters
    ----------
    action:
        'on' — enable Bluetooth
        'off' — disable Bluetooth
        'status' — check Bluetooth status
    """
    action = action.strip().lower()

    if action == "on":
        return _run(["rfkill", "unblock", "bluetooth"])
    elif action == "off":
        return _run(["rfkill", "block", "bluetooth"])
    elif action == "status":
        output = _run(["rfkill", "list", "bluetooth"])
        if "Soft blocked: yes" in output:
            return "Bluetooth is currently OFF (blocked)."
        elif "Soft blocked: no" in output:
            return "Bluetooth is currently ON (unblocked)."
        else:
            return f"Bluetooth status unknown. Output:\n{output}"
    else:
        return "Usage: bluetooth on | off | status"
