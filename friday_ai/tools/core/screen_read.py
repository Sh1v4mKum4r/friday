"""Screen reading tool — OCR + screenshot for identifying on-screen content.

Takes a screenshot (full or region), runs OCR to extract text, and returns
what's visible on screen. Works on any Wayland compositor.

Requires: grim, slurp (already installed), tesseract (for OCR)
Install OCR: sudo pacman -S tesseract tesseract-data-eng
"""

import subprocess
import tempfile
import os

name = "screen_read"
description = (
    "Read text from the screen using OCR. Modes: "
    "'all' to read entire screen, "
    "'region' to select an area to read, "
    "'at <x> <y> <w> <h>' to read a specific rectangle. "
    "Returns the text found on screen."
)


def run(mode: str = "all") -> str:
    """Read text from the screen.

    Parameters
    ----------
    mode:
        'all' — OCR the entire screen
        'region' — let user select a region with mouse, then OCR it
        'at <x> <y> <width> <height>' — OCR a specific rectangle
    """
    parts = mode.strip().split()
    cmd = parts[0].lower() if parts else "all"

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        screenshot_path = tmp.name

    try:
        # Take the screenshot
        if cmd == "all":
            result = subprocess.run(
                ["grim", screenshot_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return f"Screenshot error: {result.stderr.strip()}"

        elif cmd == "region":
            # Let user select region
            region = subprocess.run(
                ["slurp"], capture_output=True, text=True, timeout=30,
            )
            if region.returncode != 0:
                return "Cancelled."
            geometry = region.stdout.strip()
            result = subprocess.run(
                ["grim", "-g", geometry, screenshot_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return f"Screenshot error: {result.stderr.strip()}"

        elif cmd == "at" and len(parts) >= 5:
            x, y, w, h = parts[1], parts[2], parts[3], parts[4]
            geometry = f"{x},{y} {w}x{h}"
            result = subprocess.run(
                ["grim", "-g", geometry, screenshot_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return f"Screenshot error: {result.stderr.strip()}"

        else:
            return "Usage: all, region, at <x> <y> <width> <height>"

        # Run OCR on the screenshot
        return _ocr(screenshot_path)

    except FileNotFoundError as e:
        return f"Error: required tool not found — {e}. Need grim, slurp, tesseract."
    except subprocess.TimeoutExpired:
        return "Error: timed out (did you forget to select a region?)"
    finally:
        # Clean up temp file
        if os.path.exists(screenshot_path):
            os.unlink(screenshot_path)


def _ocr(image_path: str) -> str:
    """Run tesseract OCR on an image file and return extracted text."""
    try:
        result = subprocess.run(
            ["tesseract", image_path, "stdout", "--psm", "3"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"OCR error: {result.stderr.strip()}"

        text = result.stdout.strip()
        if not text:
            return "No text detected on screen."

        # Clean up common OCR artifacts
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

        if len(cleaned) > 5000:
            cleaned = cleaned[:5000] + "\n... (truncated)"

        return cleaned

    except FileNotFoundError:
        return (
            "Error: tesseract not found. Install: sudo pacman -S tesseract tesseract-data-eng"
        )
