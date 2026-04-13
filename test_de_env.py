import os
import subprocess
from friday_ai.tools.core import de

def test_env():
    env = de._wayland_env()
    print(f"Detected DE: {de._detect_de()}")
    print(f"WAYLAND_DISPLAY: {env.get('WAYLAND_DISPLAY')}")
    print(f"XDG_RUNTIME_DIR: {env.get('XDG_RUNTIME_DIR')}")
    print(f"HYPRLAND_INSTANCE_SIGNATURE: {env.get('HYPRLAND_INSTANCE_SIGNATURE')}")

if __name__ == "__main__":
    test_env()
