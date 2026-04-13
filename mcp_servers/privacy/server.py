"""friday-privacy MCP server.

Privacy and network tools: VPN control, proxy toggle, network audit, browser clean, privacy check.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("friday-privacy")

PROXY_TOGGLE = Path.home() / "bin" / "proxy-toggle.sh"
PROXY_ENV = Path.home() / ".proxy_env"


def _run(cmd: str, timeout: int = 30, env: dict | None = None) -> str:
    try:
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        r = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout, env=run_env
        )
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
            name="vpn_control",
            description=(
                "Start, stop, or check VPN status. "
                "Auto-detects OpenVPN, WireGuard, or ProtonVPN. "
                "Actions: 'status', 'start [profile]', 'stop'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "start", "stop"]},
                    "profile": {
                        "type": "string",
                        "description": "VPN profile/config name (for OpenVPN). Optional.",
                    },
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="proxy_toggle",
            description=(
                "Toggle system proxy on or off using ~/bin/proxy-toggle.sh. "
                "Actions: 'on', 'off', 'status'. "
                "Sources ~/.proxy_env for environment variables."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["on", "off", "status"]},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="network_audit",
            description=(
                "Show open ports, active connections, DNS servers, and firewall rules. "
                "Modes: 'all' (full audit), 'ports', 'connections', 'dns', 'firewall'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["all", "ports", "connections", "dns", "firewall"],
                        "default": "all",
                    },
                },
            },
        ),
        Tool(
            name="browser_clean",
            description=(
                "Clear browser cache and cookies for Chrome, Firefox, and Librewolf. "
                "Shows space freed. "
                "Browsers: 'all', 'chrome', 'firefox', 'librewolf'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "browser": {
                        "type": "string",
                        "enum": ["all", "chrome", "firefox", "librewolf"],
                        "default": "all",
                    },
                    "what": {
                        "type": "string",
                        "enum": ["all", "cache", "cookies"],
                        "default": "cache",
                        "description": "What to clear.",
                    },
                },
            },
        ),
        Tool(
            name="privacy_check",
            description=(
                "Run a privacy audit: "
                "check DNS leaks (dig against external resolver), "
                "check public IP, "
                "check for suspicious listening processes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "check": {
                        "type": "string",
                        "enum": ["all", "dns", "ip", "processes"],
                        "default": "all",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "vpn_control": _vpn_control,
        "proxy_toggle": _proxy_toggle,
        "network_audit": _network_audit,
        "browser_clean": _browser_clean,
        "privacy_check": _privacy_check,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


def _detect_vpn_type() -> str:
    if _which("protonvpn-cli") or _which("protonvpn"):
        return "protonvpn"
    if _which("wg") or _which("wg-quick"):
        # Check if any WG interface is up
        wg = _run("wg show 2>/dev/null")
        if wg and "interface" in wg:
            return "wireguard"
    if _which("openvpn") or _which("nmcli"):
        return "openvpn"
    return "unknown"


def _vpn_control(args: dict) -> str:
    action = args["action"]
    profile = args.get("profile", "")
    vpn_type = _detect_vpn_type()

    if action == "status":
        lines = [f"VPN type detected: {vpn_type}"]

        # Check tun/wg interfaces
        ifaces = _run("ip link show | grep -E '^[0-9]+: (tun|wg|proton)' || true")
        if ifaces:
            lines.append(f"VPN interfaces:\n{ifaces}")

        # ProtonVPN status
        if _which("protonvpn-cli"):
            lines.append(_run("protonvpn-cli status 2>&1 | head -20"))
        elif _which("protonvpn"):
            lines.append(_run("protonvpn status 2>&1 | head -10"))

        # WireGuard
        wg_out = _run("wg show 2>/dev/null || true")
        if wg_out and "interface" in wg_out:
            lines.append(f"WireGuard:\n{wg_out[:500]}")

        # OpenVPN via NetworkManager
        nm_vpn = _run("nmcli con show --active 2>/dev/null | grep vpn || true")
        if nm_vpn:
            lines.append(f"Active VPN (NetworkManager): {nm_vpn}")

        # Public IP quick check
        pub_ip = _run("curl -s --max-time 5 https://api.ipify.org || echo 'unable to check'")
        lines.append(f"Public IP: {pub_ip}")

        return "\n".join(lines)

    elif action == "start":
        if vpn_type == "protonvpn":
            cmd = "protonvpn-cli connect --fastest" if not profile else f"protonvpn-cli connect '{profile}'"
            if _which("protonvpn") and not _which("protonvpn-cli"):
                cmd = "protonvpn connect --fastest"
            return _run(cmd, timeout=60)
        elif vpn_type == "wireguard":
            wg_profile = profile if profile else "wg0"
            return _run(f"sudo wg-quick up '{wg_profile}'")
        elif vpn_type == "openvpn":
            if profile:
                return _run(f"sudo openvpn --config '{profile}' --daemon", timeout=15)
            # Try NetworkManager
            vpns = _run("nmcli con show | grep vpn | awk '{print $1}' | head -5")
            if vpns:
                first_vpn = vpns.splitlines()[0]
                return _run(f"nmcli con up '{first_vpn}'")
            return "No VPN profile specified. Use: start with profile=<path or name>"
        return f"Cannot start VPN: type '{vpn_type}' not handled. Install protonvpn-cli, wg-quick, or openvpn."

    elif action == "stop":
        results = []
        if _which("protonvpn-cli"):
            results.append(_run("protonvpn-cli disconnect 2>&1"))
        if _which("protonvpn"):
            results.append(_run("protonvpn disconnect 2>&1"))
        wg_ifaces = _run("wg show interfaces 2>/dev/null || true")
        for iface in wg_ifaces.split():
            results.append(_run(f"sudo wg-quick down '{iface}'"))
        if _which("nmcli"):
            active_vpns = _run("nmcli con show --active | grep vpn | awk '{print $1}'")
            for vpn in active_vpns.splitlines():
                if vpn:
                    results.append(_run(f"nmcli con down '{vpn}'"))
        # Kill openvpn process
        results.append(_run("sudo pkill openvpn 2>/dev/null || true"))
        return "VPN stop attempted:\n" + "\n".join(r for r in results if r and r != "Done.")

    return "Unknown action."


def _proxy_toggle(args: dict) -> str:
    action = args["action"]

    if action == "status":
        lines = []
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy"):
            val = os.environ.get(var, "")
            if val:
                lines.append(f"  {var}={val}")
        if PROXY_ENV.exists():
            lines.append(f"\n~/.proxy_env contents:\n{PROXY_ENV.read_text().strip()}")
        return "Proxy status:\n" + ("\n".join(lines) if lines else "  No proxy set in environment.")

    if not PROXY_TOGGLE.exists():
        return f"proxy-toggle.sh not found at {PROXY_TOGGLE}. Create it first."

    if action == "on":
        out = _run(f'bash "{PROXY_TOGGLE}" on')
        return f"Proxy enabled.\n{out}"
    elif action == "off":
        out = _run(f'bash "{PROXY_TOGGLE}" off')
        return f"Proxy disabled.\n{out}"

    return "Unknown action."


def _network_audit(args: dict) -> str:
    mode = args.get("mode", "all")
    sections: list[str] = []

    if mode in ("all", "ports"):
        ports = _run("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null | head -40")
        sections.append(f"=== Listening Ports ===\n{ports}")

    if mode in ("all", "connections"):
        conns = _run("ss -tnp state established 2>/dev/null | head -40")
        sections.append(f"=== Active Connections ===\n{conns}")

    if mode in ("all", "dns"):
        resolvconf = _run("cat /etc/resolv.conf 2>/dev/null | grep nameserver")
        systemd_dns = _run("resolvectl status 2>/dev/null | grep 'DNS Servers' | head -5")
        sections.append(f"=== DNS Servers ===\n/etc/resolv.conf:\n{resolvconf}\nresolvectl:\n{systemd_dns}")

    if mode in ("all", "firewall"):
        if _which("ufw"):
            fw = _run("sudo ufw status numbered 2>/dev/null || ufw status 2>/dev/null")
        elif _which("firewall-cmd"):
            fw = _run("firewall-cmd --list-all 2>/dev/null")
        else:
            fw = _run("sudo iptables -L -n --line-numbers 2>/dev/null | head -50")
        sections.append(f"=== Firewall ===\n{fw}")

    return "\n\n".join(sections)


def _browser_clean(args: dict) -> str:
    browser = args.get("browser", "all")
    what = args.get("what", "cache")
    home = Path.home()
    results: list[str] = []

    def _clean_dir(label: str, path: Path) -> str:
        if not path.exists():
            return f"  {label}: not found ({path})"
        before = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        try:
            import shutil
            shutil.rmtree(str(path))
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return f"  {label}: error — {e}"
        freed = before
        return f"  {label}: freed {freed / 1024 / 1024:.1f} MB"

    def _clean_browser(name: str, cache_paths: list[Path], cookie_paths: list[Path]) -> list[str]:
        res = [f"\n{name}:"]
        if what in ("all", "cache"):
            for p in cache_paths:
                res.append(_clean_dir("cache", p))
        if what in ("all", "cookies"):
            for p in cookie_paths:
                # Cookies are a SQLite file, truncate it rather than delete
                if p.exists() and p.is_file():
                    before = p.stat().st_size
                    try:
                        p.write_bytes(b"")
                    except Exception as e:
                        res.append(f"  cookies: error — {e}")
                        continue
                    res.append(f"  cookies: freed {before / 1024:.0f} KB ({p.name})")
                else:
                    res.append(f"  cookies: not found ({p})")
        return res

    if browser in ("all", "chrome"):
        base = home / ".config" / "google-chrome" / "Default"
        results.extend(_clean_browser(
            "Google Chrome",
            [base / "Cache", base / "Code Cache"],
            [base / "Cookies"],
        ))

    if browser in ("all", "firefox"):
        ff_base = home / ".mozilla" / "firefox"
        if ff_base.exists():
            profiles = [d for d in ff_base.iterdir() if d.is_dir() and "default" in d.name.lower()]
            if not profiles:
                profiles = [d for d in ff_base.iterdir() if d.is_dir()]
            for p in profiles[:2]:
                results.extend(_clean_browser(
                    f"Firefox ({p.name})",
                    [p / "cache2", p / "startupCache"],
                    [p / "cookies.sqlite"],
                ))
        else:
            results.append("\nFirefox: profile directory not found")

    if browser in ("all", "librewolf"):
        lw_base = home / ".librewolf"
        if lw_base.exists():
            profiles = [d for d in lw_base.iterdir() if d.is_dir() and "default" in d.name.lower()]
            if not profiles:
                profiles = [d for d in lw_base.iterdir() if d.is_dir()]
            for p in profiles[:2]:
                results.extend(_clean_browser(
                    f"Librewolf ({p.name})",
                    [p / "cache2", p / "startupCache"],
                    [p / "cookies.sqlite"],
                ))
        else:
            results.append("\nLibrewolf: profile directory not found")

    return "Browser cleanup results:\n" + "\n".join(results) if results else "Nothing to clean."


def _privacy_check(args: dict) -> str:
    check = args.get("check", "all")
    sections: list[str] = []

    if check in ("all", "dns"):
        # Check DNS via external resolver to detect leaks
        normal = _run("dig +short myip.opendns.com @resolver1.opendns.com 2>/dev/null || echo 'unavailable'")
        dns_leak = _run("dig +short whoami.akamai.net @ns1-1.akamaitech.net 2>/dev/null || echo 'unavailable'")
        local_dns = _run("cat /etc/resolv.conf | grep nameserver | head -5")
        sections.append(
            f"=== DNS Check ===\n"
            f"Your IP via OpenDNS:  {normal}\n"
            f"Your IP via Akamai:   {dns_leak}\n"
            f"Local nameservers:\n{local_dns}"
        )

    if check in ("all", "ip"):
        ipv4 = _run("curl -s --max-time 5 https://api.ipify.org || echo 'unavailable'")
        ipv6 = _run("curl -s --max-time 5 https://api6.ipify.org || echo 'unavailable'")
        geo = _run("curl -s --max-time 5 'https://ipapi.co/json/' | python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'Country: {d.get(\\\"country_name\\\",\\\"?\\\")}  City: {d.get(\\\"city\\\",\\\"?\\\")}  ISP: {d.get(\\\"org\\\",\\\"?\\\")}')\" 2>/dev/null || echo 'geo lookup unavailable'")
        sections.append(
            f"=== IP Check ===\n"
            f"Public IPv4: {ipv4}\n"
            f"Public IPv6: {ipv6}\n"
            f"{geo}"
        )

    if check in ("all", "processes"):
        # Check for suspicious listening processes
        listeners = _run("ss -tlnp 2>/dev/null | tail -n +2")
        suspicious_keywords = ["telemetry", "tracker", "spy", "monitor", "keylog"]
        proc_list = _run("ps aux --no-headers | awk '{print $11}' | sort -u")
        flagged = [p for p in proc_list.splitlines() if any(kw in p.lower() for kw in suspicious_keywords)]

        sections.append(
            f"=== Process Check ===\n"
            f"Listening ports:\n{listeners}\n\n"
            f"Flagged process names ({len(flagged)}):\n" +
            ("\n".join(f"  {p}" for p in flagged) if flagged else "  None detected.")
        )

    return "\n\n".join(sections)


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
