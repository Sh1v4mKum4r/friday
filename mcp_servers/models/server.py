"""friday-models MCP server.

Ollama model manager: list, pull, remove, info, VRAM status, benchmark.
"""

import json
import subprocess
import time
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("friday-models")

OLLAMA_BASE = "http://localhost:11434"


def _run(cmd: str, timeout: int = 120) -> str:
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "Done."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


def _ollama_api(path: str, method: str = "GET", body: str = "") -> str:
    if method == "POST":
        cmd = f"curl -s --max-time 30 -X POST '{OLLAMA_BASE}{path}' -d '{body}'"
    else:
        cmd = f"curl -s --max-time 15 '{OLLAMA_BASE}{path}'"
    return _run(cmd)


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _which(binary: str) -> bool:
    return subprocess.run(["which", binary], capture_output=True).returncode == 0


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="model_list",
            description="List all installed Ollama models with sizes. Also shows current VRAM usage if nvidia-smi is available.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="model_pull",
            description=(
                "Pull (download) a new Ollama model. "
                "Shows progress. Examples: 'llama3', 'mistral', 'codellama:7b', 'phi3:mini'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model name/tag to pull (e.g. 'llama3:8b')."},
                },
                "required": ["model"],
            },
        ),
        Tool(
            name="model_remove",
            description="Remove (delete) an installed Ollama model by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model name to remove (e.g. 'llama3:8b')."},
                },
                "required": ["model"],
            },
        ),
        Tool(
            name="model_info",
            description="Show detailed info about an installed Ollama model: parameters, quantization, context length, template, license.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model name (e.g. 'llama3')."},
                },
                "required": ["model"],
            },
        ),
        Tool(
            name="vram_status",
            description="Show current NVIDIA VRAM usage via nvidia-smi. Also shows which Ollama models are currently loaded.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="model_benchmark",
            description=(
                "Run a quick benchmark on an Ollama model. "
                "Sends a short test prompt and measures tokens/second. "
                "Optional: custom prompt, token count."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model to benchmark."},
                    "prompt": {
                        "type": "string",
                        "default": "Write a short poem about the moon.",
                        "description": "Test prompt to send.",
                    },
                    "num_tokens": {
                        "type": "integer",
                        "default": 100,
                        "description": "Approximate tokens to generate.",
                    },
                },
                "required": ["model"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "model_list": _model_list,
        "model_pull": _model_pull,
        "model_remove": _model_remove,
        "model_info": _model_info,
        "vram_status": _vram_status,
        "model_benchmark": _model_benchmark,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _model_list(args: dict) -> str:
    raw = _ollama_api("/api/tags")
    lines = ["Installed Ollama models:\n"]

    try:
        data = json.loads(raw)
        models = data.get("models", [])
        if not models:
            lines.append("  No models installed.")
        else:
            total_size = 0
            for m in sorted(models, key=lambda x: x.get("size", 0), reverse=True):
                name = m.get("name", "?")
                size = m.get("size", 0)
                total_size += size
                modified = m.get("modified_at", "")[:10] if m.get("modified_at") else ""
                details = m.get("details", {})
                family = details.get("family", "")
                params = details.get("parameter_size", "")
                quant = details.get("quantization_level", "")
                meta = " | ".join(filter(None, [family, params, quant]))
                lines.append(f"  {name:<35}  {_human(size):>10}  {modified}  {meta}")
            lines.append(f"\nTotal: {len(models)} models, {_human(total_size)}")
    except Exception:
        # Fallback to CLI
        cli_out = _run("ollama list 2>/dev/null || echo 'ollama not running or not installed'")
        lines.append(cli_out)

    # Add VRAM info
    if _which("nvidia-smi"):
        vram = _run("nvidia-smi --query-gpu=name,memory.used,memory.free,memory.total --format=csv,noheader,nounits 2>/dev/null | head -4")
        if vram:
            lines.append(f"\nGPU VRAM:\n  {vram.replace(chr(10), chr(10) + '  ')}")

    return "\n".join(lines)


def _model_pull(args: dict) -> str:
    model = args.get("model", "")
    if not model:
        return "model is required"

    if not _which("ollama"):
        return "ollama CLI not found. Install it first."

    # Stream pull with CLI (captures progress summary)
    lines = [f"Pulling model: {model}\n"]
    cmd = f"ollama pull '{model}' 2>&1"
    result = _run(cmd, timeout=600)
    lines.append(result[-3000:] if len(result) > 3000 else result)

    # Show final size
    raw = _ollama_api("/api/tags")
    try:
        data = json.loads(raw)
        for m in data.get("models", []):
            if m.get("name", "").startswith(model.split(":")[0]):
                lines.append(f"\nInstalled: {m['name']} ({_human(m.get('size', 0))})")
                break
    except Exception:
        pass

    return "\n".join(lines)


def _model_remove(args: dict) -> str:
    model = args.get("model", "")
    if not model:
        return "model is required"

    # Use API DELETE
    raw = _run(f"curl -s -X DELETE '{OLLAMA_BASE}/api/delete' -d '{{\"name\":\"{model}\"}}'")
    if raw and "error" in raw.lower():
        return f"Error removing model: {raw}"

    # Also try CLI as fallback
    cli = _run(f"ollama rm '{model}' 2>&1")
    return f"Removed model: {model}\n{cli}"


def _model_info(args: dict) -> str:
    model = args.get("model", "")
    if not model:
        return "model is required"

    body = json.dumps({"name": model})
    raw = _run(f"curl -s --max-time 15 -X POST '{OLLAMA_BASE}/api/show' -d '{body}'")
    lines = [f"Model info: {model}\n"]

    try:
        data = json.loads(raw)
        if "error" in data:
            return f"Error: {data['error']}"

        details = data.get("details", {})
        if details:
            lines.append("Details:")
            for k, v in details.items():
                lines.append(f"  {k:<25} {v}")

        model_info = data.get("model_info", {})
        if model_info:
            lines.append("\nModel Parameters:")
            for k, v in model_info.items():
                if not isinstance(v, (dict, list)):
                    lines.append(f"  {k:<35} {v}")

        template = data.get("template", "")
        if template:
            lines.append(f"\nTemplate:\n{template[:500]}")

        license_text = data.get("license", "")
        if license_text:
            lines.append(f"\nLicense:\n{license_text[:300]}")

    except Exception:
        # Fallback CLI
        cli = _run(f"ollama show '{model}' 2>&1")
        lines.append(cli)

    return "\n".join(lines)


def _vram_status(args: dict) -> str:
    lines = []

    if _which("nvidia-smi"):
        # GPU overview
        gpu_info = _run(
            "nvidia-smi --query-gpu=index,name,memory.used,memory.free,memory.total,utilization.gpu,temperature.gpu "
            "--format=csv,noheader 2>/dev/null"
        )
        lines.append("=== GPU VRAM Status ===")
        for line in gpu_info.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                idx, name, used, free, total, util = parts[:6]
                temp = parts[6] if len(parts) > 6 else "?"
                used_n = int(used.replace(" MiB", "")) if "MiB" in used else 0
                total_n = int(total.replace(" MiB", "")) if "MiB" in total else 1
                bar_len = int(used_n / total_n * 30)
                bar = "#" * bar_len + "-" * (30 - bar_len)
                lines.append(f"  GPU {idx}: {name}")
                lines.append(f"  VRAM: [{bar}] {used}/{total}  GPU: {util}  Temp: {temp}C")
        lines.append("")
    else:
        lines.append("nvidia-smi not found (no NVIDIA GPU or driver not installed).")
        # Try AMD
        amd = _run("rocm-smi --showmeminfo vram 2>/dev/null | head -20")
        if amd and "Error" not in amd:
            lines.append(f"AMD GPU (rocm-smi):\n{amd}")

    # Check currently loaded Ollama models (running)
    running = _run(f"curl -s --max-time 5 '{OLLAMA_BASE}/api/ps'")
    try:
        data = json.loads(running)
        models = data.get("models", [])
        lines.append("=== Loaded Ollama Models ===")
        if models:
            for m in models:
                name = m.get("name", "?")
                size_vram = m.get("size_vram", 0)
                size = m.get("size", 0)
                expires = m.get("expires_at", "")[:19] if m.get("expires_at") else "N/A"
                lines.append(f"  {name:<35}  VRAM: {_human(size_vram):>10}  Total: {_human(size):>10}  Expires: {expires}")
        else:
            lines.append("  No models currently loaded.")
    except Exception:
        lines.append("Could not fetch running models from Ollama API.")

    return "\n".join(lines)


def _model_benchmark(args: dict) -> str:
    model = args.get("model", "")
    prompt = args.get("prompt", "Write a short poem about the moon.")
    num_tokens = int(args.get("num_tokens", 100))

    if not model:
        return "model is required"

    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_tokens},
    })

    lines = [f"Benchmarking '{model}'...\n", f"Prompt: {prompt[:80]}\n"]

    t_start = time.time()
    raw = _run(
        f"curl -s --max-time 120 -X POST '{OLLAMA_BASE}/api/generate' -d '{body}'",
        timeout=130,
    )
    t_end = time.time()
    elapsed = t_end - t_start

    try:
        data = json.loads(raw)
        if "error" in data:
            return f"Error: {data['error']}"

        response_text = data.get("response", "")
        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 0)
        prompt_eval_count = data.get("prompt_eval_count", 0)
        prompt_eval_duration_ns = data.get("prompt_eval_duration", 0)

        if eval_duration_ns > 0:
            tps = eval_count / (eval_duration_ns / 1e9)
        else:
            tps = eval_count / elapsed if elapsed > 0 else 0

        prompt_tps = (
            prompt_eval_count / (prompt_eval_duration_ns / 1e9)
            if prompt_eval_duration_ns > 0
            else 0
        )

        lines.append("Results:")
        lines.append(f"  Tokens generated:     {eval_count}")
        lines.append(f"  Generation speed:     {tps:.1f} tok/s")
        lines.append(f"  Prompt eval speed:    {prompt_tps:.1f} tok/s")
        lines.append(f"  Total time (wall):    {elapsed:.1f}s")
        lines.append(f"\nResponse preview:\n{response_text[:400]}")
        if len(response_text) > 400:
            lines.append("  [...]")

    except Exception:
        lines.append(f"Raw response (parse failed):\n{raw[:500]}")
        lines.append(f"\nElapsed: {elapsed:.1f}s")

    return "\n".join(lines)


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
