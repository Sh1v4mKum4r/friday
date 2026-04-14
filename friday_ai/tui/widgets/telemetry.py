"""Telemetry panel showing provider health, MCP status, and session info."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class TelemetryPanel(Widget):
    """Right-side toggleable panel with live system stats."""

    providers: reactive[list[str]] = reactive(list)
    mcp_servers: reactive[list[str]] = reactive(list)
    active_provider: reactive[str] = reactive("")
    active_model: reactive[str] = reactive("")
    last_latency: reactive[float] = reactive(0.0)
    memory_count: reactive[int] = reactive(0)
    session_saved: reactive[bool] = reactive(False)

    class RefreshRequested(Message):
        """Emitted when telemetry wants fresh data from the API."""

    def compose(self) -> ComposeResult:
        with Vertical(id="telemetry"):
            yield Label("SYSTEM", id="telemetry-title")
            yield VerticalScroll(id="telemetry-content")

    def on_mount(self) -> None:
        """Start auto-refresh timer (30s)."""
        self.set_interval(30, self._request_refresh)

    def _request_refresh(self) -> None:
        self.post_message(self.RefreshRequested())

    def _rebuild(self) -> None:
        try:
            container = self.query_one("#telemetry-content", VerticalScroll)
            container.remove_children()

            # Providers
            container.mount(Label("PROVIDERS", classes="telemetry-label"))
            for p in self.providers:
                container.mount(Label(f"  > {p}", classes="telemetry-value status-online"))
            container.mount(Label(""))

            # Active session
            container.mount(Label("ACTIVE", classes="telemetry-label"))
            container.mount(Label(f"  Provider  {self.active_provider or '-'}", classes="telemetry-value"))
            container.mount(Label(f"  Model     {self.active_model or '-'}", classes="telemetry-value"))
            latency_str = f"{self.last_latency:.2f}s" if self.last_latency else "-"
            container.mount(Label(f"  Latency   {latency_str}", classes="telemetry-value"))
            container.mount(Label(""))

            # MCP
            container.mount(Label(f"MCP SERVERS  {len(self.mcp_servers)}", classes="telemetry-label"))
            for server in self.mcp_servers:
                container.mount(Label(f"  > {server}", classes="telemetry-value status-online"))
            container.mount(Label(""))

            # Memory/Session
            container.mount(Label(f"MEMORY  {self.memory_count} facts", classes="telemetry-label"))
            save_status = "saved" if self.session_saved else "unsaved"
            container.mount(Label(f"SESSION  {save_status}", classes="telemetry-label"))
        except Exception:
            pass

    def update_health(self, data: dict) -> None:
        self.providers = data.get("providers", [])
        self._rebuild()

    def update_mcp(self, data: dict) -> None:
        self.mcp_servers = data.get("servers", [])
        self._rebuild()

    def update_last_response(self, provider: str, model: str, latency: float) -> None:
        self.active_provider = provider
        self.active_model = model
        self.last_latency = latency
        self._rebuild()

    def update_memory(self, count: int) -> None:
        self.memory_count = count
        self._rebuild()

    def update_session_status(self, saved: bool) -> None:
        self.session_saved = saved
        self._rebuild()
