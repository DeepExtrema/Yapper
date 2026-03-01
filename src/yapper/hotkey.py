"""Unix socket server for receiving commands from yapper-ctl."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable

log = logging.getLogger(__name__)

CommandHandler = Callable[[str], Awaitable[str]]


class HotkeyServer:
    """Async Unix socket server that accepts commands."""

    def __init__(self, socket_path: Path, handler: CommandHandler) -> None:
        self._socket_path = socket_path
        self._handler = handler
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        # Clean up stale socket
        self._socket_path.unlink(missing_ok=True)
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)

        self._server = await asyncio.start_unix_server(
            self._client_handler,
            path=str(self._socket_path),
        )
        # Make socket accessible
        self._socket_path.chmod(0o600)
        log.info("Listening on %s", self._socket_path)

    async def _client_handler(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            if not data:
                return

            command = data.decode().strip()
            log.debug("Received command: %s", command)

            response = await self._handler(command)
            writer.write(response.encode())
            await writer.drain()
        except asyncio.TimeoutError:
            log.warning("Client read timed out")
        except Exception:
            log.exception("Error handling client")
        finally:
            writer.close()
            await writer.wait_closed()

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self._socket_path.unlink(missing_ok=True)
        log.info("Socket server stopped")
