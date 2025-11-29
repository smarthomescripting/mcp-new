"""Website fetch service that returns extracted plain text."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlparse
from html.parser import HTMLParser

from fastmcp import FastMCP

from mcp_framework import log_interaction


ARCHIVE_DIR = Path("archive/news_crawler")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


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


def _archive_path(url: str) -> Path:
    parsed = urlparse(url)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    hostname = parsed.netloc or "unknown_host"
    return ARCHIVE_DIR / f"{hostname}_{digest}.txt"


def _load_from_archive(path: Path) -> str | None:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _save_to_archive(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def register_web_fetch_service(mcp: FastMCP) -> None:
    """Register a tool that fetches a URL and returns plain text content."""

    @mcp.tool()
    def fetch_plain_text(url: str) -> dict[str, str]:
        """Fetch the given URL and return its plain text content."""

        archive_path = _archive_path(url)
        request = urllib.request.Request(url, headers={"User-Agent": "mcp-web-fetch/1.0"})

        def _archive_response(action: str, error_detail: dict[str, str | int]):
            archived_text = _load_from_archive(archive_path)
            if archived_text is None:
                return None

            result = {"url": url, "text": archived_text, "source": "archive"}
            log_interaction(
                action,
                {"url": url},
                {"archive_path": str(archive_path), **error_detail},
            )
            return result

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = getattr(response, "status", response.getcode())
                if status == 308:  # Explicitly handle permanent redirects via archive fallback
                    raise urllib.error.HTTPError(
                        url, status, "Permanent Redirect", hdrs=response.headers, fp=None
                    )

                raw_bytes = response.read()
                content_type = response.headers.get_content_type()
                charset = response.headers.get_content_charset("utf-8")
        except urllib.error.HTTPError as exc:
            error_detail = {"error": str(exc), "status": exc.code}
            archive_action = (
                "fetch_plain_text_archive_redirect" if exc.code == 308 else "fetch_plain_text_archive_fallback"
            )
            archive_result = _archive_response(archive_action, error_detail)
            if archive_result is not None:
                return archive_result

            log_interaction("fetch_plain_text_error", {"url": url}, error_detail)
            raise
        except Exception as exc:  # Other urllib errors and unexpected issues
            error_detail = {"error": str(exc)}
            archive_result = _archive_response("fetch_plain_text_archive_fallback", error_detail)
            if archive_result is not None:
                return archive_result

            log_interaction("fetch_plain_text_error", {"url": url}, error_detail)
            raise

        decoded_content = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding=charset, errors="replace").read()
        text = _extract_text(decoded_content, content_type)

        _save_to_archive(archive_path, text)

        result = {"url": url, "text": text}
        log_interaction("fetch_plain_text", {"url": url}, result)
        return result
