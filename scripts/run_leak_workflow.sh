#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -d "$ROOT/.venv" ]]; then
  source "$ROOT/.venv/bin/activate"
fi

python -m java_leak_hunter_mcp.workflow "$@"
