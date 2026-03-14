#!/usr/bin/env bash
set -euo pipefail

require() {
  local bin="$1"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "MISSING: $bin"
    return 1
  fi
  echo "OK: $bin -> $(command -v "$bin")"
  return 0
}

status=0
for bin in jcmd jmap jstat jfr; do
  require "$bin" || status=1
done

if command -v ParseHeapDump.sh >/dev/null 2>&1 || command -v ParseHeapDump.bat >/dev/null 2>&1 || command -v mat >/dev/null 2>&1 || [[ -n "${MAT_BIN:-}" ]]; then
  echo "OK: MAT CLI"
else
  echo "MISSING: Eclipse MAT CLI (ParseHeapDump.sh, ParseHeapDump.bat, or mat)"
  status=1
fi

if command -v async-profiler >/dev/null 2>&1 || command -v profiler.sh >/dev/null 2>&1 || [[ -n "${ASYNC_PROFILER_BIN:-}" ]]; then
  echo "OK: async-profiler"
else
  echo "WARN: async-profiler missing (optional; deep mode falls back to JFR + MAT)"
fi

exit "$status"
