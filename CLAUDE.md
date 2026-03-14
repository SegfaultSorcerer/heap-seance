# Java Leak Hunter Project Instructions

Use this project to diagnose Java memory leaks with low false-positive bias.

## Default policy

- Prefer conservative decisions.
- Run deep forensics only when both signals are present:
  - monotonic class growth across 3 histogram samples
  - old-gen pressure despite Full GC

## Workflow

1. Resolve target process (PID or process pattern).
2. Collect 3 class histograms over time.
3. Collect GC snapshot.
4. Trigger deep forensics when thresholds are met:
   - JFR recording + summary
   - heap dump
   - MAT leak suspects
   - async-profiler allocation profile
5. Return a structured report with confidence and remediation next steps.

## Output format requirements

Always include:
- verdict (`probable_memory_leak`, `suspicious_growth`, `watch`, `no_strong_leak_signal`)
- confidence (`none`, `low`, `medium`, `high`)
- key evidence bullets
- next steps

## Tooling constraints

- If MAT or async-profiler is missing and deep forensics is required, fail explicitly and provide recovery instructions.
- Do not claim high confidence without evidence from at least two independent signals.
