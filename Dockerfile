FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/src \
    D4D_STORAGE_BACKEND=sqlite \
    D4D_SQLITE_PATH=/app/data/runtime/readiness.sqlite3

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev && mkdir -p /app/data/runtime

EXPOSE 8000

CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "d4d.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
