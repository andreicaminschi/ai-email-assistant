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


FROM base AS wrapper

ARG CLAUDE_CODE_VERSION=2.1.216
ENV DISABLE_AUTOUPDATER=1
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN uv sync --frozen --no-dev --group wrapper --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --group wrapper

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://claude.ai/install.sh | bash -s "$CLAUDE_CODE_VERSION" \
    && cp -L /root/.local/bin/claude /usr/local/bin/claude \
    && rm -rf /root/.local /root/.claude /root/.claude.json \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && claude --version

RUN useradd --system --uid 10002 --create-home wrapper
USER wrapper

CMD ["/app/.venv/bin/uvicorn", "wrapper.server:app", "--host", "0.0.0.0", "--port", "8000"]
