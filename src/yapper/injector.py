"""Text injection into the focused application."""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yapper.config import InjectorConfig
    from yapper.context import WindowContext

log = logging.getLogger(__name__)


class Injector:
    """Inject text into the focused window using wtype, ydotool, xdotool, or clipboard."""

    def __init__(self, config: InjectorConfig) -> None:
        self._config = config
        self._has_wtype = shutil.which("wtype") is not None
        self._has_ydotool = shutil.which("ydotool") is not None
        self._has_xdotool = shutil.which("xdotool") is not None
        self._has_wl_copy = shutil.which("wl-copy") is not None
        self._has_xclip = shutil.which("xclip") is not None
        log.info(
            "Injection tools: wtype=%s ydotool=%s xdotool=%s wl-copy=%s xclip=%s",
            self._has_wtype, self._has_ydotool, self._has_xdotool,
            self._has_wl_copy, self._has_xclip,
        )

    async def inject(self, text: str, context: WindowContext) -> None:
        """Inject text into the focused application."""
        if not text:
            return

        method = self._config.method
        if method == "auto":
            method = self._pick_method(text, context)

        log.info("Injecting %d chars via %s", len(text), method)

        # Always copy to clipboard as a fallback so text isn't lost
        await self._copy_to_clipboard(text)

        if method == "clipboard":
            await self._inject_clipboard(text, context)
        elif method == "ydotool":
            ok = await self._inject_ydotool(text)
            if not ok:
                log.warning("ydotool failed, falling back to clipboard paste")
                await self._inject_clipboard(text, context)
        elif method == "xdotool":
            ok = await self._inject_xdotool(text)
            if not ok:
                log.warning("xdotool failed, falling back to clipboard paste")
                await self._inject_clipboard(text, context)
        else:
            ok = await self._inject_wtype(text)
            if not ok:
                log.warning("wtype failed, falling back to clipboard paste")
                await self._inject_clipboard(text, context)

    def _pick_method(self, text: str, context: WindowContext) -> str:
        if context.is_xwayland:
            if self._has_ydotool:
                return "ydotool"
            if self._has_xdotool:
                return "xdotool"
            return "clipboard"
        if len(text) > self._config.clipboard_threshold:
            return "clipboard"
        if self._has_wtype:
            return "wtype"
        if self._has_ydotool:
            return "ydotool"
        if self._has_xdotool:
            return "xdotool"
        return "clipboard"

    async def _inject_wtype(self, text: str) -> bool:
        cmd = ["wtype", "--"]
        if self._config.typing_delay > 0:
            cmd = ["wtype", "-d", str(self._config.typing_delay), "--"]
        cmd.append(text)
        return await self._run(cmd)

    async def _inject_ydotool(self, text: str) -> bool:
        return await self._run(["ydotool", "type", "--", text])

    async def _inject_xdotool(self, text: str) -> bool:
        return await self._run(["xdotool", "type", "--clearmodifiers", "--", text])

    async def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard (used as fallback for all methods)."""
        if self._has_wl_copy:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "wl-copy", "--", text,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=2.0)
                return
            except (asyncio.TimeoutError, FileNotFoundError) as e:
                log.warning("Failed to copy to clipboard via wl-copy: %s", e)
        if self._has_xclip:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "xclip", "-selection", "clipboard",
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(input=text.encode()), timeout=2.0)
                return
            except (asyncio.TimeoutError, FileNotFoundError) as e:
                log.warning("Failed to copy to clipboard via xclip: %s", e)
        log.warning("No clipboard tool found (wl-copy or xclip), cannot copy to clipboard")

    async def _inject_clipboard(self, text: str, context: WindowContext) -> None:
        await asyncio.sleep(self._config.clipboard_paste_delay)

        if context.is_xwayland or not self._has_wtype:
            if self._has_ydotool:
                await self._run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])
            elif self._has_xdotool:
                await self._run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
            else:
                log.warning("No tool available to paste from clipboard")
        else:
            await self._run(["wtype", "-M", "ctrl", "-P", "v", "-p", "v", "-m", "ctrl"])

    async def _run(self, cmd: list[str]) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode != 0:
                log.error("%s failed (rc=%d): %s", cmd[0], proc.returncode, stderr.decode().strip())
                return False
            return True
        except FileNotFoundError:
            log.error("%s not found in PATH", cmd[0])
            return False
        except asyncio.TimeoutError:
            log.error("%s timed out", cmd[0])
            return False
