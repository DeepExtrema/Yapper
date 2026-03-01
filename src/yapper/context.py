"""Active window detection via hyprctl."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Map app class to dictation mode
_APP_MODES: dict[str, str] = {
    # Code editors
    "code": "code",
    "code-url-handler": "code",
    "codium": "code",
    "neovim": "code",
    "nvim": "code",
    "vim": "code",
    "emacs": "code",
    "jetbrains": "code",
    # Chat / messaging
    "discord": "chat",
    "telegram": "chat",
    "signal": "chat",
    "slack": "chat",
    "element": "chat",
    # Email
    "thunderbird": "email",
    "evolution": "email",
    "geary": "email",
    # Browsers — default to prose
    "firefox": "prose",
    "chromium": "prose",
    "brave-browser": "prose",
    "google-chrome": "prose",
    # Terminal
    "kitty": "terminal",
    "alacritty": "terminal",
    "foot": "terminal",
    "wezterm": "terminal",
}


@dataclass
class WindowContext:
    app_class: str = ""
    title: str = ""
    is_xwayland: bool = False
    mode: str = "prose"  # default mode


async def get_active_window() -> WindowContext:
    """Get the currently focused window info from Hyprland."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "hyprctl", "activewindow", "-j",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=2.0)

        if proc.returncode != 0:
            log.warning("hyprctl failed: %s", stderr.decode().strip())
            return WindowContext()

        data = json.loads(stdout)
        app_class = data.get("class", "").lower()
        title = data.get("title", "")
        is_xwayland = data.get("xwayland", False)

        # Determine mode from app class
        mode = "prose"
        for pattern, m in _APP_MODES.items():
            if pattern in app_class:
                mode = m
                break

        ctx = WindowContext(
            app_class=app_class,
            title=title,
            is_xwayland=is_xwayland,
            mode=mode,
        )
        log.debug("Window context: %s", ctx)
        return ctx

    except (asyncio.TimeoutError, FileNotFoundError, json.JSONDecodeError) as e:
        log.warning("Failed to detect active window: %s", e)
        return WindowContext()
