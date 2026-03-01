"""Tests for the Dictionary class."""

from yapper.dictionary import Dictionary


def test_disabled_dictionary_returns_original():
    d = Dictionary(enabled=False)
    assert d.apply("hello world") == "hello world"


def test_word_boundary_matching(tmp_path):
    p = tmp_path / "dict.txt"
    p.write_text("he -> she\n")
    d = Dictionary(path=str(p), enabled=True)

    assert d.apply("he said hello") == "she said hello"
    assert d.apply("the help") == "the help"  # must NOT match inside words


def test_multiple_substitutions(tmp_path):
    p = tmp_path / "dict.txt"
    p.write_text("teh -> the\nrecieve -> receive\n")
    d = Dictionary(path=str(p), enabled=True)

    assert d.apply("teh recieve") == "the receive"


def test_comments_and_blank_lines_ignored(tmp_path):
    p = tmp_path / "dict.txt"
    p.write_text("# comment\n\nfoo -> bar\n")
    d = Dictionary(path=str(p), enabled=True)

    assert d.apply("foo baz") == "bar baz"
    assert len(d._patterns) == 1


def test_missing_file_no_error():
    d = Dictionary(path="/tmp/nonexistent_yapper_dict.txt", enabled=True)
    assert d.apply("hello") == "hello"
    assert len(d._patterns) == 0
