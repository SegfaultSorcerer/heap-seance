---
description: Force full Java leak forensics with JFR, heap dump, MAT, and async-profiler. Use when /leak-scan flagged suspicious growth, when you want deep analysis regardless of scan results, or when investigating a known OOM with retained object evidence. Triggers on phrases like "deep leak analysis", "heap dump", "dominator tree", "who retains", or "force forensics".
allowed-tools: Read,mcp__heap_seance
---

Run full deep Java leak forensics for `$ARGUMENTS`.

Interpret `$ARGUMENTS` as either a PID (integer) or a process name/pattern (string).

This command runs deep evidence collection **unconditionally** — it does not wait for scan signals to justify escalation. Use it when you already suspect a leak or want comprehensive evidence.

## Step 1: Resolve target process

- If `$ARGUMENTS` is an integer, use it directly as PID.
- If `$ARGUMENTS` is empty, call `java_list_processes()` and list all discovered JVMs so the user can choose. Do not pick one silently.
- If `$ARGUMENTS` is a string, call `java_list_processes()` and match by substring against each process `display` field (case-insensitive). If exactly one process matches, use it. If multiple match, list them and ask the user to narrow down. If none match, report this and stop.

## Step 2: Capture baseline signals

These establish the growth and GC context that deep tools will corroborate or refute.

1. Collect 3 histogram samples with `java_class_histogram(pid, live_only=true)`. **Between each sample, ask the user to perform the suspected leaking action** in their application (e.g., open/close a view, send requests, load/discard data) and confirm when done. Without exercising the app between snapshots, leaks stay invisible. This gives the monotonic growth baseline — classes whose retained bytes rise across all 3 snapshots are candidates.
2. Collect GC snapshot with `java_gc_snapshot(pid, interval_s=2, samples=6)`. This reveals whether old-gen is under pressure and Full GCs are occurring.

## Step 3: Deep evidence collection

Run all of these unconditionally, in sequence:

1. **JFR recording**: `java_jfr_start(pid, profile="profile", duration_s=45)` — captures allocation events, GC activity, and object count data over 45 seconds.
2. **JFR summary**: `java_jfr_summary(jfr_file)` — extracts event types and counts. Look for `jdk.ObjectCountAfterGC` events and whether growth candidate classes appear in allocation-heavy events.
3. **Heap dump**: `java_heap_dump(pid, live_only=true)` — full reachable-object snapshot. `live_only=true` triggers GC first so the dump contains only retained objects, making dominator analysis cleaner.
4. **MAT leak suspects**: `java_mat_suspects(heap_dump_file)` — runs Eclipse MAT's automated leak suspect analysis. This is the strongest signal: it identifies dominator holders, accumulation points, and retained byte chains.
5. **Allocation profile**: `java_async_alloc_profile(pid, duration_s=30)` — flame graph of allocation hot spots. Only if async-profiler is available. Useful as tie-breaker when MAT and JFR are ambiguous.

Error handling:
- If MAT is missing: **stop** and return explicit install guidance. MAT is required for deep forensics — without dominator analysis, the investigation lacks its strongest signal. Provide: "Install Eclipse MAT CLI (ParseHeapDump.sh on macOS/Linux, ParseHeapDump.bat on Windows) and set MAT_BIN if not in PATH."
- If async-profiler is missing: **continue** with JFR + MAT. Note the fallback in the report. Confidence scoring still works — async-profiler is a tie-breaker, not a gate.

## Step 4: Correlate evidence

Cross-reference all signals to build the root holder hypothesis:

- **Histogram growth candidates** identify *what* is growing.
- **GC pressure** confirms the growth is not being collected — the GC is losing the fight.
- **MAT dominator analysis** reveals *who holds* the growing objects — this is the root cause pointer.
- **JFR events** corroborate whether the growing classes appear in allocation-heavy or GC-surviving event streams.
- **Allocation profile** (if available) shows *where in the code* allocations originate — the stack trace tie-breaker.

The strongest diagnosis combines histogram growth + GC pressure + MAT holder, with JFR or allocation data as independent corroboration.

## Output format

Return exactly these sections:

```
## Verdict
probable_memory_leak | suspicious_growth | watch | no_strong_leak_signal

## Confidence
high | medium | low | none

## Root Holder Hypothesis
- Which class/object retains the growing instances (from MAT dominator analysis)
- The retention chain: holder -> field -> growing collection -> leaked instances

## Supporting Evidence
- Histogram: which classes grew, by how much, across how many samples
- GC: old-gen utilization, Full GC count, slope direction
- MAT: suspect lines, retained byte counts
- JFR: corroborating event types (if relevant)
- Allocation profile: hot allocation sites (if available)

## Artifacts
- JFR recording path
- Heap dump path
- MAT report path
- Allocation profile path (if generated)

## Remediation Hypotheses
- Concrete fix suggestions based on the root holder (e.g., "add eviction policy to cache X", "unregister listener in onDestroy", "use WeakReference for observer pattern")
- Prioritized by confidence

## Verification Plan
- Steps to confirm the fix worked: re-run /leak-scan, compare verdict/confidence, check that suspect classes no longer show monotonic growth
```

## Confidence policy

- `high`: monotonic growth + GC pressure + at least one of (MAT holder signal, JFR corroboration). Two independent strong signals minimum.
- `medium`: monotonic growth + GC pressure, but MAT/JFR did not produce clear corroboration.
- `low`: growth signal present but GC is not under pressure — could be normal load.
- `none`: no evidence of a leak despite full forensics.

Never output `high` confidence without at least two independent strong signals. Histogram growth alone is not sufficient — applications legitimately grow caches, pools, and buffers under load.
