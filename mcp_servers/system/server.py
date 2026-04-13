"""friday-system MCP server.

Tools for system maintenance, monitoring, snapshots, and dotfile management.

Usage: python server.py (runs as MCP stdio server)
"""

import subprocess
import os
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("friday-system")


def _run(cmd: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip() or result.stderr.strip() or "Done."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="system_cleanup",
            description="Run system cleanup: clear package cache, remove orphans, clean user caches, trim journal. Shows space reclaimed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "default": False, "description": "If true, show what would be cleaned without doing it"},
                },
            },
        ),
        Tool(
            name="disk_usage",
            description="Show disk usage analysis. Modes: 'overview' for filesystem summary, 'heavy' to find largest files/dirs, 'home' for home directory breakdown.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["overview", "heavy", "home"], "default": "overview"},
                },
            },
        ),
        Tool(
            name="process_monitor",
            description="Show top processes by CPU or memory usage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sort_by": {"type": "string", "enum": ["cpu", "memory"], "default": "cpu"},
                    "count": {"type": "integer", "default": 10},
                },
            },
        ),
        Tool(
            name="service_manager",
            description="Manage systemd services. Actions: 'list' running services, 'status <name>', 'start <name>', 'stop <name>', 'restart <name>', 'enable <name>', 'disable <name>'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "status", "start", "stop", "restart", "enable", "disable"]},
                    "service": {"type": "string", "description": "Service name (required for all except 'list')"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="package_manager",
            description="Manage Arch Linux packages. Actions: 'search <query>', 'info <package>', 'list_installed', 'recently_installed', 'orphans', 'update_check'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["search", "info", "list_installed", "recently_installed", "orphans", "update_check"]},
                    "query": {"type": "string"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="dotfile_manager",
            description="Manage dotfiles. Actions: 'list' tracked configs, 'diff' to show uncommitted changes, 'backup' to create a tarball.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "diff", "backup"]},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="boot_analysis",
            description="Analyze system boot performance using systemd-analyze.",
            inputSchema={
                "type": "object",
                "properties": {
                    "detail": {"type": "string", "enum": ["summary", "blame", "critical"], "default": "summary"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "system_cleanup": _system_cleanup,
        "disk_usage": _disk_usage,
        "process_monitor": _process_monitor,
        "service_manager": _service_manager,
        "package_manager": _package_manager,
        "dotfile_manager": _dotfile_manager,
        "boot_analysis": _boot_analysis,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _system_cleanup(args: dict) -> str:
    dry = args.get("dry_run", False)
    parts = []

    if dry:
        # Show what would be cleaned
        cache_size = _run("du -sh ~/.cache 2>/dev/null | cut -f1")
        orphans = _run("pacman -Qdtq 2>/dev/null | wc -l")
        journal = _run("journalctl --disk-usage 2>/dev/null")
        trash_size = _run("du -sh ~/.local/share/Trash 2>/dev/null | cut -f1")
        parts.append(f"User cache: {cache_size}")
        parts.append(f"Orphan packages: {orphans}")
        parts.append(f"Journal: {journal}")
        parts.append(f"Trash: {trash_size}")
        parts.append("\nRun without dry_run to clean.")
    else:
        # Actually clean
        parts.append("Cleaning package cache...")
        parts.append(_run("paccache -rk2 2>/dev/null"))

        orphans = _run("pacman -Qdtq 2>/dev/null")
        if orphans and orphans != "Done.":
            parts.append(f"Removing orphans: {orphans}")

        # Clean safe user caches
        cache_dirs = [
            "~/.cache/yay", "~/.cache/pip", "~/.cache/electron",
            "~/.cache/node-gyp", "~/.cache/go-build", "~/.cache/thumbnails",
            "~/.cache/mesa_shader_cache",
        ]
        for d in cache_dirs:
            expanded = os.path.expanduser(d)
            if os.path.isdir(expanded):
                _run(f"rm -rf {expanded}/*")

        parts.append("User caches cleared.")
        parts.append(_run("journalctl --vacuum-size=50M 2>/dev/null"))
        parts.append(f"\nDisk free: {_run('df -h / /home | tail -2')}")

    return "\n".join(parts)


def _disk_usage(args: dict) -> str:
    mode = args.get("mode", "overview")
    if mode == "overview":
        return _run("df -h / /home /boot/efi 2>/dev/null")
    elif mode == "heavy":
        return _run("du -sh ~/*/ ~/.local/ ~/.cache/ ~/.config/ 2>/dev/null | sort -rh | head -15")
    elif mode == "home":
        return _run("du -sh ~/*/  2>/dev/null | sort -rh | head -20")
    return "Unknown mode."


def _process_monitor(args: dict) -> str:
    sort_by = args.get("sort_by", "cpu")
    count = args.get("count", 10)
    if sort_by == "cpu":
        return _run(f"ps aux --sort=-%cpu | head -{count + 1}")
    else:
        return _run(f"ps aux --sort=-%mem | head -{count + 1}")


def _service_manager(args: dict) -> str:
    action = args["action"]
    service = args.get("service", "")

    if action == "list":
        return _run("systemctl list-units --type=service --state=running --no-pager | head -30")
    elif action == "status" and service:
        return _run(f"systemctl status {service} --no-pager | head -20")
    elif action in ("start", "stop", "restart", "enable", "disable") and service:
        return _run(f"systemctl {action} {service} 2>&1")
    return f"Usage: {action} requires a service name."


def _package_manager(args: dict) -> str:
    action = args["action"]
    query = args.get("query", "")

    if action == "search" and query:
        return _run(f"pacman -Ss {query} 2>/dev/null | head -30")
    elif action == "info" and query:
        return _run(f"pacman -Qi {query} 2>/dev/null || pacman -Si {query} 2>/dev/null")
    elif action == "list_installed":
        count = _run("pacman -Qeq 2>/dev/null | wc -l")
        return f"Explicitly installed: {count} packages\n\n{_run('pacman -Qeq 2>/dev/null | tail -20')}\n..."
    elif action == "recently_installed":
        return _run("expac --timefmt='%Y-%m-%d' '%l\t%n' | sort -r | head -15")
    elif action == "orphans":
        return _run("pacman -Qdtq 2>/dev/null") or "No orphan packages."
    elif action == "update_check":
        return _run("checkupdates 2>/dev/null | head -20") or "System is up to date."
    return f"Unknown action: {action}"


def _dotfile_manager(args: dict) -> str:
    action = args["action"]
    config_dir = Path.home() / ".config"

    if action == "list":
        important = ["hypr", "cosmic", "waybar", "rofi", "wofi", "kitty", "alacritty",
                      "nvim", "zshrc", "ml4w", "friday"]
        found = []
        for name in important:
            path = config_dir / name
            if path.exists():
                size = _run(f"du -sh {path} 2>/dev/null | cut -f1")
                found.append(f"  {name}: {size}")
        return "Tracked configs:\n" + "\n".join(found) if found else "No tracked configs found."

    elif action == "diff":
        # Check if dotfiles repo exists
        dotfiles_dir = Path.home() / "dotfiles"
        if dotfiles_dir.exists() and (dotfiles_dir / ".git").exists():
            return _run(f"cd {dotfiles_dir} && git diff --stat")
        return "No dotfiles git repo found at ~/dotfiles. Create one to track changes."

    elif action == "backup":
        backup_path = Path.home() / f"dotfiles-backup-{_run('date +%Y%m%d')}.tar.gz"
        configs = "hypr cosmic waybar rofi kitty nvim zshrc ml4w friday"
        cmd = f"tar czf {backup_path} " + " ".join(
            f"-C ~/.config {c}" for c in configs.split() if (config_dir / c).exists()
        )
        _run(cmd)
        return f"Backup saved to {backup_path}"

    return f"Unknown action: {action}"


def _boot_analysis(args: dict) -> str:
    detail = args.get("detail", "summary")
    if detail == "summary":
        return _run("systemd-analyze")
    elif detail == "blame":
        return _run("systemd-analyze blame | head -15")
    elif detail == "critical":
        return _run("systemd-analyze critical-chain | head -20")
    return "Unknown detail level."


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
