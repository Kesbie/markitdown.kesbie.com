"""CLI: md2x serve | md2x convert <file|url> ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import get_converter, markdown_filename


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="md2x",
        description="Convert tài liệu (docx, xlsx, pptx, pdf, html, csv...) sang Markdown.",
    )
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="Chạy web UI (mặc định)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--reload", action="store_true", help="Tự reload khi sửa code")
    s.add_argument("--no-open", action="store_true", help="Không tự mở trình duyệt")

    c = sub.add_parser("convert", help="Convert ngay trong terminal")
    c.add_argument("sources", nargs="+", help="Đường dẫn file hoặc URL http(s)")
    c.add_argument("-o", "--output", help="Thư mục lưu .md (bỏ qua = in ra stdout)")
    c.add_argument("-q", "--quiet", action="store_true", help="Chỉ in lỗi")

    return p


def _is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))


def cmd_convert(args: argparse.Namespace) -> int:
    conv = get_converter()
    out_dir = Path(args.output).expanduser() if args.output else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    multiple = len(args.sources) > 1

    for src in args.sources:
        res = conv.convert_url(src) if _is_url(src) else conv.convert_path(src)
        if not res.ok:
            print(f"[LỖI] {src}: {res.error}", file=sys.stderr)
            failures += 1
            continue

        if out_dir:
            target = out_dir / (res.filename or markdown_filename(src))
            stem = target.stem
            n = 1
            while target.exists():
                target = out_dir / f"{stem}-{n}.md"
                n += 1
            target.write_text(res.markdown, encoding="utf-8")
            if not args.quiet:
                print(f"✓ {src} → {target} ({len(res.markdown):,} ký tự)")
        else:
            if multiple and not args.quiet:
                print(f"\n<!-- ===== {src} ===== -->")
            sys.stdout.write(res.markdown)
            if not res.markdown.endswith("\n"):
                sys.stdout.write("\n")

    return 1 if failures else 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import run

    url = f"http://{args.host}:{args.port}"
    print(f"md2x đang chạy tại {url}  (Ctrl+C để dừng)")
    if not args.no_open:
        import threading
        import webbrowser

        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    run(host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["serve"]
    args = parser.parse_args(argv)

    if args.cmd == "convert":
        return cmd_convert(args)
    return cmd_serve(args)


if __name__ == "__main__":
    raise SystemExit(main())
