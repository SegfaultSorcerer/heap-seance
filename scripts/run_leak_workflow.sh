#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -d "$ROOT/.venv" ]]; then
  source "$ROOT/.venv/bin/activate"
fi

python -m heap_seance_mcp.workflow "$@"
