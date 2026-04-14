"""Friday TUI — keyboard-driven terminal interface."""

import argparse
import sys


def _quick_chat(message: str, host: str, port: int) -> None:
    """Send a single message to Friday and print the response."""
    import httpx

    try:
        r = httpx.post(
            f"http://{host}:{port}/chat",
            json={"message": message},
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
        print(data.get("response", "No response"))
    except httpx.ConnectError:
        print(f"Error: Cannot connect to Friday at {host}:{port}")
        print("Start the backend first: start.sh")
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"Error: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point for friday command.

    Usage:
        friday                          # launch TUI
        friday decrease brightness      # quick chat (send message, print response)
        friday --theme neural           # launch TUI with theme
        friday "what time is it"        # quick chat with quoted message
    """
    parser = argparse.ArgumentParser(
        description="Friday AI — personal assistant",
        usage="friday [message...] [--theme THEME] [--port PORT] [--host HOST] [--no-connect] [--session FILE]",
    )
    parser.add_argument("message", nargs="*", help="Message to send (skips TUI, prints response)")
    parser.add_argument("--theme", choices=["obsidian", "neural", "prism", "techno"], help="Override startup theme")
    parser.add_argument("--port", type=int, default=65535, help="API port (default: 65535)")
    parser.add_argument("--host", default="127.0.0.1", help="API host (default: 127.0.0.1)")
    parser.add_argument("--no-connect", action="store_true", help="Launch without connecting to backend")
    parser.add_argument("--session", help="Load a specific session file on start")
    args = parser.parse_args()

    # If positional message given, do quick chat (no TUI)
    if args.message:
        _quick_chat(" ".join(args.message), args.host, args.port)
        return

    # Otherwise launch the TUI
    from friday_ai.tui.app import FridayApp

    app = FridayApp(
        host=args.host,
        port=args.port,
        theme=args.theme,
        no_connect=args.no_connect,
        session=args.session,
    )
    app.run()
