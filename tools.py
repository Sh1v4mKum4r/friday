import subprocess

def run_shell(command: str) -> str:
    """Executes a bash shell command and returns the output."""
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error ({e.returncode}): {e.stderr.strip()}"

def notify(message: str, title: str = "Friday"):
    """Sends a desktop notification using notify-send."""
    run_shell(f"notify-send '{title}' '{message}'")
    return "Notification sent."

def get_clipboard() -> str:
    """Gets the current text content of the clipboard using wl-paste."""
    return run_shell("wl-paste")

def set_clipboard(text: str) -> str:
    """Sets the text content of the clipboard using wl-copy."""
    process = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
    process.communicate(input=text)
    return "Clipboard updated."

def hyprctl_command(cmd: str) -> str:
    """Executes a hyprctl command to manage windows or workspaces.
    For example: 'dispatch workspace 1' or 'clients'
    """
    return run_shell(f"hyprctl {cmd}")
