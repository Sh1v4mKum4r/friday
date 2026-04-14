"""Friday TUI — keyboard-driven terminal interface."""

import argparse


def main() -> None:
    """Entry point for friday-tui command."""
    parser = argparse.ArgumentParser(description="Friday AI Terminal Interface")
    parser.add_argument("--theme", choices=["obsidian", "neural", "prism", "techno"], help="Override startup theme")
    parser.add_argument("--port", type=int, default=65535, help="API port (default: 65535)")
    parser.add_argument("--host", default="127.0.0.1", help="API host (default: 127.0.0.1)")
    parser.add_argument("--no-connect", action="store_true", help="Launch without connecting to backend")
    parser.add_argument("--session", help="Load a specific session file on start")
    args = parser.parse_args()

    from friday_ai.tui.app import FridayApp

    app = FridayApp(
        host=args.host,
        port=args.port,
        theme=args.theme,
        no_connect=args.no_connect,
        session=args.session,
    )
    app.run()
