"""Website fetch service that returns extracted plain text."""
from __future__ import annotations

import io
import urllib.error
import urllib.request
from html.parser import HTMLParser

from fastmcp import FastMCP

from mcp_framework import log_interaction


class _TextExtractor(HTMLParser):
    """Simple HTML parser that extracts readable text while skipping scripts/styles."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str):  # type: ignore[override]
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str):  # type: ignore[override]
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        return "\n".join(self._chunks)


def _extract_text(content: str, content_type: str) -> str:
    if content_type.startswith("text/plain"):
        return content

    parser = _TextExtractor()
    parser.feed(content)
    return parser.get_text()


def register_web_fetch_service(mcp: FastMCP) -> None:
    """Register a tool that fetches a URL and returns plain text content."""

    @mcp.tool()
    def fetch_plain_text(url: str) -> dict[str, str]:
        """Fetch the given URL and return its plain text content."""

        request = urllib.request.Request(url, headers={"User-Agent": "mcp-web-fetch/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw_bytes = response.read()
                content_type = response.headers.get_content_type()
                charset = response.headers.get_content_charset("utf-8")
        except urllib.error.URLError as exc:
            error_detail = {"error": str(exc.reason) if hasattr(exc, "reason") else str(exc)}
            log_interaction("fetch_plain_text_error", {"url": url}, error_detail)
            raise

        decoded_content = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding=charset, errors="replace").read()
        text = _extract_text(decoded_content, content_type)

        result = {"url": url, "text": text}
        log_interaction("fetch_plain_text", {"url": url}, result)
        return result
