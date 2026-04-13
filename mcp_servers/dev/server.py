"""friday-dev MCP server.

Tools for development workflow: git summaries, project scaffolding,
test running, Docker management, and code stats.

Usage: python server.py (runs as MCP stdio server)
"""

import subprocess
import os
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("friday-dev")


def _run(cmd: str, cwd: str = None, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
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
            name="git_summary",
            description="Summarize git activity across all repos or a specific one. Shows uncommitted changes, recent commits, branches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repo path (default: scan ~/Projects/)"},
                    "days": {"type": "integer", "description": "How many days of history", "default": 7},
                },
            },
        ),
        Tool(
            name="project_scaffold",
            description="Create a new project with boilerplate. Types: 'python' (FastAPI), 'rust' (CLI), 'react' (Vite+TS), 'fullstack' (FastAPI+React).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "type": {"type": "string", "enum": ["python", "rust", "react", "fullstack"]},
                    "path": {"type": "string", "description": "Parent directory", "default": "~/Projects"},
                },
                "required": ["name", "type"],
            },
        ),
        Tool(
            name="run_tests",
            description="Detect and run tests in a project directory. Auto-detects pytest, cargo test, npm test, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory"},
                    "verbose": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="docker_manager",
            description="Manage Docker containers. Actions: 'ps' (running), 'images', 'stop <name>', 'rm <name>', 'logs <name>', 'stats'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["ps", "images", "stop", "rm", "logs", "stats", "prune"]},
                    "target": {"type": "string", "description": "Container name/ID (for stop, rm, logs)"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="code_stats",
            description="Count lines of code, files, and languages in a project directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="port_finder",
            description="Find what's running on a specific port, or list all listening ports.",
            inputSchema={
                "type": "object",
                "properties": {
                    "port": {"type": "integer", "description": "Specific port to check (omit for all)"},
                },
            },
        ),
        Tool(
            name="env_manager",
            description="Manage Python virtual environments. Actions: 'list' all venvs, 'create <path>', 'info <path>' (show packages).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "create", "info"]},
                    "path": {"type": "string"},
                },
                "required": ["action"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "git_summary": _git_summary,
        "project_scaffold": _project_scaffold,
        "run_tests": _run_tests,
        "docker_manager": _docker_manager,
        "code_stats": _code_stats,
        "port_finder": _port_finder,
        "env_manager": _env_manager,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _git_summary(args: dict) -> str:
    path = args.get("path", "")
    days = args.get("days", 7)

    if path:
        path = os.path.expanduser(path)
        if not os.path.isdir(os.path.join(path, ".git")):
            return f"Not a git repo: {path}"
        return _summarize_repo(path, days)

    # Scan ~/Projects for all repos
    projects_dir = os.path.expanduser("~/Projects")
    if not os.path.isdir(projects_dir):
        return "~/Projects not found."

    parts = []
    for entry in sorted(os.listdir(projects_dir)):
        repo_path = os.path.join(projects_dir, entry)
        if os.path.isdir(os.path.join(repo_path, ".git")):
            summary = _summarize_repo(repo_path, days)
            if "no activity" not in summary.lower():
                parts.append(f"### {entry}\n{summary}")

    return "\n\n".join(parts) if parts else "No recent git activity found."


def _summarize_repo(path: str, days: int) -> str:
    parts = []
    # Uncommitted changes
    status = _run("git status --short", cwd=path)
    if status and status != "Done.":
        changed = len(status.splitlines())
        parts.append(f"Uncommitted: {changed} files changed")

    # Recent commits
    commits = _run(f"git log --oneline --since='{days} days ago' | head -10", cwd=path)
    if commits and commits != "Done.":
        parts.append(f"Recent commits ({days}d):\n{commits}")
    else:
        parts.append(f"No commits in last {days} days")

    # Branch info
    branch = _run("git branch --show-current", cwd=path)
    ahead = _run("git rev-list --count @{u}..HEAD 2>/dev/null", cwd=path)
    behind = _run("git rev-list --count HEAD..@{u} 2>/dev/null", cwd=path)
    branch_info = f"Branch: {branch}"
    if ahead and ahead.isdigit() and int(ahead) > 0:
        branch_info += f" ({ahead} ahead)"
    if behind and behind.isdigit() and int(behind) > 0:
        branch_info += f" ({behind} behind)"
    parts.append(branch_info)

    return "\n".join(parts)


def _project_scaffold(args: dict) -> str:
    name = args["name"]
    proj_type = args["type"]
    parent = os.path.expanduser(args.get("path", "~/Projects"))
    project_dir = os.path.join(parent, name)

    if os.path.exists(project_dir):
        return f"Directory already exists: {project_dir}"

    os.makedirs(project_dir, exist_ok=True)

    if proj_type == "python":
        _run(f"cd {project_dir} && python -m venv .venv")
        Path(project_dir, "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
            f'dependencies = ["fastapi", "uvicorn"]\n'
        )
        Path(project_dir, "main.py").write_text(
            'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/")\ndef root():\n    return {"status": "ok"}\n'
        )
        _run(f"cd {project_dir} && git init && git add -A && git commit -m 'initial scaffold'")
        return f"Python (FastAPI) project created at {project_dir}"

    elif proj_type == "rust":
        _run(f"cargo init {project_dir}")
        _run(f"cd {project_dir} && git add -A && git commit -m 'initial scaffold'")
        return f"Rust project created at {project_dir}"

    elif proj_type == "react":
        _run(f"cd {parent} && npm create vite@latest {name} -- --template react-ts", timeout=60)
        _run(f"cd {project_dir} && git init && git add -A && git commit -m 'initial scaffold'")
        return f"React (Vite+TS) project created at {project_dir}"

    elif proj_type == "fullstack":
        os.makedirs(f"{project_dir}/backend", exist_ok=True)
        os.makedirs(f"{project_dir}/frontend", exist_ok=True)
        # Backend
        _run(f"cd {project_dir}/backend && python -m venv .venv")
        Path(project_dir, "backend", "main.py").write_text(
            'from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\n\n'
            'app = FastAPI()\napp.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])\n\n'
            '@app.get("/api/health")\ndef health():\n    return {"status": "ok"}\n'
        )
        # Frontend
        _run(f"cd {project_dir} && npm create vite@latest frontend -- --template react-ts", timeout=60)
        _run(f"cd {project_dir} && git init && git add -A && git commit -m 'initial scaffold'")
        return f"Fullstack (FastAPI+React) project created at {project_dir}"

    return f"Unknown project type: {proj_type}"


def _run_tests(args: dict) -> str:
    path = os.path.expanduser(args["path"])
    verbose = args.get("verbose", False)

    if not os.path.isdir(path):
        return f"Not a directory: {path}"

    # Auto-detect test framework
    if os.path.exists(os.path.join(path, "pyproject.toml")) or os.path.exists(os.path.join(path, "tests")):
        venv_pytest = os.path.join(path, ".venv", "bin", "pytest")
        cmd = venv_pytest if os.path.exists(venv_pytest) else "pytest"
        flags = "-v" if verbose else "-q"
        return _run(f"{cmd} {flags}", cwd=path, timeout=120)

    if os.path.exists(os.path.join(path, "Cargo.toml")):
        return _run("cargo test", cwd=path, timeout=120)

    if os.path.exists(os.path.join(path, "package.json")):
        return _run("npm test --if-present", cwd=path, timeout=120)

    return "No test framework detected."


def _docker_manager(args: dict) -> str:
    action = args["action"]
    target = args.get("target", "")

    cmds = {
        "ps": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
        "images": "docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'",
        "stats": "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'",
        "prune": "docker system prune -f",
    }

    if action in cmds:
        return _run(cmds[action])
    elif action in ("stop", "rm", "logs") and target:
        if action == "logs":
            return _run(f"docker logs --tail 30 {target}")
        return _run(f"docker {action} {target}")
    return f"Usage: {action} requires a target container name."


def _code_stats(args: dict) -> str:
    path = os.path.expanduser(args["path"])
    if not os.path.isdir(path):
        return f"Not a directory: {path}"

    # Try tokei/cloc if available, fallback to manual count
    tokei = _run(f"tokei {path} 2>/dev/null")
    if "Error" not in tokei and tokei != "Done.":
        return tokei

    cloc = _run(f"cloc {path} --quiet 2>/dev/null")
    if "Error" not in cloc and cloc != "Done.":
        return cloc

    # Manual fallback
    extensions = {}
    total_lines = 0
    total_files = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "node_modules", "target", "__pycache__")]
        for f in files:
            ext = Path(f).suffix or "no-ext"
            filepath = os.path.join(root, f)
            try:
                lines = sum(1 for _ in open(filepath, "rb"))
                extensions[ext] = extensions.get(ext, {"files": 0, "lines": 0})
                extensions[ext]["files"] += 1
                extensions[ext]["lines"] += lines
                total_files += 1
                total_lines += lines
            except (OSError, UnicodeDecodeError):
                pass

    parts = [f"Total: {total_files} files, {total_lines} lines\n"]
    for ext, data in sorted(extensions.items(), key=lambda x: -x[1]["lines"])[:15]:
        parts.append(f"  {ext:10} {data['files']:5} files  {data['lines']:7} lines")

    return "\n".join(parts)


def _port_finder(args: dict) -> str:
    port = args.get("port")
    if port:
        return _run(f"ss -tlnp | grep :{port} || echo 'Port {port} is not in use'")
    return _run("ss -tlnp | head -20")


def _env_manager(args: dict) -> str:
    action = args["action"]
    path = args.get("path", "")

    if action == "list":
        # Find all .venv directories in ~/Projects
        return _run("find ~/Projects -maxdepth 3 -name '.venv' -type d 2>/dev/null")

    elif action == "create" and path:
        path = os.path.expanduser(path)
        _run(f"python -m venv {path}")
        return f"Virtual environment created at {path}"

    elif action == "info" and path:
        path = os.path.expanduser(path)
        pip = os.path.join(path, "bin", "pip")
        if os.path.exists(pip):
            return _run(f"{pip} list")
        return f"No pip found at {path}"

    return f"Usage: {action} requires a path."


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
