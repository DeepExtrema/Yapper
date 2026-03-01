"""Tests for injector method selection logic."""

from unittest.mock import patch

from yapper.config import InjectorConfig
from yapper.context import WindowContext
from yapper.injector import Injector


def _make_injector(has_wtype=True, has_ydotool=True, has_wl_copy=True, has_xdotool=False, has_xclip=False, **kwargs):
    config = InjectorConfig(**kwargs)
    with patch("yapper.injector.shutil.which") as mock_which:
        def side_effect(tool):
            return {
                "wtype": "/usr/bin/wtype" if has_wtype else None,
                "ydotool": "/usr/bin/ydotool" if has_ydotool else None,
                "xdotool": "/usr/bin/xdotool" if has_xdotool else None,
                "wl-copy": "/usr/bin/wl-copy" if has_wl_copy else None,
                "xclip": "/usr/bin/xclip" if has_xclip else None,
            }.get(tool)
        mock_which.side_effect = side_effect
        return Injector(config)


def test_pick_wtype_for_wayland():
    inj = _make_injector(has_wtype=True)
    ctx = WindowContext(is_xwayland=False)
    assert inj._pick_method("hello", ctx) == "wtype"


def test_pick_ydotool_for_xwayland():
    inj = _make_injector(has_wtype=True, has_ydotool=True)
    ctx = WindowContext(is_xwayland=True)
    assert inj._pick_method("hello", ctx) == "ydotool"


def test_pick_clipboard_for_xwayland_no_ydotool():
    inj = _make_injector(has_wtype=True, has_ydotool=False)
    ctx = WindowContext(is_xwayland=True)
    assert inj._pick_method("hello", ctx) == "clipboard"


def test_pick_clipboard_for_long_text():
    inj = _make_injector(has_wtype=True, clipboard_threshold=10)
    ctx = WindowContext(is_xwayland=False)
    assert inj._pick_method("a" * 20, ctx) == "clipboard"


def test_pick_clipboard_when_nothing_available():
    inj = _make_injector(has_wtype=False, has_ydotool=False)
    ctx = WindowContext(is_xwayland=False)
    assert inj._pick_method("hello", ctx) == "clipboard"


def test_pick_ydotool_fallback_no_wtype():
    inj = _make_injector(has_wtype=False, has_ydotool=True)
    ctx = WindowContext(is_xwayland=False)
    assert inj._pick_method("hello", ctx) == "ydotool"


def test_pick_xdotool_for_x11():
    """When no wtype/ydotool but has xdotool, picks xdotool for XWayland."""
    inj = _make_injector(has_wtype=False, has_ydotool=False, has_xdotool=True)
    ctx = WindowContext(is_xwayland=True)
    assert inj._pick_method("hello", ctx) == "xdotool"


def test_pick_xdotool_fallback_wayland():
    """When no wtype/ydotool but has xdotool on Wayland, picks xdotool."""
    inj = _make_injector(has_wtype=False, has_ydotool=False, has_xdotool=True)
    ctx = WindowContext(is_xwayland=False)
    assert inj._pick_method("hello", ctx) == "xdotool"
