"""Tests for the Dictionary class."""

import tempfile
from pathlib import Path

from yapper.dictionary import Dictionary


def test_disabled_dictionary_returns_original():
    d = Dictionary(enabled=False)
    assert d.apply("hello world") == "hello world"


def test_word_boundary_matching():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("he -> she\n")
        f.flush()
        d = Dictionary(path=f.name, enabled=True)

    assert d.apply("he said hello") == "she said hello"
    assert d.apply("the help") == "the help"  # must NOT match inside words


def test_multiple_substitutions():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("teh -> the\nrecieve -> receive\n")
        f.flush()
        d = Dictionary(path=f.name, enabled=True)

    assert d.apply("teh recieve") == "the receive"


def test_comments_and_blank_lines_ignored():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("# comment\n\nfoo -> bar\n")
        f.flush()
        d = Dictionary(path=f.name, enabled=True)

    assert d.apply("foo baz") == "bar baz"
    assert len(d._subs) == 1


def test_missing_file_no_error():
    d = Dictionary(path="/tmp/nonexistent_yapper_dict.txt", enabled=True)
    assert d.apply("hello") == "hello"
    assert len(d._subs) == 0
