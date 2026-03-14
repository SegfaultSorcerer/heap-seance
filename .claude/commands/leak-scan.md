---
description: Conservative Java memory leak scan. Use when investigating memory growth, OOM errors, heap pressure, or suspicious GC behavior in a running JVM process. Triggers on phrases like "memory leak", "heap grows", "OutOfMemoryError", "GC thrashing", or "objects not collected".
allowed-tools: Read,mcp__heap_seance
---

Run a conservative Java leak scan for `$ARGUMENTS`.

Interpret `$ARGUMENTS` as either a PID (integer) or a process name/pattern (string).

## Step 1: Resolve target process

- If `$ARGUMENTS` is an integer, use it directly as PID.
- If `$ARGUMENTS` is empty, call `java_list_processes()` and list all discovered JVMs so the user can choose. Do not pick one silently.
- If `$ARGUMENTS` is a string, call `java_list_processes()` and match by substring against each process `display` field (case-insensitive). If exactly one process matches, use it. If multiple match, list them and ask the user to narrow down. If none match, report this and stop.

## Step 2: Collect 3 histogram samples

Call `java_class_histogram(pid, live_only=true)` three times. **Between each sample, ask the user to perform the suspected leaking action** in their application (e.g., open/close a view, send requests, load/discard data) and confirm when done. This is critical — without exercising the app between snapshots, leaks stay invisible because no new objects are created along the leaking path.

Prompt the user like this:
- After sample 1: "Histogram sample 1 collected. Please perform the action you suspect is leaking (e.g., open/close views, trigger requests), then let me know when you're done."
- After sample 2: "Histogram sample 2 collected. Please repeat the same action once more, then confirm."
- After sample 3: proceed to Step 3.

Why 3 samples: detecting monotonic growth requires at least 3 data points. The `live_only=true` flag triggers a GC before each snapshot, so only reachable objects are counted — this filters out garbage that would skew the signal.

## Step 3: Collect GC pressure snapshot

Call `java_gc_snapshot(pid, interval_s=2, samples=6)`.

This samples `jstat -gcutil` over ~12 seconds to capture old-gen utilization trend and Full GC activity.

## Step 4: Evaluate signals

Two independent signals determine whether escalation is warranted:

**Monotonic growth candidate**: a class whose retained bytes are non-decreasing across all 3 histogram samples AND whose total growth is >= 1,000,000 bytes. Classes that shrink between any two samples are not candidates — the threshold filters noise from normal allocation churn.

**GC pressure**: `max_oldgen_utilization >= 80%` AND `full_gc_delta >= 1` AND `oldgen_slope > 0`. This means old-gen is nearly full, Full GCs are happening, and utilization is still rising — the GC is fighting but losing.

## Step 5: Decide on escalation

- If **both** signals are present: escalate to deep forensics (continue to Step 6).
- If **only growth** is present: report as `watch` / `low` confidence. Recommend re-scanning under sustained load or running `/leak-deep` manually if operationally suspicious.
- If **neither** signal is present: report as `no_strong_leak_signal` / `none` confidence.

Do NOT escalate on a single signal alone — that is the conservative policy of this scan.

## Step 6: Deep forensics (only when escalated)

Run these in sequence:

1. `java_jfr_start(pid, profile="profile", duration_s=45)` — captures allocation and GC events.
2. `java_jfr_summary(jfr_file)` — checks if growth candidates appear in JFR event data.
3. `java_heap_dump(pid, live_only=true)` — full heap snapshot for dominator analysis.
4. `java_mat_suspects(heap_dump_file)` — identifies retained holders and accumulation points.
5. `java_async_alloc_profile(pid, duration_s=30)` — optional allocation flame graph as tie-breaker.

Error handling:
- If MAT is missing: stop and return explicit install guidance (`ParseHeapDump.sh/.bat` from Eclipse MAT CLI). Do not continue without MAT — it is the strongest signal source.
- If async-profiler is missing (common on Windows): continue with JFR + MAT and note the fallback in the report. Confidence scoring still works — async-profiler is a tie-breaker, not a requirement.

## Output format

Return exactly these sections:

```
## Verdict
probable_memory_leak | suspicious_growth | watch | no_strong_leak_signal

## Confidence
high | medium | low | none

## Key Evidence
- Bullet points summarizing what was observed (growth classes, GC stats, MAT findings if escalated)

## Suspect Types
- List of class names showing monotonic growth with byte counts (omit section if no candidates)

## Artifacts
- Paths to .jfr, .hprof, MAT report if deep forensics ran (omit section if scan-only)

## Next Steps
- Actionable recommendations based on the verdict
```

## Confidence policy

- `high`: monotonic growth + GC pressure + MAT holder signal, corroborated by JFR or allocation profile. Requires at least two independent strong signals beyond histogram growth.
- `medium`: monotonic growth + GC pressure, but no MAT/JFR corroboration yet.
- `low`: growth signal only, no GC pressure. Could be normal load behavior.
- `none`: no evidence of a leak.

Never claim `high` confidence from histogram data alone — histogram growth without independent corroboration could be normal application behavior under load.
