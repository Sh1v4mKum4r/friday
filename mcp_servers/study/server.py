"""friday-study MCP server.

Tools for student workflow: pomodoro, assignments, flashcards, notes, deadlines.
"""

import subprocess
import json
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("friday-study")

DATA_DIR = Path.home() / ".local" / "share" / "friday" / "study"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(name: str) -> dict | list:
    path = DATA_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return [] if name in ("assignments", "flashcards") else {}


def _save_json(name: str, data):
    (DATA_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, default=str))


def _notify(msg: str, title: str = "Friday Study"):
    subprocess.Popen(["notify-send", title, msg])


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="pomodoro",
            description="Start/stop a Pomodoro timer. Actions: 'start [minutes]' (default 25), 'break [minutes]' (default 5), 'status', 'stop'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["start", "break", "status", "stop"]},
                    "minutes": {"type": "integer", "default": 25},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="assignment",
            description="Track assignments. Actions: 'add <title> <due_date> [course]', 'list', 'done <title>', 'remove <title>', 'upcoming' (next 7 days).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "list", "done", "remove", "upcoming"]},
                    "title": {"type": "string"},
                    "due_date": {"type": "string", "description": "YYYY-MM-DD format"},
                    "course": {"type": "string"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="flashcard",
            description="Create and review flashcards. Actions: 'add <front> <back> [deck]', 'review [deck]', 'list', 'stats'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "review", "list", "stats"]},
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                    "deck": {"type": "string", "default": "general"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="study_notes",
            description="Quick note taking. Actions: 'add <topic> <content>', 'search <query>', 'list', 'read <topic>'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "search", "list", "read"]},
                    "topic": {"type": "string"},
                    "content": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="study_timer",
            description="Track total study time. Actions: 'start <subject>', 'stop', 'today', 'week', 'stats'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["start", "stop", "today", "week", "stats"]},
                    "subject": {"type": "string"},
                },
                "required": ["action"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "pomodoro": _pomodoro,
        "assignment": _assignment,
        "flashcard": _flashcard,
        "study_notes": _study_notes,
        "study_timer": _study_timer,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _pomodoro(args: dict) -> str:
    action = args["action"]
    minutes = args.get("minutes", 25)
    state = _load_json("pomodoro_state")

    if action == "start":
        end_time = time.time() + (minutes * 60)
        state = {"active": True, "type": "work", "end": end_time, "minutes": minutes}
        _save_json("pomodoro_state", state)
        # Schedule notification
        subprocess.Popen(["bash", "-c", f"sleep {minutes * 60} && notify-send 'Friday Study' 'Pomodoro done! Take a break.' &"])
        return f"Pomodoro started: {minutes} minutes. Focus!"

    elif action == "break":
        mins = args.get("minutes", 5)
        state = {"active": True, "type": "break", "end": time.time() + (mins * 60), "minutes": mins}
        _save_json("pomodoro_state", state)
        subprocess.Popen(["bash", "-c", f"sleep {mins * 60} && notify-send 'Friday Study' 'Break over! Back to work.' &"])
        return f"Break started: {mins} minutes. Relax."

    elif action == "status":
        if not state.get("active"):
            return "No active pomodoro."
        remaining = max(0, state["end"] - time.time())
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        return f"{'Work' if state['type'] == 'work' else 'Break'}: {mins}m {secs}s remaining"

    elif action == "stop":
        state = {"active": False}
        _save_json("pomodoro_state", state)
        return "Pomodoro stopped."

    return "Unknown action."


def _assignment(args: dict) -> str:
    action = args["action"]
    assignments = _load_json("assignments")

    if action == "add":
        title = args.get("title", "")
        due = args.get("due_date", "")
        course = args.get("course", "")
        if not title or not due:
            return "Usage: add requires title and due_date (YYYY-MM-DD)"
        assignments.append({"title": title, "due": due, "course": course, "done": False})
        _save_json("assignments", assignments)
        return f"Added: '{title}' due {due}" + (f" ({course})" if course else "")

    elif action == "list":
        active = [a for a in assignments if not a.get("done")]
        if not active:
            return "No assignments."
        active.sort(key=lambda a: a["due"])
        lines = []
        for a in active:
            days = (datetime.strptime(a["due"], "%Y-%m-%d") - datetime.now()).days
            urgency = "OVERDUE" if days < 0 else f"{days}d left"
            lines.append(f"  [{urgency}] {a['title']} — due {a['due']}" + (f" ({a['course']})" if a.get("course") else ""))
        return "Assignments:\n" + "\n".join(lines)

    elif action == "done" and args.get("title"):
        for a in assignments:
            if a["title"].lower() == args["title"].lower():
                a["done"] = True
                _save_json("assignments", assignments)
                return f"Completed: '{a['title']}'"
        return f"Not found: '{args['title']}'"

    elif action == "remove" and args.get("title"):
        assignments = [a for a in assignments if a["title"].lower() != args["title"].lower()]
        _save_json("assignments", assignments)
        return f"Removed: '{args['title']}'"

    elif action == "upcoming":
        week = datetime.now() + timedelta(days=7)
        upcoming = [a for a in assignments if not a.get("done") and datetime.strptime(a["due"], "%Y-%m-%d") <= week]
        if not upcoming:
            return "Nothing due in the next 7 days."
        upcoming.sort(key=lambda a: a["due"])
        lines = [f"  {a['title']} — {a['due']}" + (f" ({a['course']})" if a.get("course") else "") for a in upcoming]
        return "Due this week:\n" + "\n".join(lines)

    return "Unknown action."


def _flashcard(args: dict) -> str:
    action = args["action"]
    cards = _load_json("flashcards")

    if action == "add":
        front = args.get("front", "")
        back = args.get("back", "")
        deck = args.get("deck", "general")
        if not front or not back:
            return "Usage: add requires front and back"
        cards.append({"front": front, "back": back, "deck": deck, "reviews": 0, "correct": 0})
        _save_json("flashcards", cards)
        return f"Card added to '{deck}': {front[:50]}"

    elif action == "review":
        deck = args.get("deck", "")
        pool = [c for c in cards if not deck or c["deck"] == deck]
        if not pool:
            return "No cards to review." + (f" (deck: {deck})" if deck else "")
        # Pick least reviewed cards
        pool.sort(key=lambda c: c["reviews"])
        card = pool[0]
        card["reviews"] += 1
        _save_json("flashcards", cards)
        return f"Q: {card['front']}\n\n(Think about it, then ask me for the answer)\n\nA: ||{card['back']}||"

    elif action == "list":
        decks = {}
        for c in cards:
            d = c.get("deck", "general")
            decks[d] = decks.get(d, 0) + 1
        if not decks:
            return "No flashcards."
        lines = [f"  {deck}: {count} cards" for deck, count in sorted(decks.items())]
        return f"Flashcard decks ({len(cards)} total):\n" + "\n".join(lines)

    elif action == "stats":
        total = len(cards)
        reviewed = sum(1 for c in cards if c["reviews"] > 0)
        return f"Cards: {total} | Reviewed: {reviewed} | Never reviewed: {total - reviewed}"

    return "Unknown action."


def _study_notes(args: dict) -> str:
    action = args["action"]
    notes_dir = DATA_DIR / "notes"
    notes_dir.mkdir(exist_ok=True)

    if action == "add":
        topic = args.get("topic", "").replace(" ", "-").lower()
        content = args.get("content", "")
        if not topic or not content:
            return "Usage: add requires topic and content"
        path = notes_dir / f"{topic}.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        if path.exists():
            with path.open("a") as f:
                f.write(f"\n\n---\n*{timestamp}*\n\n{content}")
        else:
            path.write_text(f"# {topic}\n\n*{timestamp}*\n\n{content}")
        return f"Note saved to {topic}.md"

    elif action == "search":
        query = args.get("query", "")
        if not query:
            return "Usage: search requires a query"
        results = []
        for note in notes_dir.glob("*.md"):
            text = note.read_text()
            if query.lower() in text.lower():
                # Find matching line
                for line in text.splitlines():
                    if query.lower() in line.lower():
                        results.append(f"  {note.stem}: {line.strip()[:80]}")
                        break
        return f"Found {len(results)} matches:\n" + "\n".join(results) if results else f"No notes matching '{query}'"

    elif action == "list":
        notes = sorted(notes_dir.glob("*.md"))
        if not notes:
            return "No notes."
        lines = []
        for n in notes:
            size = n.stat().st_size
            lines.append(f"  {n.stem} ({size} bytes)")
        return f"Notes ({len(notes)}):\n" + "\n".join(lines)

    elif action == "read":
        topic = args.get("topic", "").replace(" ", "-").lower()
        path = notes_dir / f"{topic}.md"
        if path.exists():
            content = path.read_text()
            return content[:3000] + "\n..." if len(content) > 3000 else content
        return f"Note not found: {topic}"

    return "Unknown action."


def _study_timer(args: dict) -> str:
    action = args["action"]
    sessions = _load_json("study_sessions")
    if not isinstance(sessions, dict):
        sessions = {"active": None, "log": []}

    if action == "start":
        subject = args.get("subject", "general")
        sessions["active"] = {"subject": subject, "start": datetime.now().isoformat()}
        _save_json("study_sessions", sessions)
        return f"Study timer started: {subject}"

    elif action == "stop":
        if not sessions.get("active"):
            return "No active study session."
        start = datetime.fromisoformat(sessions["active"]["start"])
        duration = (datetime.now() - start).total_seconds() / 60
        sessions.setdefault("log", []).append({
            "subject": sessions["active"]["subject"],
            "date": start.strftime("%Y-%m-%d"),
            "minutes": round(duration),
        })
        subject = sessions["active"]["subject"]
        sessions["active"] = None
        _save_json("study_sessions", sessions)
        return f"Studied {subject} for {round(duration)} minutes."

    elif action == "today":
        today = datetime.now().strftime("%Y-%m-%d")
        today_sessions = [s for s in sessions.get("log", []) if s["date"] == today]
        total = sum(s["minutes"] for s in today_sessions)
        by_subject = {}
        for s in today_sessions:
            by_subject[s["subject"]] = by_subject.get(s["subject"], 0) + s["minutes"]
        lines = [f"  {subj}: {mins}m" for subj, mins in by_subject.items()]
        return f"Today: {total} minutes\n" + "\n".join(lines) if lines else "No study sessions today."

    elif action == "week":
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        week_sessions = [s for s in sessions.get("log", []) if s["date"] >= week_ago]
        total = sum(s["minutes"] for s in week_sessions)
        by_subject = {}
        for s in week_sessions:
            by_subject[s["subject"]] = by_subject.get(s["subject"], 0) + s["minutes"]
        lines = [f"  {subj}: {mins}m" for subj, mins in sorted(by_subject.items(), key=lambda x: -x[1])]
        return f"This week: {total} minutes ({total // 60}h {total % 60}m)\n" + "\n".join(lines) if lines else "No study this week."

    elif action == "stats":
        all_sessions = sessions.get("log", [])
        total = sum(s["minutes"] for s in all_sessions)
        by_subject = {}
        for s in all_sessions:
            by_subject[s["subject"]] = by_subject.get(s["subject"], 0) + s["minutes"]
        lines = [f"  {subj}: {mins // 60}h {mins % 60}m" for subj, mins in sorted(by_subject.items(), key=lambda x: -x[1])]
        return f"All time: {total // 60}h {total % 60}m across {len(all_sessions)} sessions\n" + "\n".join(lines)

    return "Unknown action."


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
