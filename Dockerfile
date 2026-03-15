FROM eclipse-temurin:17-jdk AS base

# Install Python 3.12 and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY . .

RUN uv venv .venv && uv pip install --python .venv/bin/python -e .

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "heap_seance_mcp.server"]
