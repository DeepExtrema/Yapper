"""Tests for context window mode detection."""

from yapper.context import _APP_MODES, WindowContext, resolve_mode


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
