# md2x — image gọn, chạy bằng uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    MD2X_MAX_FILE_MB=200 \
    MD2X_MAX_FILES=50

WORKDIR /app

# Cài phụ thuộc trước, tách khỏi mã nguồn để tận dụng cache của Docker.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --no-dev

# Chạy dưới user thường.
RUN useradd -r -u 10001 -m md2x && chown -R md2x:md2x /app
USER md2x

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=4).status==200 else 1)"

CMD ["uv", "run", "md2x", "serve", "--host", "0.0.0.0", "--port", "8765", "--no-open"]
