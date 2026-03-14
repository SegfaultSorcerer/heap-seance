from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .parsers import (
    parse_heap_histogram,
    parse_jcmd_processes,
    parse_jfr_summary,
    parse_jstat_gcutil,
    parse_mat_suspects_output,
)
from .results import error_result, ok_result, warn_result
from .shell_tools import (
    CommandExecutionError,
    ToolingMissingError,
    ensure_success,
    require_any_binary,
    require_binary,
    run_command,
)


def _artifact_dir() -> Path:
    import tempfile

    default = str(Path(tempfile.gettempdir()) / "heap-seance")
    target = Path(os.environ.get("HEAP_SEANCE_ARTIFACT_DIR", default))
    target.mkdir(parents=True, exist_ok=True)
    return target


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _missing_tool(message: str) -> dict[str, Any]:
    return error_result(
        message,
        next_recommended_action="Install missing external tools and retry the same command.",
    )


def _command_failed(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    next_action = "Verify process permissions and command inputs, then retry."
    if "AttachNotSupportedException" in message or "doesn't respond" in message:
        next_action = (
            "Ensure target JVM runs with same OS user, wait a few seconds after startup, "
            "then retry attach-based commands."
        )
    return error_result(
        message,
        next_recommended_action=next_action,
    )


def java_list_processes() -> dict[str, Any]:
    try:
        require_binary("jcmd", "Install OpenJDK 17+ so jcmd is available.")
        output = ensure_success(run_command(["jcmd", "-l"])).stdout
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    all_processes = parse_jcmd_processes(output)
    processes = [
        process
        for process in all_processes
        if "sun.tools.jcmd.JCmd" not in process["main_class"]
    ]
    if not processes:
        processes = all_processes
    evidence = [f"Discovered {len(processes)} JVM process(es) via jcmd -l."]
    if processes:
        sample = ", ".join(str(proc["pid"]) for proc in processes[:5])
        evidence.append(f"Sample PIDs: {sample}")

    return ok_result(
        evidence=evidence,
        metrics={"process_count": len(processes), "processes": processes},
        confidence="low",
        next_recommended_action="Choose a target PID and run java_class_histogram + java_gc_snapshot.",
    )


def java_gc_snapshot(pid: int, interval_s: int = 2, samples: int = 6) -> dict[str, Any]:
    try:
        require_binary("jstat", "Install OpenJDK 17+ so jstat is available.")
        interval_ms = max(1, interval_s) * 1000
        output = ensure_success(
            run_command(["jstat", "-gcutil", str(pid), f"{interval_ms}ms", str(max(2, samples))])
        ).stdout
        parsed = parse_jstat_gcutil(output)
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    summary = parsed["summary"]
    max_oldgen = float(summary["max_oldgen_utilization"])
    full_gc_delta = float(summary["full_gc_delta"])
    oldgen_slope = float(summary["oldgen_slope"])

    evidence = [
        f"Collected {summary['sample_count']} gcutil samples for PID {pid}.",
        f"OldGen max={max_oldgen:.2f}% slope={oldgen_slope:.2f} FullGC delta={full_gc_delta:.0f}.",
    ]

    pressure = max_oldgen >= 80.0 and full_gc_delta >= 1.0 and oldgen_slope > 0.0
    confidence = "medium" if pressure else "low"

    return ok_result(
        evidence=evidence,
        metrics={
            "pid": pid,
            "series": parsed["series"],
            "summary": summary,
            "pressure_detected": pressure,
        },
        confidence=confidence,
        next_recommended_action=(
            "Correlate with 3 histogram samples and escalate to deep forensics if pressure persists."
        ),
    )


def java_class_histogram(pid: int, live_only: bool = True) -> dict[str, Any]:
    try:
        require_binary("jmap", "Install OpenJDK 17+ so jmap is available.")
        mode = "live" if live_only else "all"
        output = ensure_success(run_command(["jmap", f"-histo:{mode}", str(pid)], timeout_s=240)).stdout
        parsed = parse_heap_histogram(output)
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    top = parsed["top_classes"][:3]
    evidence = [f"Collected class histogram for PID {pid} ({mode} objects)."]
    if top:
        evidence.append(
            "Top classes: "
            + ", ".join(f"{entry['class_name']}={entry['bytes']}B" for entry in top)
        )

    return ok_result(
        evidence=evidence,
        metrics={
            "pid": pid,
            "live_only": live_only,
            "summary": parsed["summary"],
            "top_classes": parsed["top_classes"],
        },
        confidence="low",
        next_recommended_action="Take 3 samples over time and compare monotonic growth of retained classes.",
    )


def java_jfr_start(
    pid: int,
    profile: str = "profile",
    duration_s: int = 30,
    out_file: str | None = None,
) -> dict[str, Any]:
    try:
        require_binary("jcmd", "Install OpenJDK 17+ so jcmd is available.")
        path = Path(out_file) if out_file else _artifact_dir() / f"jfr-{pid}-{_timestamp()}.jfr"
        path.parent.mkdir(parents=True, exist_ok=True)

        output = ensure_success(
            run_command(
                [
                    "jcmd",
                    str(pid),
                    "JFR.start",
                    "name=HeapSeance",
                    f"settings={profile}",
                    f"duration={max(5, duration_s)}s",
                    f"filename={str(path)}",
                ],
                timeout_s=max(60, duration_s + 15),
            )
        ).stdout
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    if not path.exists():
        return warn_result(
            evidence=[
                f"JFR command executed but expected output file was not found at {path}.",
                output.strip()[:800],
            ],
            metrics={"pid": pid, "requested_file": str(path)},
            confidence="low",
            next_recommended_action="Check JFR permissions and rerun java_jfr_start with an explicit writable out_file.",
        )

    return ok_result(
        evidence=[f"Recorded JFR capture for PID {pid} at {path}.", output.strip()[:800]],
        metrics={"pid": pid, "duration_s": duration_s, "profile": profile},
        confidence="medium",
        next_recommended_action="Run java_jfr_summary on the generated recording.",
        raw_artifact_path=str(path),
    )


def java_jfr_summary(jfr_file: str) -> dict[str, Any]:
    path = Path(jfr_file)
    if not path.exists():
        return error_result(
            f"JFR file not found: {jfr_file}",
            next_recommended_action="Provide a valid .jfr file path from java_jfr_start.",
        )

    try:
        from .shell_tools import which

        jfr_bin = which("jfr")
        if jfr_bin:
            output = ensure_success(run_command([jfr_bin, "summary", str(path)], timeout_s=120)).stdout
        else:
            output = ensure_success(run_command(["jcmd", "JFR.view", str(path)], timeout_s=120)).stdout
        parsed = parse_jfr_summary(output)
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    has_object_count = parsed["contains_object_count_after_gc"]
    confidence = "medium" if has_object_count else "low"

    return ok_result(
        evidence=[f"Generated JFR summary for {path}."] + parsed["summary_lines"][:5],
        metrics={
            "contains_object_count_after_gc": has_object_count,
            "event_counts": parsed["event_counts"],
        },
        confidence=confidence,
        next_recommended_action="Correlate high-allocation events with histogram growth candidates.",
        raw_artifact_path=str(path),
    )


def java_heap_dump(pid: int, live_only: bool = True, out_file: str | None = None) -> dict[str, Any]:
    try:
        require_binary("jmap", "Install OpenJDK 17+ so jmap is available.")
        path = Path(out_file) if out_file else _artifact_dir() / f"heap-{pid}-{_timestamp()}.hprof"
        path.parent.mkdir(parents=True, exist_ok=True)

        mode = "live" if live_only else "all"
        dump_opt = f"-dump:{mode},format=b,file={str(path)}"
        output = ensure_success(run_command(["jmap", dump_opt, str(pid)], timeout_s=900)).stdout
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    if not path.exists():
        return warn_result(
            evidence=[f"Heap dump command succeeded but file is missing at {path}.", output.strip()[:800]],
            metrics={"pid": pid, "requested_file": str(path)},
            confidence="low",
            next_recommended_action="Retry with explicit writable out_file and sufficient disk space.",
        )

    return ok_result(
        evidence=[f"Heap dump created for PID {pid}: {path}"],
        metrics={"pid": pid, "size_bytes": path.stat().st_size, "live_only": live_only},
        confidence="medium",
        next_recommended_action="Run java_mat_suspects on this heap dump.",
        raw_artifact_path=str(path),
    )


def java_mat_suspects(heap_dump_file: str) -> dict[str, Any]:
    heap_path = Path(heap_dump_file)
    if not heap_path.exists():
        return error_result(
            f"Heap dump file not found: {heap_dump_file}",
            next_recommended_action="Run java_heap_dump first and pass its artifact path.",
        )

    try:
        mat_bin = os.environ.get("MAT_BIN")
        if mat_bin:
            mat_exec = mat_bin
        else:
            mat_exec = require_any_binary(
                ["ParseHeapDump.sh", "ParseHeapDump.bat", "mat"],
                "Install Eclipse MAT CLI and set MAT_BIN if binary is not in PATH.",
            )

        mat_env: dict[str, str] | None = None
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            path_sep = ";" if os.name == "nt" else ":"
            java_bin = os.path.join(java_home, "bin")
            mat_env = {
                "JAVA_HOME": java_home,
                "PATH": java_bin + path_sep + os.environ.get("PATH", ""),
            }

        result = run_command(
            [mat_exec, str(heap_path), "org.eclipse.mat.api:suspects"],
            timeout_s=1200,
            env=mat_env,
        )

        if result.returncode != 0:
            raise CommandExecutionError(
                f"MAT suspects analysis failed with code {result.returncode}. stderr: {result.stderr.strip()[:1000]}"
            )

        parsed = parse_mat_suspects_output(result.stdout + "\n" + result.stderr)
    except ToolingMissingError as exc:
        return _missing_tool(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    report_path = parsed["report_paths"][0] if parsed["report_paths"] else None
    confidence = "high" if parsed["suspect_lines"] else "medium"

    return ok_result(
        evidence=[f"MAT suspects analysis completed for {heap_path}."] + parsed["suspect_lines"][:5],
        metrics={
            "suspect_line_count": len(parsed["suspect_lines"]),
            "report_paths": parsed["report_paths"],
        },
        confidence=confidence,
        next_recommended_action="Correlate MAT dominators with class histogram and allocation profile.",
        raw_artifact_path=report_path,
    )


def java_async_alloc_profile(
    pid: int,
    duration_s: int = 30,
    out_file: str | None = None,
) -> dict[str, Any]:
    try:
        async_bin = os.environ.get("ASYNC_PROFILER_BIN")
        if async_bin:
            profiler = async_bin
        else:
            profiler = require_any_binary(
                ["async-profiler", "profiler.sh", "asprof"],
                "Install async-profiler and set ASYNC_PROFILER_BIN if not in PATH.",
            )

        path = Path(out_file) if out_file else _artifact_dir() / f"alloc-{pid}-{_timestamp()}.html"
        path.parent.mkdir(parents=True, exist_ok=True)

        output = ensure_success(
            run_command(
                [
                    profiler,
                    "-e",
                    "alloc",
                    "-d",
                    str(max(5, duration_s)),
                    "-f",
                    str(path),
                    str(pid),
                ],
                timeout_s=max(60, duration_s + 20),
            )
        ).stdout
    except ToolingMissingError as exc:
        return _missing_tool(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _command_failed(exc)

    if not path.exists():
        return warn_result(
            evidence=[
                f"async-profiler finished but output file is missing at {path}.",
                output.strip()[:800],
            ],
            metrics={"pid": pid, "requested_file": str(path)},
            confidence="low",
            next_recommended_action="Validate profiler permissions and rerun with explicit output path.",
        )

    return ok_result(
        evidence=[f"Allocation profile generated for PID {pid}: {path}"],
        metrics={"pid": pid, "duration_s": duration_s},
        confidence="medium",
        next_recommended_action="Use this profile as tie-breaker if MAT and histogram are inconclusive.",
        raw_artifact_path=str(path),
    )
