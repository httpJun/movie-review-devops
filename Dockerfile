FROM python:3.12-slim-trixie AS builder

WORKDIR /app

# Compilers and development headers belong only in the build stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

FROM python:3.12-slim-trixie AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

COPY --from=builder /app/.venv /app/.venv
# Keep browser and PostgreSQL runtime libraries, without the compiler toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY data ./data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
