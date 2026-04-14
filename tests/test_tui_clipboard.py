"""Tests for clipboard utility."""

from unittest.mock import AsyncMock, patch

import pytest

from friday_ai.tui.utils.clipboard import copy_to_clipboard, detect_clipboard_cmd


class TestClipboard:
    def test_detect_wayland(self):
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            with patch("shutil.which", return_value="/usr/bin/wl-copy"):
                cmd = detect_clipboard_cmd()
                assert cmd == ["wl-copy"]

    def test_detect_x11(self):
        env = {"DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=True):
            with patch("shutil.which", side_effect=lambda x: "/usr/bin/xclip" if x == "xclip" else None):
                cmd = detect_clipboard_cmd()
                assert cmd == ["xclip", "-selection", "clipboard"]

    def test_detect_xsel_fallback(self):
        env = {"DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=True):
            with patch("shutil.which", side_effect=lambda x: "/usr/bin/xsel" if x == "xsel" else None):
                cmd = detect_clipboard_cmd()
                assert cmd == ["xsel", "--clipboard", "--input"]

    def test_detect_none(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value=None):
                cmd = detect_clipboard_cmd()
                assert cmd is None

    @pytest.mark.asyncio
    async def test_copy_success(self):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("friday_ai.tui.utils.clipboard.detect_clipboard_cmd", return_value=["wl-copy"]):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
                result = await copy_to_clipboard("hello world")
                assert result is True
                mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_copy_no_clipboard_tool(self):
        with patch("friday_ai.tui.utils.clipboard.detect_clipboard_cmd", return_value=None):
            result = await copy_to_clipboard("hello")
            assert result is False
