"""Friday TUI — keyboard-driven terminal interface."""


def main() -> None:
    """Entry point for friday-tui command."""
    from friday_ai.tui.app import FridayApp
    app = FridayApp()
    app.run()
