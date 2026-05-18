"""Tests for REQ-003: only http(s) URLs accepted; invalid URLs raise ValueError."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shortener import URLShortener  # noqa: E402


@pytest.mark.parametrize("url", ["http://example.com/foo", "https://example.com/bar"])
def test_http_and_https_urls_are_accepted(url: str) -> None:
    shortener = URLShortener()
    code = shortener.shorten(url)
    assert len(code) == 6


@pytest.mark.parametrize(
    "bad_url",
    [
        "ftp://example.com/file",
        "example.com",
        "not a url",
        "",
        "http://",
    ],
)
def test_invalid_urls_rejected_with_error_message(bad_url: str) -> None:
    shortener = URLShortener()
    with pytest.raises(ValueError, match="Invalid URL"):
        shortener.shorten(bad_url)
