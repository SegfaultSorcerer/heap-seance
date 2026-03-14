---
description: Force deep Java leak forensics (JFR + heap dump + MAT + async-profiler)
allowed-tools: Read,mcp__heap_seance
---

Run full deep Java leak forensics for `$ARGUMENTS`.

Interpret `$ARGUMENTS` as either PID (integer) or process match pattern.

Mandatory sequence:
1. Resolve PID (from argument directly or via `java_list_processes()`).
2. Capture baseline:
   - 3x `java_class_histogram(pid, live_only=true)`
   - `java_gc_snapshot(pid, interval_s=2, samples=6)`
3. Run deep evidence collection unconditionally:
   - `java_jfr_start(pid, profile="profile", duration_s=45)`
   - `java_jfr_summary(jfr_file)`
   - `java_heap_dump(pid, live_only=true)`
   - `java_mat_suspects(heap_dump_file)`
   - `java_async_alloc_profile(pid, duration_s=30)` when available
4. Correlate evidence:
   - histogram growth candidates
   - old-gen pressure trend
   - MAT dominator/retained holder findings
   - JFR/allocation support
5. If MAT is missing, stop and return explicit installation guidance.
6. If async-profiler is missing (especially on Windows), continue and declare JFR+MAT fallback mode.

Output exactly these sections:
- Verdict
- Confidence
- Root Holder Hypothesis
- Supporting Evidence
- Artifacts
- Remediation Hypotheses
- Verification Plan

Do not output `high` confidence without at least two independent strong signals.
