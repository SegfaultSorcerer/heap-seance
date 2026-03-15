<p align="center">
  <img src="assets/banner.png" alt="Heap Seance" width="700">
</p>

<h1 align="center">Heap Seance</h1>

<p align="center">
  <em>Summoning retained objects from the heap — so you can interrogate what refuses to die.</em>
</p>

An MCP server + CLI toolkit that channels the spirits of `jcmd`, `jmap`, `jstat`, `jfr`, Eclipse MAT, and async-profiler into a structured leak investigation workflow — designed to run inside [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

---

## How It Works

Heap Seance follows a two-stage escalation model. No deep forensics unless the evidence demands it.

```
 /leak-scan                          /leak-deep
     |                                   |
     v                                   v
  3x class histogram               (all of scan, plus)
  + GC pressure snapshot            JFR recording
     |                              heap dump
     v                              MAT leak suspects
  monotonic growth?                 async-profiler alloc profile
  old-gen pressure?                     |
     |                                  v
     +--- both true? -----> auto-escalate to deep
     |
     +--- otherwise ------> verdict + next steps
```

**Confidence is earned, not assumed.** `high` requires at least two independent strong signals. A single growing class is `watch`. Growth plus GC pressure is `suspicious`. Add a MAT dominator or JFR correlation and you get `probable_memory_leak`.

## Quick Start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/), Python 3.10+, and a JDK 17+ for tooling (the target app can run any Java version).

### 1. Clone

```bash
git clone https://github.com/your-org/heap-seance.git
```

### 2. Add `.mcp.json` to your Java project

In the project you want to investigate, create a `.mcp.json`:

```json
{
  "mcpServers": {
    "heap-seance": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/heap-seance", "python", "-m", "heap_seance_mcp.server"],
      "env": {
        "JAVA_HOME": "/path/to/jdk-17",
        "MAT_BIN": "/path/to/ParseHeapDump.sh",
        "ASYNC_PROFILER_BIN": "/path/to/asprof"
      }
    }
  }
}
```

`--directory` points to where you cloned Heap Seance. `uv run` handles the virtual environment and dependencies automatically. `ASYNC_PROFILER_BIN` is optional — if missing, deep mode continues with JFR + MAT.

### 3. Copy the Claude Code commands

Copy the `.claude/commands/` folder into your Java project so the `/leak-scan` and `/leak-deep` slash commands are available:

```bash
cp -r /path/to/heap-seance/.claude/commands/ .claude/commands/
```

### 4. Run

```bash
/leak-scan my-service        # conservative scan
/leak-deep 12345             # full forensics by PID
```

Heap Seance resolves the target process, collects evidence, and returns a structured verdict.

## MCP Tools

| Tool | What it does |
|------|-------------|
| `java_list_processes()` | Discover running JVMs via `jcmd -l` |
| `java_class_histogram(pid)` | Snapshot live object counts per class |
| `java_gc_snapshot(pid)` | Sample `jstat -gcutil` over time |
| `java_jfr_start(pid)` | Capture a JFR recording |
| `java_jfr_summary(jfr_file)` | Summarize JFR event types and counts |
| `java_heap_dump(pid)` | Full heap dump (`.hprof`) |
| `java_mat_suspects(heap_dump)` | Run MAT leak suspects analysis |
| `java_async_alloc_profile(pid)` | Allocation flame graph via async-profiler |

Every tool returns the same unified schema:

```json
{
  "status": "ok | warn | error",
  "evidence": ["..."],
  "metrics": {},
  "confidence": "none | low | medium | high",
  "next_recommended_action": "...",
  "raw_artifact_path": "..."
}
```

## Investigation Workflow

1. **Start your app** and let it initialize fully.
2. **`/leak-scan <name-or-pid>`** — takes the first histogram snapshot.
3. **Exercise the suspect behavior** — the scan prompts you between each of the 3 histogram samples to perform the action you suspect is leaking (open/close views, send requests, repeat workflows). This is critical — without load between samples, leaks stay invisible.
4. **Read the verdict.** Focus on `Confidence`, `Key Evidence`, `Suspect Types`.
5. **`/leak-deep <name-or-pid>`** if the scan flags growth, or if you want full forensics regardless.
6. **Fix and re-scan.** Bounded caches, weak refs, listener cleanup — then `/leak-scan` again to confirm the signal drops.
7. **Keep artifacts.** `.jfr`, `.hprof`, and MAT reports are saved for team review.

### What you get back

**`/leak-scan`** returns: Verdict, Confidence, Key Evidence, Suspect Types, Artifacts, Next Steps.

**`/leak-deep`** goes further: Verdict, Confidence, Root Holder Hypothesis (who retains the growing objects and via which field/chain), Supporting Evidence, Artifacts, Remediation Hypotheses (concrete fix suggestions), Verification Plan.

### Confidence ladder

| Confidence | What it means | Signals required |
|------------|--------------|-----------------|
| `none` | No leak evidence | — |
| `low` | Weak growth, no GC pressure | histogram only |
| `medium` | Growth + GC is losing | histogram + GC pressure |
| `high` | Probable leak, corroborated | histogram + GC + MAT/JFR |

## Prerequisites

**Tooling JDK** (required):
- JDK 17+ for `jcmd`, `jmap`, `jstat` — set via `JAVA_HOME` in `.mcp.json`
- The target application can run any Java version (including Java 8)

**Deep forensics** (for `/leak-deep`):
- [Eclipse MAT CLI](https://eclipse.dev/mat/downloads.php) (`ParseHeapDump.sh` / `.bat`) — required for deep mode
- [async-profiler](https://github.com/async-profiler/async-profiler/releases) — optional tie-breaker

**Optional tools:**
- `jfr` CLI — used for JFR summary if available, falls back to `jcmd JFR.view` otherwise. JFR is skipped entirely for Java 8 targets (incompatible format).

Check your setup:

```bash
./scripts/check_prereqs.sh          # macOS / Linux
scripts\check_prereqs.bat           # Windows
```

### Environment overrides

Set these in your `.mcp.json` `env` block (recommended) or as shell variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `JAVA_HOME` | recommended | JDK 17+ installation path — `$JAVA_HOME/bin` is searched first for `jcmd`, `jmap`, `jstat`, `jfr`. Also used to launch MAT with the correct Java version. |
| `MAT_BIN` | for deep mode | Path to `ParseHeapDump.sh` (macOS/Linux) or `.bat` (Windows) |
| `ASYNC_PROFILER_BIN` | optional | Path to async-profiler binary — tie-breaker evidence, deep mode works without it |
| `HEAP_SEANCE_ARTIFACT_DIR` | optional | Where `.jfr`, `.hprof`, and reports are saved (default: system temp dir) |

See `.mcp.json.example` for a full config template.

### Compatibility notes

- **Java 8 targets**: histogram + GC + MAT work fully. JFR is skipped (v0.9 format incompatible with modern tools).
- **Windows**: MAT works via `ParseHeapDump.bat`. async-profiler is optional — if missing, deep mode continues with JFR + MAT. Locale-specific decimal separators (comma vs dot) in `jstat` output are handled automatically.
- **MAT + JAVA_HOME**: MAT is launched with the JDK from `JAVA_HOME`, so it works even if the system default Java is too old for MAT.

## CLI Usage (without Claude Code)

```bash
uv run heap-seance --mode scan --match your-app
uv run heap-seance --mode deep --pid 12345 --output json
```

<details>
<summary><strong>Installing uv</strong></summary>

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

</details>

<details>
<summary><strong>Manual setup (without uv)</strong></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .\.venv\Scripts\Activate.ps1
pip install -e .

heap-seance --mode scan --match your-app
```

</details>

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Example Java scenarios for validation live in `examples/java-scenarios/` — a real leak, a bounded cache (no leak), and a burst allocator (no leak).

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding tools, signals, and skills.

## License

This project is dual-licensed under either of

- [Apache License, Version 2.0](LICENSE-APACHE)
- [MIT License](LICENSE-MIT)

at your option.
