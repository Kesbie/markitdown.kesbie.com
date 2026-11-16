#!/usr/bin/env bash
# Chạy md2x — tự cài phụ thuộc lần đầu bằng uv.
set -euo pipefail

cd "$(dirname "$0")"

# Dùng cache trong thư mục dự án để tránh lỗi quyền ở ~/.cache trên một số máy.
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uvcache}"

if ! command -v uv >/dev/null 2>&1; then
  echo "Chưa có uv. Cài bằng: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

exec uv run md2x "$@"
