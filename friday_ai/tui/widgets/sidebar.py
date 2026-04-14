"""Conversation history sidebar overlay."""

from __future__ import annotations

from datetime import datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class Sidebar(Widget):
    """Toggle-able conversation history panel."""

    sessions: reactive[list[dict]] = reactive(list, layout=True)

    class SessionSelected(Message):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    class NewSessionRequested(Message):
        pass

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar"):
            yield Label("CONVERSATIONS", id="sidebar-title")
            yield Label("+ New Session", id="new-session-btn", classes="session-item")
            yield VerticalScroll(id="session-list")

    def load_sessions(self, sessions: list[dict]) -> None:
        self.sessions = sessions
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        try:
            container = self.query_one("#session-list", VerticalScroll)
            container.remove_children()

            grouped = self._group_by_date(self.sessions)
            for group_label, items in grouped.items():
                container.mount(Label(group_label, classes="session-group-label"))
                for session in items:
                    item = Label(
                        f"  > {session['name'][:22]}",
                        classes="session-item",
                        id=f"session-{session['id']}",
                    )
                    item.session_id = session["id"]
                    container.mount(item)
        except Exception:
            pass

    def _group_by_date(self, sessions: list[dict]) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        for s in sessions:
            try:
                date = datetime.strptime(s["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                date = today

            if date == today:
                label = "TODAY"
            elif date == yesterday:
                label = "YESTERDAY"
            elif date >= week_ago:
                label = "THIS WEEK"
            else:
                label = "OLDER"

            groups.setdefault(label, []).append(s)

        return groups
