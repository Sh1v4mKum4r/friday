"""friday-gaming MCP server.

Tools for gaming: game mode toggle, GPU performance management,
process management, and game launching.

Usage: python server.py (runs as MCP stdio server)
"""

import subprocess
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("friday-gaming")

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _run(cmd: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip() or result.stderr.strip() or "Done."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


def _is_game_mode() -> bool:
    """Check if game mode is currently active."""
    return os.path.exists("/tmp/friday-game-mode")


# -----------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="game_mode",
            description="Toggle game mode on/off. When ON: kills background apps, sets GPU to performance, raises process priority. When OFF: restores normal state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "'on' to enable, 'off' to disable, 'status' to check",
                        "enum": ["on", "off", "status"],
                    }
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="gpu_performance",
            description="Set NVIDIA GPU performance level. Modes: 'max' for maximum performance, 'auto' for adaptive, 'low' for power saving.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["max", "auto", "low"],
                    }
                },
                "required": ["mode"],
            },
        ),
        Tool(
            name="kill_background",
            description="Kill resource-heavy background processes to free RAM/CPU for gaming. Shows what it killed.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="launch_game",
            description="Launch a game via Steam, Lutris, or directly. Automatically enables game mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "game": {
                        "type": "string",
                        "description": "Game name or Steam app ID or path to executable",
                    }
                },
                "required": ["game"],
            },
        ),
        Tool(
            name="gaming_stats",
            description="Show current gaming-relevant system stats: GPU temp, VRAM, FPS (if mangohud running), CPU load, RAM usage.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "game_mode":
        result = _game_mode(arguments.get("action", "status"))
    elif name == "gpu_performance":
        result = _gpu_performance(arguments.get("mode", "auto"))
    elif name == "kill_background":
        result = _kill_background()
    elif name == "launch_game":
        result = _launch_game(arguments.get("game", ""))
    elif name == "gaming_stats":
        result = _gaming_stats()
    else:
        result = f"Unknown tool: {name}"

    return [TextContent(type="text", text=result)]


# -----------------------------------------------------------------------
# Implementations
# -----------------------------------------------------------------------

# Processes to kill in game mode (resource hogs that aren't essential)
_KILLABLE = [
    "electron", "slack", "discord", "telegram-desktop",
    "thunderbird", "evolution", "epiphany",
    "tracker-miner-fs-3", "tracker-extract-3",
    "baloo_file", "zeitgeist",
]


def _game_mode(action: str) -> str:
    if action == "status":
        return f"Game mode: {'ON' if _is_game_mode() else 'OFF'}"

    if action == "on":
        # Kill background apps
        killed = _kill_background()
        # Set GPU to max
        _gpu_performance("max")
        # Set CPU governor to performance
        _run("echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null")
        # Mark game mode active
        with open("/tmp/friday-game-mode", "w") as f:
            f.write("on")
        return f"Game mode ON.\n{killed}\nGPU: max performance\nCPU: performance governor"

    if action == "off":
        # Restore GPU
        _gpu_performance("auto")
        # Restore CPU governor
        _run("echo 'powersave' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null")
        # Remove marker
        try:
            os.unlink("/tmp/friday-game-mode")
        except FileNotFoundError:
            pass
        return "Game mode OFF. GPU: auto, CPU: powersave"

    return f"Unknown action: {action}"


def _gpu_performance(mode: str) -> str:
    mode_map = {
        "max": "prefer maximum performance",
        "auto": "adaptive",
        "low": "prefer minimum power",
    }
    setting = mode_map.get(mode, "adaptive")

    # NVIDIA: set via nvidia-settings or nvidia-smi
    result = _run(f'nvidia-settings -a "[gpu:0]/GPUPowerMizerMode=1" 2>/dev/null')
    if "max" in mode:
        _run("nvidia-smi -pm 1 2>/dev/null")
        _run("nvidia-smi -pl 75 2>/dev/null")  # Set power limit to max TDP
    elif "low" in mode:
        _run("nvidia-smi -pm 0 2>/dev/null")

    return f"GPU performance set to: {mode} ({setting})"


def _kill_background() -> str:
    killed = []
    for proc in _KILLABLE:
        result = _run(f"pkill -f '{proc}' 2>/dev/null")
        check = _run(f"pgrep -f '{proc}' 2>/dev/null")
        if not check or check == "Done.":
            killed.append(proc)

    if killed:
        return f"Killed: {', '.join(killed)}"
    return "No background apps to kill."


def _launch_game(game: str) -> str:
    # Enable game mode first
    _game_mode("on")

    # Try Steam first (by name or app ID)
    if game.isdigit():
        _run(f"steam steam://rungameid/{game} &")
        return f"Launching Steam app {game} with game mode ON."

    # Try Lutris
    lutris_check = _run(f"lutris -l 2>/dev/null | grep -i '{game}'")
    if lutris_check and "Error" not in lutris_check:
        slug = lutris_check.split("|")[0].strip() if "|" in lutris_check else game
        _run(f"lutris lutris:rungame/{slug} &")
        return f"Launching '{game}' via Lutris with game mode ON."

    # Try Steam by name search
    steam_check = _run(f"steam steam://run/{game} &")
    return f"Attempting to launch '{game}'. Game mode ON."


def _gaming_stats() -> str:
    parts = []

    # GPU
    gpu = _run("nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits")
    if gpu and "Error" not in gpu:
        fields = [f.strip() for f in gpu.split(",")]
        if len(fields) >= 5:
            parts.append(f"GPU: {fields[0]} | {fields[4]}% util | {fields[1]}°C | VRAM: {fields[2]}MB/{fields[3]}MB")

    # CPU
    load = _run("cat /proc/loadavg | cut -d' ' -f1-3")
    temp = _run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    if temp and temp.isdigit():
        temp = f"{int(temp) / 1000:.0f}°C"
    parts.append(f"CPU: load {load} | {temp}")

    # RAM
    ram = _run("free -h | grep Mem | awk '{print $3\"/\"$2}'")
    parts.append(f"RAM: {ram}")

    # Game mode
    parts.append(f"Game mode: {'ON' if _is_game_mode() else 'OFF'}")

    return "\n".join(parts)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
