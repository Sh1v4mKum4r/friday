"""friday-rice MCP server.

Desktop customization: wallpaper, themes, colorscheme, fonts, Hyprland config.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("friday-rice")

WALLPAPER_DIR = Path.home() / "wallpaper"
HYPR_CONF = Path.home() / ".config" / "hypr" / "hyprland.conf"


def _run(cmd: str, timeout: int = 30) -> str:
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "Done."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


def _which(binary: str) -> bool:
    return subprocess.run(["which", binary], capture_output=True).returncode == 0


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="wallpaper",
            description=(
                "Set, get, or pick a random wallpaper. "
                "Actions: 'set <path>' — set specific wallpaper; "
                "'get' — show current wallpaper; "
                "'random' — pick random file from ~/wallpaper/. "
                "Uses swww (Wayland) or swaybg as fallback."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["set", "get", "random"]},
                    "path": {"type": "string", "description": "Wallpaper path for 'set' action."},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="theme_switch",
            description=(
                "Switch between dark/light GTK themes. "
                "Updates GTK theme, icon theme, and cursor via gsettings. "
                "Actions: 'dark', 'light', 'status'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["dark", "light", "status"]},
                    "gtk_theme": {"type": "string", "description": "Custom GTK theme name (optional)."},
                    "icon_theme": {"type": "string", "description": "Custom icon theme name (optional)."},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="colorscheme",
            description=(
                "Generate a colorscheme from the current wallpaper using pywal or wallust. "
                "Applies colors to terminal and desktop environment. "
                "Actions: 'generate' (run wal/wallust on current wallpaper), 'apply' (re-apply last scheme), 'status'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["generate", "apply", "status"]},
                    "wallpaper": {"type": "string", "description": "Custom wallpaper path for generation (optional)."},
                    "backend": {"type": "string", "enum": ["wal", "wallust"], "default": "wal"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="font_preview",
            description=(
                "List installed fonts or get details about a specific font. "
                "Actions: 'list' — show all font families; "
                "'search <query>' — filter fonts by name; "
                "'info <family>' — show font path and metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "search", "info"]},
                    "query": {"type": "string", "description": "Font name to search or get info for."},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="hyprland_config",
            description=(
                "Read or modify Hyprland config values at ~/.config/hypr/hyprland.conf. "
                "Actions: 'get <key>' — show current value(s) matching key; "
                "'set <key> <value>' — update a config value; "
                "'show' — dump decoration/animation/general sections; "
                "'reload' — run hyprctl reload."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["get", "set", "show", "reload"]},
                    "key": {"type": "string", "description": "Config key to get/set (e.g. 'gaps_in', 'rounding', 'blur')."},
                    "value": {"type": "string", "description": "New value for 'set' action."},
                },
                "required": ["action"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "wallpaper": _wallpaper,
        "theme_switch": _theme_switch,
        "colorscheme": _colorscheme,
        "font_preview": _font_preview,
        "hyprland_config": _hyprland_config,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _wallpaper(args: dict) -> str:
    action = args["action"]

    if action == "get":
        # Check swww cache or look for common state files
        cache = Path.home() / ".cache" / "swww"
        if cache.exists():
            for f in cache.iterdir():
                return f"Current wallpaper (swww): {f.read_text().strip()}"
        wal_seq = Path.home() / ".config" / "wal" / "wal"
        if wal_seq.exists():
            return f"Last wal wallpaper: {wal_seq.read_text().strip()}"
        return "Cannot determine current wallpaper (no swww cache or wal state)."

    if action == "random":
        if not WALLPAPER_DIR.exists():
            return f"Wallpaper directory not found: {WALLPAPER_DIR}"
        images = [f for f in WALLPAPER_DIR.rglob("*") if f.suffix.lower() in
                  {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}]
        if not images:
            return f"No images found in {WALLPAPER_DIR}"
        import random
        chosen = random.choice(images)
        args = dict(args, action="set", path=str(chosen))
        return _wallpaper(args)

    # action == "set"
    path = args.get("path", "")
    if not path:
        return "Usage: set requires a path"
    wall = Path(path.replace("~", str(Path.home()))).expanduser()
    if not wall.exists():
        return f"File not found: {wall}"

    if _which("swww"):
        # Ensure swww daemon is running
        _run("swww query || swww init")
        out = _run(f'swww img "{wall}" --transition-type fade --transition-fps 60')
        return f"Wallpaper set via swww: {wall}\n{out}"
    elif _which("swaybg"):
        _run(f'pkill swaybg; swaybg -i "{wall}" -m fill &')
        return f"Wallpaper set via swaybg: {wall}"
    else:
        return "No wallpaper setter found. Install swww or swaybg."


def _theme_switch(args: dict) -> str:
    action = args["action"]

    DARK_DEFAULTS = {"gtk": "Adwaita-dark", "icons": "Papirus-Dark", "cursor": "Adwaita"}
    LIGHT_DEFAULTS = {"gtk": "Adwaita", "icons": "Papirus-Light", "cursor": "Adwaita"}

    if action == "status":
        gtk = _run("gsettings get org.gnome.desktop.interface gtk-theme")
        icons = _run("gsettings get org.gnome.desktop.interface icon-theme")
        cursor = _run("gsettings get org.gnome.desktop.interface cursor-theme")
        color = _run("gsettings get org.gnome.desktop.interface color-scheme")
        return f"GTK theme:   {gtk}\nIcon theme:  {icons}\nCursor:      {cursor}\nColor scheme: {color}"

    defaults = DARK_DEFAULTS if action == "dark" else LIGHT_DEFAULTS
    gtk_theme = args.get("gtk_theme", defaults["gtk"])
    icon_theme = args.get("icon_theme", defaults["icons"])
    cursor = defaults["cursor"]
    color_scheme = "prefer-dark" if action == "dark" else "prefer-light"

    results = []
    results.append(_run(f"gsettings set org.gnome.desktop.interface gtk-theme '{gtk_theme}'"))
    results.append(_run(f"gsettings set org.gnome.desktop.interface icon-theme '{icon_theme}'"))
    results.append(_run(f"gsettings set org.gnome.desktop.interface cursor-theme '{cursor}'"))
    results.append(_run(f"gsettings set org.gnome.desktop.interface color-scheme '{color_scheme}'"))

    # Also set GTK4 dark preference via environment hint
    if _which("hyprctl"):
        results.append(_run("hyprctl reload"))

    return f"Switched to {action} theme:\n  GTK:    {gtk_theme}\n  Icons:  {icon_theme}\n  Cursor: {cursor}"


def _colorscheme(args: dict) -> str:
    action = args["action"]
    backend = args.get("backend", "wal")

    if action == "status":
        colors_json = Path.home() / ".cache" / "wal" / "colors.json"
        if colors_json.exists():
            data = json.loads(colors_json.read_text())
            wallpaper = data.get("wallpaper", "unknown")
            colors = data.get("colors", {})
            lines = [f"Last generated scheme from: {wallpaper}", "Colors:"]
            for k, v in list(colors.items())[:8]:
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        return "No colorscheme found. Run 'generate' first."

    if action == "apply":
        out = _run("(cat ~/.cache/wal/colors-wal.sh 2>/dev/null | source /dev/stdin) || wal -R")
        return f"Colorscheme re-applied.\n{out}"

    # generate
    wallpaper = args.get("wallpaper", "")
    if not wallpaper:
        # Try to get current wallpaper
        wal_file = Path.home() / ".config" / "wal" / "wal"
        if wal_file.exists():
            wallpaper = wal_file.read_text().strip()
        else:
            # Check swww cache
            cache = Path.home() / ".cache" / "swww"
            if cache.exists():
                for f in cache.iterdir():
                    wallpaper = f.read_text().strip()
                    break
    if not wallpaper:
        return "Cannot determine current wallpaper. Provide wallpaper path explicitly."

    if backend == "wallust" and _which("wallust"):
        out = _run(f'wallust run "{wallpaper}"')
    elif _which("wal"):
        out = _run(f'wal -i "{wallpaper}" --backend haishoku -n')
    else:
        return "Neither pywal (wal) nor wallust is installed."

    return f"Colorscheme generated from {wallpaper}\n{out}"


def _font_preview(args: dict) -> str:
    action = args["action"]
    query = args.get("query", "")

    if action == "list":
        out = _run("fc-list : family | sort -u | head -100")
        lines = out.splitlines()
        return f"Installed font families ({len(lines)} shown):\n" + "\n".join(f"  {l}" for l in lines)

    elif action == "search":
        if not query:
            return "search requires a query"
        out = _run(f"fc-list : family | grep -i '{query}' | sort -u")
        lines = [l for l in out.splitlines() if l.strip()]
        if not lines:
            return f"No fonts matching '{query}'"
        return f"Fonts matching '{query}':\n" + "\n".join(f"  {l}" for l in lines)

    elif action == "info":
        if not query:
            return "info requires a font family name"
        out = _run(f"fc-list : family file | grep -i '{query}' | head -20")
        if not out or "Error" in out:
            return f"No font found matching '{query}'"
        lines = []
        for line in out.splitlines():
            if ":" in line:
                path, rest = line.split(":", 1)
                lines.append(f"  Path:   {path.strip()}")
                lines.append(f"  Family: {rest.strip()}")
                lines.append("")
        return f"Font info for '{query}':\n" + "\n".join(lines)

    return "Unknown action."


def _hyprland_config(args: dict) -> str:
    action = args["action"]

    if not HYPR_CONF.exists():
        return f"Hyprland config not found: {HYPR_CONF}"

    text = HYPR_CONF.read_text()

    if action == "reload":
        if _which("hyprctl"):
            return _run("hyprctl reload")
        return "hyprctl not found."

    elif action == "show":
        # Extract general, decoration, animations sections
        sections = []
        in_section = False
        depth = 0
        current: list[str] = []
        capture_names = {"general", "decoration", "animations", "misc"}
        current_name = ""
        for line in text.splitlines():
            stripped = line.strip()
            if not in_section:
                m = re.match(r'^(\w+)\s*\{', stripped)
                if m and m.group(1) in capture_names:
                    in_section = True
                    depth = 1
                    current_name = m.group(1)
                    current = [line]
                    continue
            else:
                current.append(line)
                depth += stripped.count("{") - stripped.count("}")
                if depth <= 0:
                    in_section = False
                    sections.append(f"[{current_name}]\n" + "\n".join(current))
                    current = []
        return "\n\n".join(sections) if sections else "No matching sections found."

    elif action == "get":
        key = args.get("key", "")
        if not key:
            return "get requires a key"
        matches = []
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(rf'\b{re.escape(key)}\b', line):
                matches.append(f"  L{i}: {line.strip()}")
        if not matches:
            return f"Key '{key}' not found in {HYPR_CONF}"
        return f"Matches for '{key}' in {HYPR_CONF}:\n" + "\n".join(matches)

    elif action == "set":
        key = args.get("key", "")
        value = args.get("value", "")
        if not key or not value:
            return "set requires key and value"
        # Replace first occurrence of `key = <anything>` within config
        new_text, count = re.subn(
            rf'^(\s*{re.escape(key)}\s*=\s*).*$',
            rf'\g<1>{value}',
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if count == 0:
            return f"Key '{key}' not found in config. No changes made."
        HYPR_CONF.write_text(new_text)
        result = f"Set '{key} = {value}' in {HYPR_CONF}"
        if _which("hyprctl"):
            reload_out = _run("hyprctl reload")
            result += f"\nReloaded: {reload_out}"
        return result

    return "Unknown action."


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
