"""Tests for fenced code-block parsing."""

from ask_cli.core.fences import extract_code_blocks, strip_outer_fence


class TestExtractCodeBlocks:
    def test_extracts_blocks_with_language(self):
        text = "intro\n```python\nprint(1)\n```\nmiddle\n```bash\nls -la\n```\n"
        assert extract_code_blocks(text) == [("python", "print(1)"), ("bash", "ls -la")]

    def test_language_tag_with_symbols(self):
        assert extract_code_blocks("```c++\nint x;\n```") == [("c++", "int x;")]

    def test_block_without_language(self):
        assert extract_code_blocks("```\nplain\n```") == [("", "plain")]

    def test_no_blocks(self):
        assert extract_code_blocks("just prose") == []

    def test_preserves_internal_blank_lines_and_long_lines(self):
        code = "a = 1\n\n" + "b = '" + "x" * 150 + "'"
        assert extract_code_blocks(f"```python\n{code}\n```") == [("python", code)]


class TestStripOuterFence:
    def test_whole_text_fenced(self):
        assert strip_outer_fence('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_single_block_with_surrounding_prose(self):
        assert strip_outer_fence("Here you go:\n```json\n[1, 2]\n```\nEnjoy.") == "[1, 2]"

    def test_unfenced_text_is_trimmed(self):
        assert strip_outer_fence('  {"a": 1}\n') == '{"a": 1}'

    def test_multiple_blocks_left_untouched(self):
        text = "```json\n[1]\n```\n```json\n[2]\n```"
        assert strip_outer_fence(text) == text
