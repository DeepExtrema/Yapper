"""CLI client that sends commands to the Yapper daemon via Unix socket."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _socket_path(override: str | None = None) -> Path:
    if override:
        return Path(override)
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return Path(runtime_dir) / "yapper.sock"


async def _send_command(command: str, socket_override: str | None = None) -> str:
    sock = _socket_path(socket_override)
    if not sock.exists():
        print(f"Error: Yapper daemon not running (no socket at {sock})", file=sys.stderr)
        sys.exit(1)

    try:
        reader, writer = await asyncio.open_unix_connection(str(sock))
        writer.write(command.encode())
        await writer.drain()
        writer.write_eof()

        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        writer.close()
        await writer.wait_closed()
        return response.decode()
    except ConnectionRefusedError:
        print("Error: Yapper daemon not responding", file=sys.stderr)
        sys.exit(1)
    except asyncio.TimeoutError:
        print("Error: Timed out waiting for response", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = sys.argv[1:]
    socket_override = None

    # Parse --socket flag
    if "--socket" in args:
        idx = args.index("--socket")
        if idx + 1 >= len(args):
            print("Error: --socket requires a path argument", file=sys.stderr)
            sys.exit(1)
        socket_override = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    # Also check YAPPER_SOCKET env var
    if socket_override is None:
        socket_override = os.environ.get("YAPPER_SOCKET")

    if not args:
        print("Usage: yapper-ctl [--socket PATH] <command>", file=sys.stderr)
        print("Commands: start, stop, toggle, status, quit", file=sys.stderr)
        sys.exit(1)

    command = args[0].lower()
    if command not in ("start", "stop", "toggle", "status", "quit"):
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)

    response = asyncio.run(_send_command(command, socket_override))
    print(response)


if __name__ == "__main__":
    main()
