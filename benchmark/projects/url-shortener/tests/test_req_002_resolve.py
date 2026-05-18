"""Tests for REQ-002: resolve valid codes to originals; unknown codes absent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shortener import URLShortener  # noqa: E402


def test_valid_short_code_resolves_to_original_url() -> None:
    shortener = URLShortener()
    url = "https://example.com/target"
    code = shortener.shorten(url)
    assert shortener.resolve(code) == url


def test_invalid_short_code_returns_none() -> None:
    shortener = URLShortener()
    assert shortener.resolve("no_such_code") is None
