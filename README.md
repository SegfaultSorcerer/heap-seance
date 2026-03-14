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
- Eclipse Memory Analyzer (MAT) CLI (required on all platforms)
- `async-profiler` CLI (optional fallback booster; see Windows note below)

### Recommended concrete tooling (verified on March 14, 2026)

1. MAT CLI (heap dump analyzer):
- Recommended: Eclipse MAT `1.16.1` package from the official download page:
  - [https://eclipse.dev/mat/downloads.php](https://eclipse.dev/mat/downloads.php)
- Use the MAT CLI launcher from that package:
  - Linux/macOS: `ParseHeapDump.sh`
  - Windows: `ParseHeapDump.bat`
- Analyzer report used by this project:
  - `org.eclipse.mat.api:suspects` (Leak Suspects report)
  - Official command-line docs: [https://help.eclipse.org/latest/topic/org.eclipse.mat.ui.help/tasks/runningleaksuspectreport.html](https://help.eclipse.org/latest/topic/org.eclipse.mat.ui.help/tasks/runningleaksuspectreport.html)

2. Allocation analyzer:
- Recommended: `async-profiler v4.3` (latest stable release at time of verification):
  - [https://github.com/async-profiler/async-profiler/releases](https://github.com/async-profiler/async-profiler/releases)
- Command reference and usage examples:
  - [https://github.com/async-profiler/async-profiler](https://github.com/async-profiler/async-profiler)

### Windows compatibility behavior

- MAT deep analysis is supported on Windows via `ParseHeapDump.bat`.
- If `async-profiler` is not available on Windows, deep mode does **not** fail:
  - the workflow continues with `JFR + heap dump + MAT suspects`
  - report confidence is still based on independent signals (growth, GC pressure, MAT, JFR support)
  - async-profiler is treated as optional tie-breaker evidence
- On Linux/macOS, async-profiler is still recommended for stronger allocation evidence.

Optional env overrides:
- `MAT_BIN=/absolute/path/to/ParseHeapDump.sh` or `C:\\path\\to\\ParseHeapDump.bat`
- `ASYNC_PROFILER_BIN=/absolute/path/to/async-profiler`
- `LEAK_HUNTER_ARTIFACT_DIR=/tmp/java-leak-hunter`

Prerequisite checks:
- Linux/macOS: `./scripts/check_prereqs.sh`
- Windows (cmd.exe): `scripts\\check_prereqs.bat`

## Step-by-step Setup with Claude Code

### macOS Setup (zsh/bash)

1. Clone/open this project in your terminal.
2. Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

3. Configure deep-forensics tools (recommended):
- Install MAT and set `MAT_BIN` to `ParseHeapDump.sh` if it is not in `PATH`.
- Install async-profiler and set `ASYNC_PROFILER_BIN` if it is not in `PATH`.

Example:

```bash
export MAT_BIN="/Applications/mat/ParseHeapDump.sh"
export ASYNC_PROFILER_BIN="/opt/async-profiler/asprof"
```

4. Run prerequisite check:

```bash
./scripts/check_prereqs.sh
```

5. Register MCP server in Claude Code (project scope):

```bash
claude mcp add java-leak-hunter --scope project -- python -m java_leak_hunter_mcp.server
```

6. Verify MCP registration:

```bash
claude mcp list
```

### Windows Setup (PowerShell)

1. Open PowerShell in the project folder.
2. Create and activate virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

3. Configure MAT (required for deep path):
- Set `MAT_BIN` to `ParseHeapDump.bat` if not in `PATH`.

Example:

```powershell
$env:MAT_BIN = "C:\tools\mat\ParseHeapDump.bat"
```

4. Optional: configure async-profiler if you have a compatible setup:

```powershell
$env:ASYNC_PROFILER_BIN = "C:\path\to\async-profiler-executable"
```

5. Run prerequisite check:

```powershell
cmd /c scripts\check_prereqs.bat
```

6. Register MCP server in Claude Code (project scope):

```powershell
claude mcp add java-leak-hunter --scope project -- python -m java_leak_hunter_mcp.server
```

7. Verify MCP registration:

```powershell
claude mcp list
```

Note for Windows deep mode:
- If async-profiler is missing, deep analysis automatically falls back to `JFR + heap dump + MAT`.
- If MAT is missing, deep mode will fail with installation guidance.

## Run in Claude Code

This repo includes:
- `.claude/commands/leak-scan.md`
- `.claude/commands/leak-deep.md`

Inside Claude Code:
- `/leak-scan <pid-or-pattern>`
- `/leak-deep <pid-or-pattern>`

Examples:
- `/leak-scan my-service`
- `/leak-deep 12345`

## How to Use (Leak Investigation Workflow)

Use this sequence when you suspect a leak in a running Java app (including GUI apps):

1. Start the target app normally.
- Example: launch from IDE, app launcher, or startup script.
- Wait until the app is fully initialized.

2. Reproduce the suspicious behavior.
- For GUI apps, perform the user flow that likely leaks memory (open/close views, repeated actions, long-running sessions).

3. Run a conservative scan in Claude Code.
- Use process pattern:
  - `/leak-scan MyGuiApp`
- Or use explicit PID:
  - `/leak-scan 12345`

4. Check scan output.
- Focus on `Verdict`, `Confidence`, `Key Evidence`, and `Suspect Types`.
- If confidence is low but you still observe memory growth, continue with deep analysis.

5. Run deep forensics.
- `/leak-deep <pid-or-pattern>`
- This collects JFR, heap dump, and MAT suspects report.
- If async-profiler is unavailable (common on Windows), the workflow continues with JFR + MAT fallback.

6. Fix and verify.
- Apply remediation (for example: listener cleanup, bounded caches, lifecycle unsubscription).
- Restart the app and rerun `/leak-scan` (and `/leak-deep` if needed).
- Compare verdict/confidence and suspect classes before vs. after.

7. Keep artifacts for evidence.
- Use artifact paths from the report (`.jfr`, `.hprof`, MAT report output) for team review and regression tracking.

## Optional CLI Workflow (outside Claude Code)

macOS/Linux:

```bash
source .venv/bin/activate
leak-workflow --mode scan --match your-app
leak-workflow --mode deep --pid 12345 --output json
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
leak-workflow --mode scan --match your-app
leak-workflow --mode deep --pid 12345 --output json
```

## Validation

Run tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Example Java scenarios are available in `examples/java-scenarios`.
