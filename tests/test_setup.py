"""Tests for setup wizard helpers."""

from yapper.setup import _bold, _green, _red, _yellow, _cyan, _dim


def test_ansi_helpers():
    assert "\033[1m" in _bold("test")
    assert "\033[32m" in _green("test")
    assert "\033[31m" in _red("test")
    assert "\033[33m" in _yellow("test")
    assert "\033[36m" in _cyan("test")
    assert "\033[2m" in _dim("test")


def test_bold_contains_text():
    assert "hello" in _bold("hello")


def test_green_contains_text():
    assert "world" in _green("world")


def test_reset_suffix():
    for fn in (_bold, _green, _red, _yellow, _cyan, _dim):
        assert fn("x").endswith("\033[0m")
