"""Desktop notifications via notify-send."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yapper.config import NotificationConfig

log = logging.getLogger(__name__)


class Notifier:
    """Send desktop notifications via notify-send."""

    def __init__(self, config: NotificationConfig) -> None:
        self._config = config

    async def send(
        self,
        summary: str,
        body: str = "",
        urgency: str = "normal",
        replace_id: str = "yapper",
    ) -> None:
        if not self._config.enabled:
            return

        cmd = [
            "notify-send",
            "--app-name=Yapper",
            f"--expire-time={self._config.timeout}",
            f"--urgency={urgency}",
            f"--hint=string:x-canonical-private-synchronous:{replace_id}",
            "--",
            summary,
        ]
        if body:
            cmd.append(body)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            if proc.returncode != 0:
                log.warning("notify-send failed: %s", stderr.decode().strip())
        except (asyncio.TimeoutError, FileNotFoundError) as e:
            log.debug("Notification failed: %s", e)

    async def recording_started(self) -> None:
        await self.send("Recording...", urgency="low")

    async def recording_stopped(self) -> None:
        await self.send("Processing...", urgency="low")

    async def text_injected(self, text: str) -> None:
        preview = text[:80] + ("..." if len(text) > 80 else "")
        await self.send("Dictation complete", f"{preview}\n(Text also on clipboard — Ctrl+V to paste)")

    async def streaming_started(self) -> None:
        await self.send("Listening...", urgency="low")

    async def dictation_ended(self) -> None:
        await self.send("Dictation ended", urgency="low")

    async def error(self, message: str) -> None:
        await self.send("Yapper Error", message, urgency="critical")
