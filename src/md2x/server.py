"""Web server FastAPI: upload file / dán URL -> Markdown."""

from __future__ import annotations

import asyncio
import io
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .core import SUPPORTED_EXTENSIONS, ConversionResult, get_converter


def _env_int(name: str, default: int) -> int:
    """Đọc số nguyên dương từ biến môi trường; giá trị sai thì dùng mặc định."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


# Giới hạn cho một request (tránh ăn hết RAM). Chỉnh qua biến môi trường khi deploy.
# Lưu ý: đặt MD2X_MAX_FILE_MB khớp với client_max_body_size trong nginx.
MAX_FILE_BYTES = _env_int("MD2X_MAX_FILE_MB", 200) * 1024 * 1024
MAX_FILES = _env_int("MD2X_MAX_FILES", 50)

_STATIC_DIR = Path(__file__).parent / "web"

app = FastAPI(title="md2x", description="Convert tài liệu sang Markdown", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    """Health-check cho nginx / systemd / docker."""
    return JSONResponse({"status": "ok"})


@app.get("/api/info")
async def info() -> JSONResponse:
    return JSONResponse(
        {
            "extensions": list(SUPPORTED_EXTENSIONS),
            "maxFileBytes": MAX_FILE_BYTES,
            "maxFiles": MAX_FILES,
        }
    )


@app.post("/api/convert")
async def convert(
    files: list[UploadFile] = File(default=[]),
    urls: str = Form(default=""),
) -> JSONResponse:
    """Nhận nhiều file và/hoặc nhiều URL (mỗi dòng một URL)."""
    url_list = [u.strip() for u in urls.splitlines() if u.strip()]
    if not files and not url_list:
        raise HTTPException(status_code=400, detail="Chưa có file hoặc URL nào.")
    if len(files) + len(url_list) > MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"Tối đa {MAX_FILES} mục trong một lần."
        )

    converter = get_converter()
    payloads: list[tuple[bytes, str]] = []
    oversize: list[ConversionResult] = []

    for up in files:
        data = await up.read()
        if len(data) > MAX_FILE_BYTES:
            oversize.append(
                ConversionResult(
                    source=up.filename or "?",
                    ok=False,
                    error=f"File quá lớn ({len(data) / 1e6:.1f} MB > {MAX_FILE_BYTES / 1e6:.0f} MB).",
                )
            )
            continue
        payloads.append((data, up.filename or "untitled"))

    async def run_file(item: tuple[bytes, str]) -> ConversionResult:
        data, name = item
        return await asyncio.to_thread(converter.convert_bytes, data, name)

    async def run_url(u: str) -> ConversionResult:
        return await asyncio.to_thread(converter.convert_url, u)

    tasks = [run_file(p) for p in payloads] + [run_url(u) for u in url_list]
    results: list[ConversionResult] = list(await asyncio.gather(*tasks))
    results.extend(oversize)

    _dedupe_filenames(results)
    return JSONResponse({"results": [r.to_dict() for r in results]})


@app.post("/api/zip")
async def zip_results(payload: dict) -> Response:
    """Đóng gói danh sách {filename, markdown} thành một file zip."""
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="Không có nội dung để đóng gói.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            name = str(item.get("filename") or "untitled.md")
            content = str(item.get("markdown") or "")
            zf.writestr(name, content)
    buf.seek(0)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="markdown-{stamp}.zip"'},
    )


def _dedupe_filenames(results: list[ConversionResult]) -> None:
    """Đảm bảo tên file trong zip không trùng nhau."""
    seen: dict[str, int] = {}
    for r in results:
        if not r.filename:
            r.filename = "untitled.md"
        base = r.filename
        if base in seen:
            seen[base] += 1
            stem = Path(base).stem
            r.filename = f"{stem}-{seen[base]}.md"
        else:
            seen[base] = 0


def run(host: str = "127.0.0.1", port: int = 8765, reload: bool = False) -> None:
    import uvicorn

    uvicorn.run(
        "md2x.server:app" if reload else app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )

