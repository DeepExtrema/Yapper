"""Active window detection with multiple desktop backends."""

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


def resolve_mode(app_class: str) -> str:
    """Resolve dictation mode from app class (exact match first, then substring)."""
    mode = _APP_MODES.get(app_class, "")
    if mode:
        return mode
    for pattern, m in _APP_MODES.items():
        if pattern in app_class:
            return m
    return "prose"


async def _get_window_hyprland() -> tuple[str, str, bool]:
    """Detect active window via hyprctl (Hyprland).

    Returns:
        (app_class, title, is_xwayland)

    Raises:
        FileNotFoundError: hyprctl not found.
        TimeoutError: hyprctl took too long.
        json.JSONDecodeError: bad JSON output.
        RuntimeError: non-zero exit code.
    """
    proc = await asyncio.create_subprocess_exec(
        "hyprctl", "activewindow", "-j",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=2.0)

    if proc.returncode != 0:
        raise RuntimeError(f"hyprctl failed: {stderr.decode().strip()}")

    data = json.loads(stdout)
    app_class = data.get("class", "").lower()
    title = data.get("title", "")
    is_xwayland = data.get("xwayland", False)
    return app_class, title, is_xwayland


async def _get_window_x11() -> tuple[str, str, bool]:
    """Detect active window via xdotool (X11).

    Returns:
        (app_class, title, True) -- X11 windows are treated like XWayland.

    Raises:
        FileNotFoundError: xdotool not found.
        TimeoutError: xdotool took too long.
        RuntimeError: non-zero exit code.
    """
    class_proc = await asyncio.create_subprocess_exec(
        "xdotool", "getactivewindow", "getwindowclassname",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    class_out, class_err = await asyncio.wait_for(
        class_proc.communicate(), timeout=2.0,
    )
    if class_proc.returncode != 0:
        raise RuntimeError(
            f"xdotool class failed: {class_err.decode().strip()}"
        )

    title_proc = await asyncio.create_subprocess_exec(
        "xdotool", "getactivewindow", "getwindowname",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    title_out, title_err = await asyncio.wait_for(
        title_proc.communicate(), timeout=2.0,
    )
    if title_proc.returncode != 0:
        raise RuntimeError(
            f"xdotool title failed: {title_err.decode().strip()}"
        )

    app_class = class_out.decode().strip().lower()
    title = title_out.decode().strip()
    return app_class, title, True


async def get_active_window() -> WindowContext:
    """Get the currently focused window info.

    Tries backends in order: Hyprland, then X11.
    Returns a default WindowContext if all backends fail.
    """
    backends = [_get_window_hyprland, _get_window_x11]

    for backend in backends:
        try:
            app_class, title, is_xwayland = await backend()
            mode = resolve_mode(app_class)
            ctx = WindowContext(
                app_class=app_class,
                title=title,
                is_xwayland=is_xwayland,
                mode=mode,
            )
            log.debug("Window context (%s): %s", backend.__name__, ctx)
            return ctx
        except (
            asyncio.TimeoutError,
            FileNotFoundError,
            json.JSONDecodeError,
            RuntimeError,
        ) as e:
            log.debug("Backend %s failed: %s", backend.__name__, e)

    log.warning("All window detection backends failed, using defaults")
    return WindowContext()
