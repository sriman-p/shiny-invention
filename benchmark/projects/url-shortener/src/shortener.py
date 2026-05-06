import hashlib
import re


class URLShortener:
    """Simple in-memory URL shortener."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def shorten(self, url: str) -> str:
        """Shorten a URL and return the short code."""
        self._validate_url(url)
        code = hashlib.md5(url.encode()).hexdigest()[:6]
        self._store[code] = url
        return code

    def resolve(self, code: str) -> str | None:
        """Resolve a short code to the original URL."""
        return self._store.get(code)

    def _validate_url(self, url: str) -> None:
        """Validate that the URL is well-formed."""
        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        if not re.match(pattern, url):
            raise ValueError(f"Invalid URL: {url}")
