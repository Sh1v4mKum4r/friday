"""friday-security MCP server.

Tools for security testing, CTF challenges, encoding/decoding,
network scanning, and password auditing.

Usage: python server.py (runs as MCP stdio server)
"""

import subprocess
import base64
import hashlib
import binascii
import codecs
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("friday-security")


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
            name="nmap_scan",
            description="Run an nmap scan on a target. Modes: 'quick' (top 100 ports), 'full' (all ports), 'service' (version detection), 'vuln' (vulnerability scripts).",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "IP, hostname, or CIDR range"},
                    "mode": {"type": "string", "enum": ["quick", "full", "service", "vuln"], "default": "quick"},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="encode_decode",
            description="Encode or decode text. Formats: base64, hex, url, rot13, binary, md5, sha256, sha1.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["encode", "decode", "hash"]},
                    "format": {"type": "string", "enum": ["base64", "hex", "url", "rot13", "binary", "md5", "sha256", "sha1"]},
                    "text": {"type": "string"},
                },
                "required": ["action", "format", "text"],
            },
        ),
        Tool(
            name="port_check",
            description="Check if a specific port is open on a host.",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["host", "port"],
            },
        ),
        Tool(
            name="whois_lookup",
            description="Run a WHOIS lookup on a domain or IP.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Domain name or IP address"},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="dns_lookup",
            description="Query DNS records for a domain. Types: A, AAAA, MX, NS, TXT, CNAME, SOA, ANY.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "record_type": {"type": "string", "default": "A"},
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="password_strength",
            description="Analyze password strength and estimate crack time. Does NOT send the password anywhere.",
            inputSchema={
                "type": "object",
                "properties": {
                    "password": {"type": "string"},
                },
                "required": ["password"],
            },
        ),
        Tool(
            name="hash_identify",
            description="Identify the type of a hash string (MD5, SHA1, SHA256, bcrypt, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "hash_string": {"type": "string"},
                },
                "required": ["hash_string"],
            },
        ),
        Tool(
            name="network_info",
            description="Show local network information: interfaces, IP addresses, routes, ARP table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "detail": {"type": "string", "enum": ["basic", "full"], "default": "basic"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "nmap_scan": _nmap_scan,
        "encode_decode": _encode_decode,
        "port_check": _port_check,
        "whois_lookup": _whois_lookup,
        "dns_lookup": _dns_lookup,
        "password_strength": _password_strength,
        "hash_identify": _hash_identify,
        "network_info": _network_info,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _nmap_scan(args: dict) -> str:
    target = args["target"]
    mode = args.get("mode", "quick")
    flags = {
        "quick": "-T4 --top-ports 100",
        "full": "-T4 -p-",
        "service": "-sV -T4 --top-ports 100",
        "vuln": "--script vuln -T4 --top-ports 100",
    }
    return _run(f"nmap {flags.get(mode, flags['quick'])} {target}", timeout=120)


def _encode_decode(args: dict) -> str:
    action = args["action"]
    fmt = args["format"]
    text = args["text"]

    try:
        if action == "hash":
            if fmt == "md5":
                return hashlib.md5(text.encode()).hexdigest()
            elif fmt == "sha256":
                return hashlib.sha256(text.encode()).hexdigest()
            elif fmt == "sha1":
                return hashlib.sha1(text.encode()).hexdigest()
            return f"Unsupported hash: {fmt}"

        if action == "encode":
            if fmt == "base64":
                return base64.b64encode(text.encode()).decode()
            elif fmt == "hex":
                return binascii.hexlify(text.encode()).decode()
            elif fmt == "url":
                from urllib.parse import quote
                return quote(text)
            elif fmt == "rot13":
                return codecs.encode(text, "rot_13")
            elif fmt == "binary":
                return " ".join(format(ord(c), "08b") for c in text)
            return f"Unsupported encode format: {fmt}"

        if action == "decode":
            if fmt == "base64":
                return base64.b64decode(text.encode()).decode()
            elif fmt == "hex":
                return binascii.unhexlify(text).decode()
            elif fmt == "url":
                from urllib.parse import unquote
                return unquote(text)
            elif fmt == "rot13":
                return codecs.decode(text, "rot_13")
            elif fmt == "binary":
                chars = text.split()
                return "".join(chr(int(b, 2)) for b in chars)
            return f"Unsupported decode format: {fmt}"

    except Exception as e:
        return f"Error: {e}"
    return "Unknown action"


def _port_check(args: dict) -> str:
    host = args["host"]
    port = args["port"]
    result = _run(f"timeout 5 bash -c 'echo >/dev/tcp/{host}/{port}' 2>&1 && echo 'OPEN' || echo 'CLOSED'")
    return f"Port {port} on {host}: {result}"


def _whois_lookup(args: dict) -> str:
    return _run(f"whois {args['target']} 2>/dev/null | head -50")


def _dns_lookup(args: dict) -> str:
    domain = args["domain"]
    rtype = args.get("record_type", "A")
    return _run(f"dig +short {domain} {rtype}")


def _password_strength(args: dict) -> str:
    pw = args["password"]
    length = len(pw)
    has_upper = any(c.isupper() for c in pw)
    has_lower = any(c.islower() for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    has_special = any(not c.isalnum() for c in pw)
    charset = 0
    if has_lower: charset += 26
    if has_upper: charset += 26
    if has_digit: charset += 10
    if has_special: charset += 32

    entropy = length * (charset.bit_length() if charset > 0 else 0)
    if entropy < 28: strength = "Very Weak"
    elif entropy < 36: strength = "Weak"
    elif entropy < 60: strength = "Moderate"
    elif entropy < 80: strength = "Strong"
    else: strength = "Very Strong"

    return (
        f"Length: {length}\n"
        f"Character types: {'upper ' if has_upper else ''}{'lower ' if has_lower else ''}"
        f"{'digits ' if has_digit else ''}{'special' if has_special else ''}\n"
        f"Charset size: {charset}\n"
        f"Estimated entropy: ~{entropy} bits\n"
        f"Strength: {strength}"
    )


def _hash_identify(args: dict) -> str:
    h = args["hash_string"].strip()
    length = len(h)
    patterns = []
    if length == 32 and all(c in "0123456789abcdef" for c in h.lower()):
        patterns.append("MD5")
    if length == 40 and all(c in "0123456789abcdef" for c in h.lower()):
        patterns.append("SHA-1")
    if length == 64 and all(c in "0123456789abcdef" for c in h.lower()):
        patterns.append("SHA-256")
    if length == 128 and all(c in "0123456789abcdef" for c in h.lower()):
        patterns.append("SHA-512")
    if h.startswith("$2b$") or h.startswith("$2a$") or h.startswith("$2y$"):
        patterns.append("bcrypt")
    if h.startswith("$6$"):
        patterns.append("SHA-512 crypt (Unix)")
    if h.startswith("$5$"):
        patterns.append("SHA-256 crypt (Unix)")
    if h.startswith("$1$"):
        patterns.append("MD5 crypt (Unix)")
    if not patterns:
        patterns.append(f"Unknown (length: {length})")
    return f"Possible types: {', '.join(patterns)}"


def _network_info(args: dict) -> str:
    detail = args.get("detail", "basic")
    parts = [_run("ip addr show | grep -E 'inet |link/ether' | head -20")]
    if detail == "full":
        parts.append(f"\nRoutes:\n{_run('ip route')}")
        parts.append(f"\nARP:\n{_run('ip neigh')}")
        parts.append(f"\nListening ports:\n{_run('ss -tlnp')}")
    return "\n".join(parts)


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
