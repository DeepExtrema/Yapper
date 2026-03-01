"""Tests for context window mode detection."""

from yapper.context import _APP_MODES, WindowContext


def test_exact_match_code_editors():
    for app in ("code", "codium", "neovim", "nvim", "vim", "emacs"):
        assert _APP_MODES.get(app) == "code", f"Expected 'code' for {app}"


def test_exact_match_chat():
    for app in ("discord", "telegram", "signal", "slack", "element"):
        assert _APP_MODES.get(app) == "chat", f"Expected 'chat' for {app}"


def test_exact_match_terminals():
    for app in ("kitty", "alacritty", "foot", "wezterm"):
        assert _APP_MODES.get(app) == "terminal", f"Expected 'terminal' for {app}"


def test_exact_match_email():
    for app in ("thunderbird", "evolution", "geary"):
        assert _APP_MODES.get(app) == "email", f"Expected 'email' for {app}"


def test_default_mode_is_prose():
    ctx = WindowContext()
    assert ctx.mode == "prose"


def test_unknown_app_not_in_modes():
    assert "my-random-app" not in _APP_MODES
