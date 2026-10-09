"""Parsing of Markdown fenced code blocks in model responses."""

import json
import re

# Language tag is any run of non-space characters (python, c++, objective-c); anything
# after it on the opening line (e.g. a filename) is ignored.
_FENCE_RE = re.compile(r"```([^\s`]*)[^\n]*\n(.*?)```", re.DOTALL)


def extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """Return (language, code) for every fenced block, in order."""
    return [(language, code.rstrip("\n")) for language, code in _FENCE_RE.findall(text)]


def strip_outer_fence(text: str) -> str:
    """Return the content of the single fenced block if there is exactly one, else the
    trimmed text. Used to recover bare JSON when a model wraps it in a fence anyway."""
    blocks = extract_code_blocks(text)
    if len(blocks) == 1:
        return blocks[0][1].strip()
    if not blocks:
        return text.strip()
    return text


def is_json_response(text: str) -> bool:
    """True if the response, once any single surrounding fence is removed, parses as JSON."""
    try:
        json.loads(strip_outer_fence(text))
    except json.JSONDecodeError:
        return False
    return True
