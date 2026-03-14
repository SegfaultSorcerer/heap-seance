#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/src/main/java"
OUT="$ROOT/target/classes"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <leak|cache|burst>"
  exit 1
fi

mkdir -p "$OUT"
find "$SRC" -name '*.java' -print0 | xargs -0 javac -d "$OUT"

case "$1" in
  leak)
    CLASS="com.example.leaks.LeakMapScenario"
    ;;
  cache)
    CLASS="com.example.leaks.BoundedCacheScenario"
    ;;
  burst)
    CLASS="com.example.leaks.BurstAllocationScenario"
    ;;
  *)
    echo "Unknown scenario '$1'. Use leak, cache, or burst."
    exit 1
    ;;
esac

java -cp "$OUT" "$CLASS"
