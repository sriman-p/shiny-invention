"""Tests for REQ-001: shorten returns a stable 6-character code."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shortener import URLShortener  # noqa: E402


def test_shorten_returns_six_character_code() -> None:
    shortener = URLShortener()
    code = shortener.shorten("https://example.com/path")
    assert len(code) == 6
    assert all(c in "0123456789abcdef" for c in code)


def test_same_url_always_generates_same_short_code() -> None:
    shortener = URLShortener()
    url = "https://example.com/stable"
    assert shortener.shorten(url) == shortener.shorten(url)
