"""friday-media MCP server.

Tools for anime tracking, media management, and streaming lookups.

Usage: python server.py (runs as MCP stdio server)
"""

import subprocess
import json
import os
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("friday-media")

WATCHLIST_PATH = Path.home() / ".local" / "share" / "friday" / "watchlist.json"


def _run(cmd: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip() or result.stderr.strip() or "Done."
    except Exception as e:
        return f"Error: {e}"


def _load_watchlist() -> dict:
    if WATCHLIST_PATH.exists():
        return json.loads(WATCHLIST_PATH.read_text())
    return {"watching": [], "completed": [], "plan_to_watch": []}


def _save_watchlist(data: dict):
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(data, indent=2))


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="anime_search",
            description="Search for anime using ani-cli or by name. Returns titles and episode counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Anime name to search for"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="anime_watch",
            description="Watch an anime episode using ani-cli. Supports dub with 'dub' flag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "anime": {"type": "string", "description": "Anime name"},
                    "episode": {"type": "integer", "description": "Episode number", "default": 1},
                    "dub": {"type": "boolean", "description": "Watch dubbed version", "default": False},
                },
                "required": ["anime"],
            },
        ),
        Tool(
            name="watchlist",
            description="Manage your anime/show watchlist. Actions: 'list', 'add <title>', 'complete <title>', 'remove <title>', 'plan <title>'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "add", "complete", "remove", "plan"]},
                    "title": {"type": "string", "description": "Show/anime title"},
                    "episode": {"type": "integer", "description": "Current episode (for 'add')"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="now_playing",
            description="Show what's currently playing via playerctl — song/video title, artist, status.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="media_library",
            description="Scan and list media files in common directories (~/Videos, ~/Music, ~/Downloads).",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["video", "music", "all"], "default": "all"},
                    "directory": {"type": "string", "description": "Custom directory to scan"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "anime_search": _anime_search,
        "anime_watch": _anime_watch,
        "watchlist": _watchlist,
        "now_playing": _now_playing,
        "media_library": _media_library,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _anime_search(args: dict) -> str:
    query = args["query"]
    # Try ani-cli search
    result = _run(f"ani-cli -q 480 '{query}' 2>/dev/null | head -20")
    if result and "Error" not in result:
        return f"Search results for '{query}':\n{result}"
    return f"No results found for '{query}'. Make sure ani-cli is installed."


def _anime_watch(args: dict) -> str:
    anime = args["anime"]
    episode = args.get("episode", 1)
    dub = args.get("dub", False)
    dub_flag = "--dub" if dub else ""
    _run(f"ani-cli {dub_flag} -e {episode} '{anime}' &", timeout=5)
    # Update watchlist
    data = _load_watchlist()
    found = False
    for item in data["watching"]:
        if item["title"].lower() == anime.lower():
            item["episode"] = episode
            found = True
            break
    if not found:
        data["watching"].append({"title": anime, "episode": episode})
    _save_watchlist(data)
    return f"Playing: {anime} episode {episode} {'(dubbed)' if dub else '(subbed)'}. Updated watchlist."


def _watchlist(args: dict) -> str:
    action = args["action"]
    title = args.get("title", "")
    data = _load_watchlist()

    if action == "list":
        parts = []
        if data["watching"]:
            parts.append("Currently watching:")
            for item in data["watching"]:
                ep = f" (ep {item['episode']})" if 'episode' in item else ""
                parts.append(f"  - {item['title']}{ep}")
        if data["plan_to_watch"]:
            parts.append("Plan to watch:")
            for item in data["plan_to_watch"]:
                parts.append(f"  - {item['title']}")
        if data["completed"]:
            parts.append(f"Completed: {len(data['completed'])} shows")
        return "\n".join(parts) if parts else "Watchlist is empty."

    if action == "add" and title:
        episode = args.get("episode", 1)
        data["watching"].append({"title": title, "episode": episode})
        _save_watchlist(data)
        return f"Added '{title}' to watching (episode {episode})."

    if action == "complete" and title:
        data["watching"] = [i for i in data["watching"] if i["title"].lower() != title.lower()]
        data["plan_to_watch"] = [i for i in data["plan_to_watch"] if i["title"].lower() != title.lower()]
        data["completed"].append({"title": title})
        _save_watchlist(data)
        return f"Moved '{title}' to completed."

    if action == "remove" and title:
        for lst in ["watching", "plan_to_watch", "completed"]:
            data[lst] = [i for i in data[lst] if i["title"].lower() != title.lower()]
        _save_watchlist(data)
        return f"Removed '{title}' from watchlist."

    if action == "plan" and title:
        data["plan_to_watch"].append({"title": title})
        _save_watchlist(data)
        return f"Added '{title}' to plan-to-watch."

    return "Usage: list, add <title>, complete <title>, remove <title>, plan <title>"


def _now_playing(args: dict) -> str:
    status = _run("playerctl status 2>/dev/null")
    if "Error" in status or "No players" in status:
        return "Nothing playing."
    title = _run("playerctl metadata title 2>/dev/null")
    artist = _run("playerctl metadata artist 2>/dev/null")
    return f"{status}: {artist} — {title}"


def _media_library(args: dict) -> str:
    media_type = args.get("type", "all")
    custom_dir = args.get("directory", "")

    dirs = [custom_dir] if custom_dir else [
        str(Path.home() / "Videos"),
        str(Path.home() / "Music"),
        str(Path.home() / "Downloads"),
    ]

    video_ext = "mp4|mkv|avi|webm|mov|flv"
    music_ext = "mp3|flac|ogg|wav|m4a|opus"

    if media_type == "video":
        pattern = video_ext
    elif media_type == "music":
        pattern = music_ext
    else:
        pattern = f"{video_ext}|{music_ext}"

    results = []
    for d in dirs:
        if os.path.isdir(d):
            found = _run(f"find '{d}' -maxdepth 3 -regextype posix-extended -regex '.*\\.({pattern})$' 2>/dev/null | head -30")
            if found and "Error" not in found:
                results.append(f"{d}:\n{found}")

    return "\n\n".join(results) if results else "No media files found."


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
