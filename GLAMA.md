# Deploying Heap Seance on Glama

## Build Steps

```json
["uv sync"]
```

## CMD Arguments

```json
["--", "/app/.venv/bin/python3", "-m", "heap_seance_mcp.server"]
```

Glama automatically prepends `mcp-proxy`, resulting in:

```
mcp-proxy -- /app/.venv/bin/python3 -m heap_seance_mcp.server
```

The `--` is critical — without it, `mcp-proxy` interprets `-m` as its own flag instead of passing it to Python.

## Local verification

Build and test the exact Glama image locally before deploying:

```bash
docker build -t mcp-server .
docker run -it --rm -e MCP_PROXY_DEBUG=true mcp-server
```

Expected output with debug enabled:

```
transport event { type: 'data', chunk: '{"jsonrpc":"2.0","id":0,"result":{...}}' }
transport event { type: 'message', message: { ... serverInfo: { name: 'heap-seance' } } }
starting server on port 8080
```

## Glama Dockerfile (auto-generated)

For reference, Glama generates a Dockerfile similar to this:

```dockerfile
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g mcp-proxy@6.4.3 && \
    curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR="/usr/local/bin" sh && \
    uv python install 3.14 --default --preview && \
    ln -s $(uv python find) /usr/local/bin/python && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN git clone https://github.com/SegfaultSorcerer/heap-seance . && git checkout main
RUN uv sync
CMD ["mcp-proxy", "--", "/app/.venv/bin/python3", "-m", "heap_seance_mcp.server"]
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `MCP error -32001: Request timed out` | Missing `--` separator | Add `--` before the Python command |
| `No virtual environment found` | `uv pip install` without venv | Use `uv sync` instead |
| `transport event { type: 'close' }` immediately | `mcp-proxy` can't start subprocess | Check Python path exists: `/app/.venv/bin/python3` |
