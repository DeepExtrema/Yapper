"""Tests for context window mode detection."""

import asyncio
from unittest.mock import AsyncMock, patch

from yapper.context import (
    _APP_MODES,
    WindowContext,
    _get_window_hyprland,
    _get_window_x11,
    get_active_window,
    resolve_mode,
)


def test_exact_match_code_editors():
    for app in ("code", "codium", "neovim", "nvim", "vim", "emacs"):
        assert resolve_mode(app) == "code", f"Expected 'code' for {app}"


def test_exact_match_chat():
    for app in ("discord", "telegram", "signal", "slack", "element"):
        assert resolve_mode(app) == "chat", f"Expected 'chat' for {app}"


def test_exact_match_terminals():
    for app in ("kitty", "alacritty", "foot", "wezterm"):
        assert resolve_mode(app) == "terminal", f"Expected 'terminal' for {app}"


def test_exact_match_email():
    for app in ("thunderbird", "evolution", "geary"):
        assert resolve_mode(app) == "email", f"Expected 'email' for {app}"


def test_substring_fallback():
    assert resolve_mode("jetbrains-idea") == "code"
    assert resolve_mode("org.telegram.desktop") == "chat"


def test_exact_match_takes_priority():
    # "code" should match exactly to "code", not substring into something else
    assert resolve_mode("code") == "code"


def test_unknown_app_defaults_to_prose():
    assert resolve_mode("my-random-app") == "prose"
    assert resolve_mode("") == "prose"


def test_default_window_context_mode():
    ctx = WindowContext()
    assert ctx.mode == "prose"


def test_x11_fallback_xdotool():
    """When Hyprland backend fails, X11 backend should be used."""

    async def _run():
        with (
            patch(
                "yapper.context._get_window_hyprland",
                new_callable=AsyncMock,
                side_effect=FileNotFoundError("hyprctl not found"),
            ),
            patch(
                "yapper.context._get_window_x11",
                new_callable=AsyncMock,
                return_value=("firefox", "Mozilla Firefox", True),
            ),
        ):
            ctx = await get_active_window()
            assert ctx.app_class == "firefox"
            assert ctx.title == "Mozilla Firefox"
            assert ctx.is_xwayland is True
            assert ctx.mode == "prose"

    asyncio.run(_run())


def test_fallback_returns_default():
    """When all backends fail, a default WindowContext is returned."""

    async def _run():
        with (
            patch(
                "yapper.context._get_window_hyprland",
                new_callable=AsyncMock,
                side_effect=FileNotFoundError("hyprctl not found"),
            ),
            patch(
                "yapper.context._get_window_x11",
                new_callable=AsyncMock,
                side_effect=FileNotFoundError("xdotool not found"),
            ),
        ):
            ctx = await get_active_window()
            assert ctx.app_class == ""
            assert ctx.title == ""
            assert ctx.is_xwayland is False
            assert ctx.mode == "prose"

    asyncio.run(_run())
