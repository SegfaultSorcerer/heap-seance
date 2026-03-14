---
description: Conservative Java leak scan with balanced escalation
allowed-tools: Read,mcp__heap_seance
---

Run a conservative Java leak scan for `$ARGUMENTS`.

Interpret `$ARGUMENTS` as either PID (integer) or process match pattern.

Workflow:
1. Resolve target process:
   - If integer, use as PID.
   - Else call `java_list_processes()` and pick the best match by substring in `display`.
2. Collect 3 histogram samples with `java_class_histogram(pid, live_only=true)`.
3. Collect GC signal with `java_gc_snapshot(pid, interval_s=2, samples=6)`.
4. Determine leak suspicion:
   - Monotonic growth candidate = class bytes non-decreasing over 3 samples and growth >= 1_000_000 bytes.
   - GC pressure = `max_oldgen_utilization >= 80` AND `full_gc_delta >= 1` AND `oldgen_slope > 0`.
5. Escalate to deep forensics only if both conditions are true:
   - `java_jfr_start(pid, profile="profile", duration_s=45)`
   - `java_jfr_summary(jfr_file)`
   - `java_heap_dump(pid, live_only=true)`
   - `java_mat_suspects(heap_dump_file)`
   - `java_async_alloc_profile(pid, duration_s=30)` (optional tie-breaker if available)
6. If MAT is unavailable, stop with actionable install guidance.
7. If async-profiler is unavailable (common on Windows), continue with JFR + MAT and mention fallback in the report.

Output exactly these sections:
- Verdict
- Confidence
- Key Evidence
- Suspect Types (if any)
- Artifacts
- Next Steps

Confidence policy:
- `high`: monotonic growth + gc pressure + MAT holder signal, supported by JFR or allocation profile.
- `medium`: monotonic growth + gc pressure.
- `low`: only weak growth signal.
- `none`: no strong leak evidence.
