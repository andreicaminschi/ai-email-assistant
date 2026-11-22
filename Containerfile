FROM ghcr.io/astral-sh/uv:0.13.7-python3.14-trixie-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./


FROM base AS app

RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --no-create-home agent \
    && mkdir /data \
    && chown agent:agent /data
USER agent

CMD ["/app/.venv/bin/python", "-m", "email_agent"]
