"""Web search tool via googler CLI."""

import subprocess

name = "web_search"
description = "Search the web using the googler CLI and return the top 5 results."


def run(query: str) -> str:
    """Run a web search for *query* using googler (5 results, no interactive prompt).

    Returns formatted search results or an error if googler is not installed.
    """
    try:
        result = subprocess.run(
            ["googler", "--count", "5", "--noprompt", "--json", query],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        return (
            f"Error running web search (exit code {result.returncode}): "
            f"{result.stderr or result.stdout}"
        )
    except FileNotFoundError:
        return (
            "Error: googler is not installed. "
            "Install it with: pip install googler  or  sudo pacman -S googler"
        )
    except subprocess.TimeoutExpired:
        return "Error: web search timed out after 30 seconds."
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"
