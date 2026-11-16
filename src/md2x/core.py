"""Lõi convert: bọc markitdown lại cho gọn và an toàn khi chạy song song."""

from __future__ import annotations

import io
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from markitdown import MarkItDown, StreamInfo

# Các đuôi file markitdown xử lý được (dùng cho UI + validate).
SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    # Office
    ".docx", ".doc", ".xlsx", ".xls", ".xlsm", ".pptx", ".ppt",
    # Tài liệu / văn bản
    ".pdf", ".epub", ".md", ".markdown", ".txt", ".text", ".rtf",
    # Web / dữ liệu
    ".html", ".htm", ".xml", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
    # Ảnh (OCR/metadata) và âm thanh (transcript)
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ".mp3", ".wav", ".m4a", ".flac",
    # Nén / khác
    ".zip", ".ipynb", ".msg", ".eml",
)

_MAX_SOURCE_LABEL = 180


@dataclass
class ConversionResult:
    """Kết quả convert một nguồn (file hoặc URL)."""

    source: str
    ok: bool
    markdown: str = ""
    title: str | None = None
    error: str | None = None
    filename: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "ok": self.ok,
            "markdown": self.markdown,
            "title": self.title,
            "error": self.error,
            "filename": self.filename,
            "chars": len(self.markdown),
            "meta": self.meta,
        }


class Converter:
    """Wrapper quanh MarkItDown.

    MarkItDown không hứa an toàn thread, nên mỗi lần convert giữ một lock ngắn.
    Dựng instance một lần vì khởi tạo plugin khá tốn thời gian.
    """

    def __init__(self, *, enable_plugins: bool = False) -> None:
        self._lock = threading.Lock()
        self._md = MarkItDown(enable_plugins=enable_plugins)

    # ---------- API chính ----------

    def convert_bytes(self, data: bytes, filename: str) -> ConversionResult:
        """Convert nội dung file đã nằm trong bộ nhớ."""
        name = Path(filename or "untitled").name
        ext = Path(name).suffix.lower()
        stream_info = StreamInfo(extension=ext or None, filename=name or None)
        try:
            with self._lock:
                res = self._md.convert_stream(io.BytesIO(data), stream_info=stream_info)
        except Exception as exc:  # noqa: BLE001 - trả lỗi về cho UI, không làm sập request
            return ConversionResult(
                source=name,
                ok=False,
                error=_format_error(exc),
                filename=markdown_filename(name),
                meta={"bytes": len(data), "extension": ext},
            )
        return ConversionResult(
            source=name,
            ok=True,
            markdown=res.markdown or "",
            title=getattr(res, "title", None),
            filename=markdown_filename(name),
            meta={"bytes": len(data), "extension": ext},
        )

    def convert_path(self, path: str | Path) -> ConversionResult:
        """Convert một file trên đĩa."""
        p = Path(path).expanduser()
        try:
            data = p.read_bytes()
        except OSError as exc:
            return ConversionResult(
                source=str(p), ok=False, error=f"Không đọc được file: {exc}"
            )
        result = self.convert_bytes(data, p.name)
        result.source = str(p)
        return result

    def convert_url(self, url: str) -> ConversionResult:
        """Convert nội dung từ URL (trang web, PDF online, YouTube...)."""
        url = url.strip()
        if not re.match(r"^https?://", url, re.IGNORECASE):
            return ConversionResult(
                source=url[:_MAX_SOURCE_LABEL],
                ok=False,
                error="URL phải bắt đầu bằng http:// hoặc https://",
            )
        try:
            with self._lock:
                res = self._md.convert_uri(url)
        except Exception as exc:  # noqa: BLE001
            return ConversionResult(
                source=url[:_MAX_SOURCE_LABEL], ok=False, error=_format_error(exc)
            )
        title = getattr(res, "title", None)
        return ConversionResult(
            source=url[:_MAX_SOURCE_LABEL],
            ok=True,
            markdown=res.markdown or "",
            title=title,
            filename=markdown_filename(title or _slug_from_url(url)),
            meta={"url": url},
        )


# ---------- Tiện ích ----------


def markdown_filename(name: str) -> str:
    """Đổi tên nguồn thành tên file .md an toàn."""
    stem = Path(name or "untitled").stem or "untitled"
    stem = re.sub(r"[^\w\s.\-()\[\]]+", "", stem, flags=re.UNICODE).strip()
    stem = re.sub(r"\s+", "-", stem) or "untitled"
    return f"{stem[:100]}.md"


def _slug_from_url(url: str) -> str:
    tail = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    tail = tail.split("?", 1)[0].split("#", 1)[0].strip("/")
    return tail.replace("/", "-") or "page"


def _format_error(exc: Exception) -> str:
    msg = str(exc).strip() or exc.__class__.__name__
    # Thông điệp lỗi của markitdown có thể rất dài (liệt kê mọi converter đã thử).
    lines = [ln.strip() for ln in msg.splitlines() if ln.strip()]
    if len(lines) > 6:
        lines = lines[:6] + [f"... (+{len(msg.splitlines()) - 6} dòng)"]
    return f"{exc.__class__.__name__}: " + " | ".join(lines)


_shared: Converter | None = None
_shared_lock = threading.Lock()


def get_converter(*, enable_plugins: bool = False) -> Converter:
    """Instance dùng chung, khởi tạo lười."""
    global _shared
    if _shared is None:
        with _shared_lock:
            if _shared is None:
                _shared = Converter(enable_plugins=enable_plugins)
    return _shared
