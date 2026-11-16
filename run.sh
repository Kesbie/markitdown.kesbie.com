#!/usr/bin/env bash
# Chạy md2x — ưu tiên uv; không có uv thì dùng .venv do pip tạo (xem deploy/android/).
set -euo pipefail

cd "$(dirname "$0")"

if command -v uv >/dev/null 2>&1; then
  # Dùng cache trong thư mục dự án để tránh lỗi quyền ở ~/.cache trên một số máy.
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uvcache}"
  # proot/chroot trên Android không thích hardlink giữa các filesystem.
  export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
  exec uv run md2x "$@"
fi

if [ -x .venv/bin/md2x ]; then
  exec .venv/bin/md2x "$@"
fi

echo "Chưa có uv và cũng chưa có .venv. Cài một trong hai:" >&2
echo "  uv:  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
echo "  pip: python3 -m venv .venv && .venv/bin/pip install -e ." >&2
echo "Android/Termux xem deploy/android/README.md" >&2
exit 1
