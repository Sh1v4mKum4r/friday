"""friday-files MCP server.

Smart file management: organize downloads, find duplicates, bulk rename, large files, recent files.
"""

import hashlib
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("friday-files")

DOWNLOADS = Path.home() / "Downloads"

TYPE_MAP = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif", ".heic", ".heif", ".avif"},
    "videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp"},
    "documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".txt", ".md", ".rtf", ".csv"},
    "archives": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".tar.gz", ".tar.bz2"},
    "installers": {".deb", ".rpm", ".AppImage", ".appimage", ".sh", ".run", ".pkg", ".dmg", ".exe", ".msi"},
    "audio": {".mp3", ".flac", ".ogg", ".wav", ".aac", ".m4a", ".opus", ".wma"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h", ".java", ".rs", ".go", ".rb", ".php"},
}


def _classify(suffix: str) -> str:
    s = suffix.lower()
    for category, exts in TYPE_MAP.items():
        if s in exts:
            return category
    return "other"


def _file_hash(path: Path, block: int = 65536) -> str:
    h = hashlib.md5()
    try:
        with path.open("rb") as f:
            while chunk := f.read(block):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="organize_downloads",
            description=(
                "Scan ~/Downloads and sort files into subfolders by type "
                "(images/, videos/, documents/, archives/, installers/, audio/, code/, other/). "
                "Shows what was moved."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, show what would move without actually moving.",
                    },
                },
            },
        ),
        Tool(
            name="find_duplicates",
            description="Find duplicate files by MD5 hash in a directory. Shows groups and total space wasted.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "default": "~/Downloads",
                        "description": "Directory to scan (default ~/Downloads).",
                    },
                    "recursive": {"type": "boolean", "default": True},
                },
                "required": [],
            },
        ),
        Tool(
            name="bulk_rename",
            description=(
                "Rename files matching a glob pattern. "
                "Modes: 'lowercase', 'replace <old> <new>', 'prefix <text>', 'suffix <text>', 'sequential <pattern>' "
                "(e.g. pattern 'file_{:03d}' produces file_001, file_002 …). "
                "dry_run=true to preview."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory containing files to rename."},
                    "pattern": {"type": "string", "description": "Glob pattern to match files, e.g. '*.jpg'."},
                    "mode": {
                        "type": "string",
                        "enum": ["lowercase", "replace", "prefix", "suffix", "sequential"],
                    },
                    "arg1": {"type": "string", "description": "First argument (old text / prefix / suffix / sequential pattern)."},
                    "arg2": {"type": "string", "description": "Second argument (new text for replace mode)."},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["directory", "pattern", "mode"],
            },
        ),
        Tool(
            name="large_files",
            description="Find the largest files in a directory tree. Default top 20.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "default": "~", "description": "Root directory to scan."},
                    "top": {"type": "integer", "default": 20, "description": "Number of largest files to show."},
                },
            },
        ),
        Tool(
            name="recent_files",
            description="Show recently modified files in a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "default": "~", "description": "Directory to scan."},
                    "hours": {"type": "integer", "description": "Files modified within last N hours."},
                    "days": {"type": "integer", "description": "Files modified within last N days (used if hours not given)."},
                    "limit": {"type": "integer", "default": 30},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "organize_downloads": _organize_downloads,
        "find_duplicates": _find_duplicates,
        "bulk_rename": _bulk_rename,
        "large_files": _large_files,
        "recent_files": _recent_files,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _organize_downloads(args: dict) -> str:
    dry = args.get("dry_run", False)
    if not DOWNLOADS.exists():
        return f"Downloads directory not found: {DOWNLOADS}"

    moved: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for item in DOWNLOADS.iterdir():
        if item.is_dir():
            skipped.append(item.name)
            continue
        category = _classify(item.suffix)
        dest_dir = DOWNLOADS / category
        dest = dest_dir / item.name
        if dest == item:
            skipped.append(item.name)
            continue
        if dry:
            moved.append(f"  {item.name}  ->  {category}/")
        else:
            try:
                dest_dir.mkdir(exist_ok=True)
                # Avoid overwrite collisions
                if dest.exists():
                    stem, suf = item.stem, item.suffix
                    i = 1
                    while dest.exists():
                        dest = dest_dir / f"{stem}_{i}{suf}"
                        i += 1
                shutil.move(str(item), str(dest))
                moved.append(f"  {item.name}  ->  {category}/")
            except Exception as e:
                errors.append(f"  {item.name}: {e}")

    lines = [f"{'[DRY RUN] ' if dry else ''}Organized ~/Downloads — {len(moved)} files moved\n"]
    if moved:
        lines.append("Moved:\n" + "\n".join(moved))
    if skipped:
        lines.append(f"\nSkipped (dirs/already placed): {len(skipped)}")
    if errors:
        lines.append("\nErrors:\n" + "\n".join(errors))
    return "\n".join(lines)


def _find_duplicates(args: dict) -> str:
    raw_dir = args.get("directory", "~/Downloads")
    directory = Path(raw_dir.replace("~", str(Path.home()))).expanduser()
    recursive = args.get("recursive", True)

    if not directory.exists():
        return f"Directory not found: {directory}"

    hashes: dict[str, list[Path]] = {}
    pattern = "**/*" if recursive else "*"
    for f in directory.glob(pattern):
        if not f.is_file():
            continue
        h = _file_hash(f)
        if h:
            hashes.setdefault(h, []).append(f)

    dupes = {h: paths for h, paths in hashes.items() if len(paths) > 1}
    if not dupes:
        return f"No duplicates found in {directory}"

    total_wasted = 0
    lines = [f"Duplicates in {directory}:\n"]
    for h, paths in sorted(dupes.items(), key=lambda x: -sum(p.stat().st_size for p in x[1])):
        size = paths[0].stat().st_size
        wasted = size * (len(paths) - 1)
        total_wasted += wasted
        lines.append(f"  [{_human(size)} each, {len(paths)} copies, wasting {_human(wasted)}]")
        for p in paths:
            lines.append(f"    {p}")
    lines.append(f"\nTotal wasted: {_human(total_wasted)} across {len(dupes)} duplicate groups")
    return "\n".join(lines)


def _bulk_rename(args: dict) -> str:
    raw_dir = args.get("directory", ".")
    directory = Path(raw_dir.replace("~", str(Path.home()))).expanduser()
    glob_pat = args.get("pattern", "*")
    mode = args.get("mode", "lowercase")
    arg1 = args.get("arg1", "")
    arg2 = args.get("arg2", "")
    dry = args.get("dry_run", False)

    if not directory.exists():
        return f"Directory not found: {directory}"

    files = sorted(f for f in directory.glob(glob_pat) if f.is_file())
    if not files:
        return f"No files matching '{glob_pat}' in {directory}"

    renames: list[tuple[Path, Path]] = []
    for i, f in enumerate(files):
        if mode == "lowercase":
            new_name = f.name.lower()
        elif mode == "replace":
            if not arg1:
                return "replace mode requires arg1=<old> arg2=<new>"
            new_name = f.name.replace(arg1, arg2)
        elif mode == "prefix":
            if not arg1:
                return "prefix mode requires arg1=<text>"
            new_name = arg1 + f.name
        elif mode == "suffix":
            if not arg1:
                return "suffix mode requires arg1=<text>"
            new_name = f.stem + arg1 + f.suffix
        elif mode == "sequential":
            pattern_str = arg1 if arg1 else "file_{:03d}"
            try:
                new_name = pattern_str.format(i + 1) + f.suffix
            except Exception as e:
                return f"Invalid sequential pattern '{pattern_str}': {e}"
        else:
            return f"Unknown mode: {mode}"

        new_path = f.parent / new_name
        if new_path != f:
            renames.append((f, new_path))

    if not renames:
        return "No files would be renamed (all names unchanged)."

    lines = [f"{'[DRY RUN] ' if dry else ''}Renaming {len(renames)} files ({mode}):\n"]
    errors: list[str] = []
    for old, new in renames:
        lines.append(f"  {old.name}  ->  {new.name}")
        if not dry:
            try:
                old.rename(new)
            except Exception as e:
                errors.append(f"  {old.name}: {e}")
    if errors:
        lines.append("\nErrors:\n" + "\n".join(errors))
    return "\n".join(lines)


def _large_files(args: dict) -> str:
    raw_dir = args.get("directory", "~")
    directory = Path(raw_dir.replace("~", str(Path.home()))).expanduser()
    top = int(args.get("top", 20))

    if not directory.exists():
        return f"Directory not found: {directory}"

    files: list[tuple[int, Path]] = []
    for f in directory.rglob("*"):
        if f.is_file():
            try:
                files.append((f.stat().st_size, f))
            except OSError:
                pass

    files.sort(reverse=True)
    top_files = files[:top]
    if not top_files:
        return f"No files found in {directory}"

    lines = [f"Top {top} largest files in {directory}:\n"]
    for size, path in top_files:
        lines.append(f"  {_human(size):>10}  {path}")
    return "\n".join(lines)


def _recent_files(args: dict) -> str:
    raw_dir = args.get("directory", "~")
    directory = Path(raw_dir.replace("~", str(Path.home()))).expanduser()
    limit = int(args.get("limit", 30))

    if args.get("hours"):
        since = datetime.now() - timedelta(hours=int(args["hours"]))
        label = f"last {args['hours']}h"
    elif args.get("days"):
        since = datetime.now() - timedelta(days=int(args["days"]))
        label = f"last {args['days']} days"
    else:
        since = datetime.now() - timedelta(hours=24)
        label = "last 24h"

    if not directory.exists():
        return f"Directory not found: {directory}"

    recent: list[tuple[datetime, Path]] = []
    for f in directory.rglob("*"):
        if f.is_file():
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime >= since:
                    recent.append((mtime, f))
            except OSError:
                pass

    recent.sort(reverse=True)
    shown = recent[:limit]
    if not shown:
        return f"No files modified in {label} under {directory}"

    lines = [f"Files modified in {label} under {directory} ({len(recent)} total, showing {len(shown)}):\n"]
    for mtime, path in shown:
        lines.append(f"  {mtime.strftime('%Y-%m-%d %H:%M')}  {path}")
    return "\n".join(lines)


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
