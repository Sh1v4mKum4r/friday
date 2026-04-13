"""Shell command execution tool."""

import subprocess

name = "run_shell"
description = "Run a bash shell command and return its stdout output."


def run(command: str) -> str:
    """Execute *command* in bash with a 30-second timeout.

    Returns stdout on success, or an error message with the exit code on failure.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        return (
            f"Error (exit code {result.returncode}):\n"
            f"{result.stderr or result.stdout}"
        )
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds."
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"
