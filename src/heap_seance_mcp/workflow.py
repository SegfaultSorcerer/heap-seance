from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .heuristics import (
    gc_pressure_signal,
    jfr_support_signal,
    mat_holder_signal,
    monotonic_growth_candidates,
    overall_confidence,
)
from .shell_tools import ToolingMissingError, require_any_binary, require_binary
from .tools import (
    java_async_alloc_profile,
    java_class_histogram,
    java_gc_snapshot,
    java_heap_dump,
    java_jfr_start,
    java_jfr_summary,
    java_list_processes,
    java_mat_suspects,
)


def _as_error(message: str, next_action: str) -> dict[str, Any]:
    return {
        "status": "error",
        "evidence": [message],
        "metrics": {},
        "confidence": "none",
        "next_recommended_action": next_action,
        "raw_artifact_path": None,
    }


def _ensure_core_tools() -> None:
    require_binary("jcmd", "Install OpenJDK 17+.")
    require_binary("jmap", "Install OpenJDK 17+.")
    require_binary("jstat", "Install OpenJDK 17+.")


def _ensure_deep_tools() -> bool:
    mat_override = Path(os.environ["MAT_BIN"]) if "MAT_BIN" in os.environ else None
    async_override = (
        Path(os.environ["ASYNC_PROFILER_BIN"])
        if "ASYNC_PROFILER_BIN" in os.environ
        else None
    )

    if mat_override and mat_override.exists():
        pass
    else:
        require_any_binary(
            ["ParseHeapDump.sh", "ParseHeapDump.bat", "mat"],
            "Install Eclipse MAT CLI and set MAT_BIN if needed.",
        )

    if async_override and async_override.exists():
        return True

    try:
        require_any_binary(
            ["async-profiler", "profiler.sh", "asprof"],
            "Install async-profiler and set ASYNC_PROFILER_BIN if needed.",
        )
        return True
    except ToolingMissingError:
        return False


def _pick_pid(pid: int | None, match: str | None) -> tuple[int | None, list[str]]:
    evidence: list[str] = []
    if pid is not None:
        evidence.append(f"Using explicit PID {pid}.")
        return pid, evidence

    proc_result = java_list_processes()
    if proc_result["status"] != "ok":
        return None, proc_result["evidence"]

    processes = proc_result["metrics"].get("processes", [])
    if not processes:
        return None, ["No running JVM processes found."]

    if not match:
        chosen = processes[0]["pid"]
        evidence.append(
            f"No --match provided; selected first JVM process PID {chosen}."
        )
        return chosen, evidence

    filtered = [
        process
        for process in processes
        if match.lower() in process["display"].lower()
    ]
    if not filtered:
        return None, [f"No JVM process matched pattern '{match}'."]

    chosen = filtered[0]["pid"]
    evidence.append(
        f"Matched {len(filtered)} process(es) for '{match}', selected PID {chosen}."
    )
    return chosen, evidence


def run_workflow(
    *,
    mode: str,
    pid: int | None,
    match: str | None,
    sample_gap_s: int,
    gc_interval_s: int,
    gc_samples: int,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "ok",
        "confidence": "none",
        "verdict": "unknown",
        "evidence": [],
        "signals": {},
        "artifacts": {},
        "next_steps": [],
    }

    try:
        _ensure_core_tools()
    except ToolingMissingError as exc:
        return _as_error(str(exc), "Install required JDK tools and retry.")

    resolved_pid, pick_evidence = _pick_pid(pid, match)
    report["evidence"].extend(pick_evidence)
    if resolved_pid is None:
        return _as_error(
            "Unable to resolve JVM target process.",
            "Use --pid or --match with a running Java process.",
        )

    histograms: list[dict[str, Any]] = []
    for index in range(3):
        histo = java_class_histogram(pid=resolved_pid, live_only=True)
        if histo["status"] != "ok":
            return histo
        histograms.append(histo["metrics"])
        report["evidence"].append(f"Histogram sample {index + 1}/3 collected.")
        if index < 2:
            time.sleep(max(1, sample_gap_s))

    gc_data = java_gc_snapshot(
        pid=resolved_pid,
        interval_s=max(1, gc_interval_s),
        samples=max(3, gc_samples),
    )
    if gc_data["status"] != "ok":
        return gc_data

    monotonic = monotonic_growth_candidates(histograms)
    gc_signal = gc_pressure_signal(gc_data["metrics"]["summary"])

    report["signals"]["monotonic_growth_candidates"] = monotonic[:8]
    report["signals"]["gc_pressure"] = gc_signal

    deep_needed = mode == "deep" or (
        bool(monotonic) and bool(gc_signal.get("pressure_detected"))
    )

    jfr_signal: dict[str, Any] | None = None
    mat_signal: dict[str, Any] | None = None

    if deep_needed:
        try:
            async_available = _ensure_deep_tools()
        except ToolingMissingError as exc:
            return _as_error(
                str(exc),
                "Deep forensics requires MAT. Install MAT CLI (ParseHeapDump.sh/.bat) and retry.",
            )

        report["signals"]["async_profiler_available"] = async_available
        if not async_available:
            report["evidence"].append(
                "async-profiler not detected. Continuing deep analysis with JFR + MAT fallback."
            )

        jfr_result = java_jfr_start(pid=resolved_pid, profile="profile", duration_s=45)
        if jfr_result["status"] != "ok":
            return jfr_result
        report["artifacts"]["jfr"] = jfr_result["raw_artifact_path"]

        jfr_summary = java_jfr_summary(jfr_result["raw_artifact_path"])
        if jfr_summary["status"] != "ok":
            return jfr_summary
        jfr_signal = jfr_support_signal(jfr_summary["metrics"], monotonic)
        report["signals"]["jfr_support"] = jfr_signal

        heap_result = java_heap_dump(pid=resolved_pid, live_only=True)
        if heap_result["status"] != "ok":
            return heap_result
        report["artifacts"]["heap_dump"] = heap_result["raw_artifact_path"]

        mat_result = java_mat_suspects(heap_result["raw_artifact_path"])
        if mat_result["status"] != "ok":
            return mat_result
        report["artifacts"]["mat"] = mat_result.get("raw_artifact_path")
        mat_signal = mat_holder_signal(mat_result["metrics"])
        report["signals"]["mat_holder"] = mat_signal

        if async_available:
            alloc_result = java_async_alloc_profile(pid=resolved_pid, duration_s=30)
            if alloc_result["status"] == "ok":
                report["artifacts"]["async_alloc_profile"] = alloc_result["raw_artifact_path"]
            else:
                report["evidence"].append(
                    "async-profiler execution failed; falling back to JFR+MAT evidence."
                )
                report["signals"]["async_profiler_runtime_error"] = True

    assessment = overall_confidence(
        monotonic_candidates=monotonic,
        gc_pressure=gc_signal,
        mat_holder=mat_signal,
        jfr_support=jfr_signal,
    )

    report["confidence"] = assessment["confidence"]
    report["verdict"] = assessment["verdict"]
    report["signals"].update(assessment["signals"])

    if assessment["confidence"] == "high":
        report["next_steps"] = [
            "Inspect dominant holders from MAT report and map them to source owners.",
            "Apply bounded caches/weak references or lifecycle cleanup where holders retain growth classes.",
            "Re-run /leak-scan to verify signal reduction.",
        ]
    elif assessment["confidence"] == "medium":
        report["next_steps"] = [
            "Run /leak-deep to gather MAT and allocation evidence.",
            "Track growth candidates over a longer window (5-10 samples).",
        ]
    else:
        report["next_steps"] = [
            "Keep this as watch state and re-check under peak load.",
            "If memory still climbs operationally, trigger /leak-deep manually.",
        ]

    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Heap Seance Report",
        "",
        f"- Status: `{report.get('status', 'unknown')}`",
        f"- Verdict: `{report.get('verdict', 'unknown')}`",
        f"- Confidence: `{report.get('confidence', 'none')}`",
    ]

    evidence = report.get("evidence", [])
    if evidence:
        lines.extend(["", "## Evidence"])
        for item in evidence:
            lines.append(f"- {item}")

    signals = report.get("signals", {})
    if signals:
        lines.extend(["", "## Signals", "```json", json.dumps(signals, indent=2), "```"])

    artifacts = report.get("artifacts", {})
    if artifacts:
        lines.extend(["", "## Artifacts"])
        for key, value in artifacts.items():
            lines.append(f"- {key}: `{value}`")

    next_steps = report.get("next_steps", [])
    if next_steps:
        lines.extend(["", "## Next Steps"])
        for item in next_steps:
            lines.append(f"- {item}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Heap Seance workflow")
    parser.add_argument("--mode", choices=["scan", "deep"], default="scan")
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--match", type=str, default=None)
    parser.add_argument("--sample-gap-s", type=int, default=6)
    parser.add_argument("--gc-interval-s", type=int, default=2)
    parser.add_argument("--gc-samples", type=int, default=6)
    parser.add_argument("--output", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--json-out", type=str, default=None)
    args = parser.parse_args()

    report = run_workflow(
        mode=args.mode,
        pid=args.pid,
        match=args.match,
        sample_gap_s=args.sample_gap_s,
        gc_interval_s=args.gc_interval_s,
        gc_samples=args.gc_samples,
    )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.output == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))

    if report.get("status") == "error":
        sys.exit(2)


if __name__ == "__main__":
    main()
