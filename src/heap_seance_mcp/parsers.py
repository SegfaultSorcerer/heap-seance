from __future__ import annotations

import re
from typing import Any

PROCESS_LINE = re.compile(r"^\s*(\d+)\s+([^\s]+)(?:\s+(.*))?$")
HISTO_LINE = re.compile(r"^\s*\d+:\s+(\d+)\s+(\d+)\s+(.+)$")
TOTAL_LINE = re.compile(r"^\s*Total\s+(\d+)\s+(\d+)", re.IGNORECASE)


def parse_jcmd_processes(text: str) -> list[dict[str, Any]]:
    processes: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = PROCESS_LINE.match(line)
        if not match:
            continue
        pid = int(match.group(1))
        main_class = match.group(2)
        args = (match.group(3) or "").strip()
        processes.append(
            {
                "pid": pid,
                "main_class": main_class,
                "args": args,
                "display": f"{pid} {main_class} {args}".strip(),
            }
        )
    return processes


def parse_jstat_gcutil(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Expected jstat output with header and at least one sample line")

    header = lines[0].split()
    samples: list[dict[str, float]] = []

    for line in lines[1:]:
        parts = line.split()
        if len(parts) != len(header):
            continue

        row: dict[str, float] = {}
        for key, value in zip(header, parts):
            row[key] = float(value.replace(",", "."))
        samples.append(row)

    if not samples:
        raise ValueError("No parseable jstat samples found")

    oldgen_series = [sample.get("O", 0.0) for sample in samples]
    full_gc_series = [sample.get("FGC", 0.0) for sample in samples]
    oldgen_slope = oldgen_series[-1] - oldgen_series[0]

    return {
        "header": header,
        "samples": samples,
        "series": {
            "oldgen_utilization": oldgen_series,
            "full_gc_count": full_gc_series,
        },
        "summary": {
            "sample_count": len(samples),
            "max_oldgen_utilization": max(oldgen_series),
            "oldgen_slope": oldgen_slope,
            "full_gc_delta": full_gc_series[-1] - full_gc_series[0],
        },
    }


def parse_heap_histogram(text: str, *, top_n: int = 25) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    total_instances = 0
    total_bytes = 0

    for line in text.splitlines():
        total_match = TOTAL_LINE.match(line)
        if total_match:
            total_instances = int(total_match.group(1))
            total_bytes = int(total_match.group(2))
            continue

        match = HISTO_LINE.match(line)
        if not match:
            continue

        instances = int(match.group(1))
        bytes_used = int(match.group(2))
        class_name = match.group(3).strip()
        entries.append(
            {
                "class_name": class_name,
                "instances": instances,
                "bytes": bytes_used,
            }
        )

    if total_bytes == 0 and entries:
        total_bytes = sum(entry["bytes"] for entry in entries)
    if total_instances == 0 and entries:
        total_instances = sum(entry["instances"] for entry in entries)

    return {
        "summary": {
            "entry_count": len(entries),
            "total_instances": total_instances,
            "total_bytes": total_bytes,
        },
        "top_classes": entries[:top_n],
        "all_classes": entries,
    }


def parse_jfr_summary(text: str, *, top_n: int = 15) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]

    event_counts: list[dict[str, Any]] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        if not parts[-1].isdigit() or not parts[-2].isdigit():
            continue
        event_name = " ".join(parts[:-2])
        event_counts.append(
            {
                "event": event_name,
                "count": int(parts[-2]),
                "size": int(parts[-1]),
            }
        )

    return {
        "summary_lines": lines[:top_n],
        "event_counts": event_counts[:top_n],
        "contains_object_count_after_gc": any(
            "jdk.ObjectCountAfterGC" in line for line in lines
        ),
    }


def parse_mat_suspects_output(text: str) -> dict[str, Any]:
    suspects = []
    html_paths = re.findall(r"(/[\w./-]+\.html)", text)

    for line in text.splitlines():
        stripped = line.strip()
        if "leak" in stripped.lower() or "suspect" in stripped.lower():
            suspects.append(stripped)

    return {
        "suspect_lines": suspects[:20],
        "report_paths": html_paths,
    }
