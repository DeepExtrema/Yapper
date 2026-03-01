"""Tests for the text formatter module."""

from yapper.formatter import format_text


class TestFormatText:
    def test_capitalize_first_letter(self):
        assert format_text("hello world") == "Hello world"

    def test_capitalize_after_period(self):
        assert format_text("hello. world") == "Hello. World"

    def test_clean_double_spaces(self):
        assert format_text("hello  world") == "Hello world"
        assert format_text("hello    world") == "Hello world"

    def test_trim_whitespace(self):
        assert format_text("  hello world  ") == "Hello world"

    def test_no_space_before_period(self):
        assert format_text("hello .") == "Hello."

    def test_no_space_before_comma(self):
        assert format_text("hello , world") == "Hello, world"

    def test_space_after_period_when_missing(self):
        assert format_text("hello.world") == "Hello. World"

    def test_empty_string(self):
        assert format_text("") == ""

    def test_already_formatted(self):
        assert format_text("Hello world.") == "Hello world."

    def test_multiple_sentences(self):
        assert format_text("hello. world. foo bar.") == "Hello. World. Foo bar."

    def test_question_marks(self):
        assert format_text("how are you? fine.") == "How are you? Fine."
        assert format_text("how are you?fine") == "How are you? Fine"

    def test_exclamation_marks(self):
        assert format_text("wow! amazing.") == "Wow! Amazing."
        assert format_text("wow!amazing") == "Wow! Amazing"

    def test_no_space_before_other_punctuation(self):
        assert format_text("wait ; what") == "Wait; what"
        assert format_text("note : this") == "Note: this"
        assert format_text("really !") == "Really!"
        assert format_text("really ?") == "Really?"

    def test_whitespace_only(self):
        assert format_text("   ") == ""

    def test_single_word(self):
        assert format_text("hello") == "Hello"
