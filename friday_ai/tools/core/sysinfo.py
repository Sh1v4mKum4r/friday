"""System information tool (works on any Linux DE)."""

import os
import subprocess

name = "sysinfo"
description = (
    "Get system information. Modes: 'all' for full summary, "
    "'cpu' for CPU temp/usage, 'ram' for memory, 'disk' for storage, "
    "'battery' for battery status, 'gpu' for GPU info, 'network' for IP/connection."
)


def _read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return ""


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _cpu_info() -> str:
    # Temperature
    temp = ""
    thermal_zones = sorted(
        [f"/sys/class/thermal/{z}/temp" for z in os.listdir("/sys/class/thermal/")
         if z.startswith("thermal_zone")]
    ) if os.path.exists("/sys/class/thermal") else []
    for zone in thermal_zones:
        val = _read_file(zone)
        if val:
            try:
                temp = f"{int(val) / 1000:.1f}°C"
                break
            except ValueError:
                pass

    # Load average
    load = _read_file("/proc/loadavg").split()[:3]
    load_str = " ".join(load) if load else "unknown"

    # CPU model
    model = ""
    for line in _read_file("/proc/cpuinfo").splitlines():
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
            break

    parts = [f"CPU: {model}"] if model else []
    if temp:
        parts.append(f"Temp: {temp}")
    parts.append(f"Load: {load_str}")
    return "\n".join(parts)


def _ram_info() -> str:
    output = _run(["free", "-h"])
    if not output:
        return "Could not read memory info."
    lines = output.splitlines()
    if len(lines) >= 2:
        mem = lines[1].split()
        if len(mem) >= 4:
            return f"RAM: {mem[2]} used / {mem[1]} total ({mem[3]} free)"
    return output


def _disk_info() -> str:
    output = _run(["df", "-h", "/", "/home"])
    if not output:
        return "Could not read disk info."
    lines = output.splitlines()
    result = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6:
            result.append(f"{parts[5]}: {parts[2]} used / {parts[1]} ({parts[4]})")
    return "\n".join(result) if result else output


def _battery_info() -> str:
    bat_path = "/sys/class/power_supply/BAT0"
    if not os.path.exists(bat_path):
        bat_path = "/sys/class/power_supply/BAT1"
    if not os.path.exists(bat_path):
        return "No battery found."

    capacity = _read_file(f"{bat_path}/capacity")
    status = _read_file(f"{bat_path}/status")
    return f"Battery: {capacity}% ({status})"


def _gpu_info() -> str:
    nvidia = _run(["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits"])
    if nvidia:
        parts = [p.strip() for p in nvidia.split(",")]
        if len(parts) >= 4:
            return f"GPU: {parts[0]} | Temp: {parts[1]}°C | VRAM: {parts[2]}MB / {parts[3]}MB"
        return f"GPU: {nvidia}"
    return "No NVIDIA GPU detected (or nvidia-smi not installed)."


def _network_info() -> str:
    # Get IP
    ip = _run(["hostname", "-I"])
    ip = ip.split()[0] if ip else "unknown"

    # Get connection info
    wifi = _run(["iwctl", "station", "wlan0", "show"])
    ssid = ""
    for line in wifi.splitlines():
        if "Connected network" in line:
            ssid = line.split()[-1]
            break

    parts = [f"IP: {ip}"]
    if ssid:
        parts.append(f"WiFi: {ssid}")
    return "\n".join(parts)


def _bluetooth_info() -> str:
    try:
        result = subprocess.run(["rfkill", "list", "bluetooth"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            if "Soft blocked: yes" in result.stdout:
                return "Bluetooth: OFF (blocked)"
            return "Bluetooth: ON"
        return "Bluetooth: unknown"
    except Exception:
        return "Bluetooth: unknown"


def run(mode: str = "all") -> str:
    """Get system information.

    Parameters
    ----------
    mode:
        'all', 'cpu', 'ram', 'disk', 'battery', 'gpu', 'network', 'bluetooth'
    """
    lower = mode.strip().lower()

    sections = {
        "cpu": _cpu_info,
        "ram": _ram_info,
        "disk": _disk_info,
        "battery": _battery_info,
        "gpu": _gpu_info,
        "network": _network_info,
        "bluetooth": _bluetooth_info,
    }

    if lower == "all":
        parts = []
        for name, fn in sections.items():
            parts.append(fn())
        return "\n\n".join(parts)

    if lower in sections:
        return sections[lower]()

    return f"Unknown mode: {mode}. Options: all, cpu, ram, disk, battery, gpu, network"
