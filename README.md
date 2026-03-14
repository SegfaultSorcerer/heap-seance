# Java Leak Hunter MCP (POC)

Hybrid POC for leak diagnostics in local Java processes:
- MCP server executes JVM forensics (`jcmd`, `jmap`, `jstat`, `jfr`, MAT, async-profiler).
- Claude Code custom commands provide deterministic workflow (`/leak-scan`, `/leak-deep`).

## Implemented MCP Tools

- `java_list_processes()`
- `java_gc_snapshot(pid, interval_s, samples)`
- `java_class_histogram(pid, live_only)`
- `java_jfr_start(pid, profile, duration_s, out_file)`
- `java_jfr_summary(jfr_file)`
- `java_heap_dump(pid, live_only, out_file)`
- `java_mat_suspects(heap_dump_file)`
- `java_async_alloc_profile(pid, duration_s, out_file)`

All tools return a unified schema:
- `status`
- `evidence[]`
- `metrics{}`
- `confidence`
- `next_recommended_action`
- `raw_artifact_path`

## Prerequisites

Required core tools:
- `jcmd`, `jmap`, `jstat`, `jfr` (OpenJDK 17+)

Required deep-forensics tools:
- Eclipse MAT CLI (`ParseHeapDump.sh` or `mat`)
- `async-profiler` (or `profiler.sh`)

Optional env overrides:
- `MAT_BIN=/absolute/path/to/ParseHeapDump.sh`
- `ASYNC_PROFILER_BIN=/absolute/path/to/async-profiler`
- `LEAK_HUNTER_ARTIFACT_DIR=/tmp/java-leak-hunter`

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run as MCP Server

```bash
source .venv/bin/activate
python -m java_leak_hunter_mcp.server
```

Then register this process in Claude Code as an MCP server (project scope). For example:

```bash
claude mcp add java-leak-hunter --scope project -- python -m java_leak_hunter_mcp.server
```

## Use Workflow CLI (optional)

```bash
source .venv/bin/activate
leak-workflow --mode scan --match your-app
leak-workflow --mode deep --pid 12345 --output json
```

## Claude Code Commands

This repo includes:
- `.claude/commands/leak-scan.md`
- `.claude/commands/leak-deep.md`

Usage in Claude Code:
- `/leak-scan <pid-or-pattern>`
- `/leak-deep <pid-or-pattern>`

## Test and Validation

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Example Java scenarios are available in `examples/java-scenarios`.
