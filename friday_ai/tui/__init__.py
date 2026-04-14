"""Friday TUI — keyboard-driven terminal interface."""

import sys


def _api(host: str, port: int):
    """Create an httpx client for the Friday API."""
    import httpx
    return httpx.Client(base_url=f"http://{host}:{port}", timeout=120.0)


def _connect_or_die(host: str, port: int):
    """Return an API client or exit with an error."""
    client = _api(host, port)
    try:
        r = client.get("/health")
        r.raise_for_status()
    except Exception:
        print(f"Error: Cannot connect to Friday at {host}:{port}")
        print("Start the backend first: start.sh")
        sys.exit(1)
    return client


def _cmd_chat(args) -> None:
    """Send a message and print the response."""
    client = _connect_or_die(args.host, args.port)
    message = " ".join(args.message)
    r = client.post("/chat", json={"message": message})
    data = r.json()
    print(data.get("response", "No response"))


def _cmd_tools(args) -> None:
    """List, enable, or disable tools."""
    client = _connect_or_die(args.host, args.port)

    if args.tools_action == "list" or args.tools_action is None:
        r = client.post("/reload")
        data = r.json()
        tools = data.get("tools", [])
        if not tools:
            print("No tools found.")
            return
        print(f"{'TOOL':<24} {'STATUS':<10}")
        print("-" * 34)
        for t in tools:
            name = t["name"] if isinstance(t, dict) else str(t)
            enabled = t.get("enabled", True) if isinstance(t, dict) else True
            status = "\033[32menabled\033[0m" if enabled else "\033[31mdisabled\033[0m"
            print(f"  {name:<22} {status}")
        print(f"\n{len(tools)} tools total")

    elif args.tools_action == "enable":
        if not args.tool_name:
            print("Usage: friday tools enable <name>")
            sys.exit(1)
        r = client.post("/tools/toggle", params={"name": args.tool_name, "enabled": True})
        data = r.json()
        if data.get("ok"):
            print(f"Enabled: {args.tool_name}")
        else:
            print(f"Tool not found: {args.tool_name}")

    elif args.tools_action == "disable":
        if not args.tool_name:
            print("Usage: friday tools disable <name>")
            sys.exit(1)
        r = client.post("/tools/toggle", params={"name": args.tool_name, "enabled": False})
        data = r.json()
        if data.get("ok"):
            print(f"Disabled: {args.tool_name}")
        else:
            print(f"Tool not found: {args.tool_name}")


def _cmd_mcp(args) -> None:
    """Show MCP status or reconnect."""
    client = _connect_or_die(args.host, args.port)

    if args.mcp_action == "reconnect":
        r = client.post("/mcp/reconnect")
        data = r.json()
        connected = data.get("connected", [])
        print(f"Reconnected: {', '.join(connected) if connected else 'none'}")
    else:
        r = client.get("/mcp/status")
        data = r.json()
        servers = data.get("servers", [])
        tools = data.get("tools", [])
        print(f"{'SERVER':<20} {'TOOLS':<8}")
        print("-" * 28)
        for s in servers:
            count = len([t for t in tools if isinstance(t, dict) and t.get("server") == s])
            print(f"  \033[32m{s:<18}\033[0m {count}")
        print(f"\n{len(servers)} servers, {len(tools)} tools total")


def _cmd_reload(args) -> None:
    """Hot-reload tools."""
    client = _connect_or_die(args.host, args.port)
    r = client.post("/reload")
    data = r.json()
    count = data.get("reloaded", 0)
    print(f"Reloaded {count} tools")


def _cmd_health(args) -> None:
    """Show backend health."""
    client = _connect_or_die(args.host, args.port)
    r = client.get("/health")
    data = r.json()
    status = data.get("status", "unknown")
    providers = data.get("providers", [])
    print(f"Status: \033[32m{status}\033[0m")
    print(f"Providers: {', '.join(providers)}")


def _cmd_memory(args) -> None:
    """List or manage memory."""
    client = _connect_or_die(args.host, args.port)

    if args.memory_action == "clear":
        r = client.post("/memory/clear")
        print("Memory cleared.")
    elif args.memory_action == "forget":
        if not args.keyword:
            print("Usage: friday memory forget <keyword>")
            sys.exit(1)
        r = client.post("/memory/forget", params={"keyword": args.keyword})
        print(f"Forgot entries matching: {args.keyword}")
    else:
        r = client.post("/memory/list")
        data = r.json()
        entries = data.get("entries", [])
        if not entries:
            print("No memory entries.")
            return
        for e in entries:
            print(f"  - {e}")
        print(f"\n{len(entries)} entries")


def _cmd_tui(args) -> None:
    """Launch the TUI."""
    from friday_ai.tui.app import FridayApp

    app = FridayApp(
        host=args.host,
        port=args.port,
        theme=args.theme,
        no_connect=args.no_connect,
        session=args.session,
    )
    app.run()


def main() -> None:
    """Entry point for friday command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Friday AI — personal assistant",
        usage="friday [command] [args...]",
    )
    parser.add_argument("--port", type=int, default=65535, help="API port (default: 65535)")
    parser.add_argument("--host", default="127.0.0.1", help="API host (default: 127.0.0.1)")

    sub = parser.add_subparsers(dest="command")

    # friday (no subcommand) → TUI or quick chat
    # We handle this after parsing

    # friday tools [list|enable|disable]
    p_tools = sub.add_parser("tools", help="List, enable, or disable tools")
    p_tools.add_argument("tools_action", nargs="?", choices=["list", "enable", "disable"], default="list")
    p_tools.add_argument("tool_name", nargs="?", help="Tool name (for enable/disable)")

    # friday mcp [status|reconnect]
    p_mcp = sub.add_parser("mcp", help="MCP server status and management")
    p_mcp.add_argument("mcp_action", nargs="?", choices=["status", "reconnect"], default="status")

    # friday reload
    sub.add_parser("reload", help="Hot-reload all tools")

    # friday health
    sub.add_parser("health", help="Check backend status")

    # friday memory [list|forget|clear]
    p_mem = sub.add_parser("memory", help="View and manage memory")
    p_mem.add_argument("memory_action", nargs="?", choices=["list", "forget", "clear"], default="list")
    p_mem.add_argument("keyword", nargs="?", help="Keyword (for forget)")

    # friday tui [--theme ...] — explicit TUI launch
    p_tui = sub.add_parser("tui", help="Launch the terminal UI")
    p_tui.add_argument("--theme", choices=["obsidian", "neural", "prism", "techno"], help="Theme")
    p_tui.add_argument("--no-connect", action="store_true", help="Launch without backend")
    p_tui.add_argument("--session", help="Load session file")

    SUBCOMMANDS = {"tools", "mcp", "reload", "health", "memory", "tui", "-h", "--help"}

    # Check if the first non-flag arg is a known subcommand
    raw_args = sys.argv[1:]
    first_word = next((a for a in raw_args if not a.startswith("-")), None)

    if first_word and first_word not in SUBCOMMANDS:
        # Bare words → quick chat (skip argparse subcommand parsing)
        # Extract --host and --port if present
        host = "127.0.0.1"
        port = 65535
        message_parts = []
        i = 0
        while i < len(raw_args):
            if raw_args[i] == "--host" and i + 1 < len(raw_args):
                host = raw_args[i + 1]
                i += 2
            elif raw_args[i] == "--port" and i + 1 < len(raw_args):
                port = int(raw_args[i + 1])
                i += 2
            elif not raw_args[i].startswith("--"):
                message_parts.append(raw_args[i])
                i += 1
            else:
                i += 1

        class ChatArgs:
            pass
        args = ChatArgs()
        args.host = host
        args.port = port
        args.message = message_parts
        _cmd_chat(args)
        return

    args = parser.parse_args()

    dispatch = {
        "tools": _cmd_tools,
        "mcp": _cmd_mcp,
        "reload": _cmd_reload,
        "health": _cmd_health,
        "memory": _cmd_memory,
        "tui": _cmd_tui,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        # No command → launch TUI
        args.theme = None
        args.no_connect = False
        args.session = None
        _cmd_tui(args)
