from __future__ import annotations

from typing import Any


def monotonic_growth_candidates(
    histograms: list[dict[str, Any]],
    *,
    min_growth_bytes: int = 1_000_000,
    min_samples: int = 3,
) -> list[dict[str, Any]]:
    if len(histograms) < min_samples:
        return []

    class_series: dict[str, list[int]] = {}
    sample_count = len(histograms)

    for sample_index, histogram in enumerate(histograms):
        totals = {
            entry["class_name"]: int(entry["bytes"])
            for entry in histogram.get("top_classes", [])
        }

        # Keep per-class series aligned to every sample index.
        for class_name in list(class_series):
            class_series[class_name].append(totals.get(class_name, 0))

        for class_name, bytes_used in totals.items():
            if class_name in class_series:
                continue
            class_series[class_name] = [0] * sample_index + [bytes_used]
    candidates: list[dict[str, Any]] = []

    for class_name, series in class_series.items():
        padded = series + [0] * (sample_count - len(series))
        monotonic = all(padded[idx] <= padded[idx + 1] for idx in range(sample_count - 1))
        growth = padded[-1] - padded[0]
        if monotonic and growth >= min_growth_bytes and padded[-1] > 0:
            candidates.append(
                {
                    "class_name": class_name,
                    "bytes_series": padded,
                    "growth_bytes": growth,
                }
            )

    candidates.sort(key=lambda item: item["growth_bytes"], reverse=True)
    return candidates


def gc_pressure_signal(gc_summary: dict[str, Any]) -> dict[str, Any]:
    max_oldgen = float(gc_summary.get("max_oldgen_utilization", 0.0))
    full_gc_delta = float(gc_summary.get("full_gc_delta", 0.0))
    oldgen_slope = float(gc_summary.get("oldgen_slope", 0.0))

    pressure = max_oldgen >= 80.0 and full_gc_delta >= 1.0 and oldgen_slope > 0.0

    return {
        "pressure_detected": pressure,
        "max_oldgen_utilization": max_oldgen,
        "full_gc_delta": full_gc_delta,
        "oldgen_slope": oldgen_slope,
    }


def mat_holder_signal(mat_result: dict[str, Any]) -> dict[str, Any]:
    suspect_lines = [line.lower() for line in mat_result.get("suspect_lines", [])]
    has_holder = any("retained" in line or "accumulat" in line or "dominator" in line for line in suspect_lines)
    return {
        "holder_detected": has_holder,
        "suspect_line_count": len(suspect_lines),
    }


def jfr_support_signal(jfr_summary: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    joined = "\n".join(jfr_summary.get("summary_lines", [])).lower()
    matched = 0
    for candidate in candidates:
        class_name = candidate["class_name"].split()[-1].split(".")[-1].lower()
        if class_name and class_name in joined:
            matched += 1
    return {
        "supports_histogram_candidates": matched > 0,
        "matched_candidate_count": matched,
    }


def overall_confidence(
    *,
    monotonic_candidates: list[dict[str, Any]],
    gc_pressure: dict[str, Any],
    mat_holder: dict[str, Any] | None = None,
    jfr_support: dict[str, Any] | None = None,
) -> dict[str, Any]:
    has_growth = bool(monotonic_candidates)
    has_gc_pressure = bool(gc_pressure.get("pressure_detected"))
    has_mat = bool(mat_holder and mat_holder.get("holder_detected"))
    has_jfr_support = bool(jfr_support and jfr_support.get("supports_histogram_candidates"))

    if has_growth and has_gc_pressure and has_mat and has_jfr_support:
        confidence = "high"
        verdict = "probable_memory_leak"
    elif has_growth and has_gc_pressure and (has_mat or has_jfr_support):
        confidence = "high"
        verdict = "probable_memory_leak"
    elif has_growth and has_gc_pressure:
        confidence = "medium"
        verdict = "suspicious_growth"
    elif has_growth:
        confidence = "low"
        verdict = "watch"
    else:
        confidence = "none"
        verdict = "no_strong_leak_signal"

    return {
        "confidence": confidence,
        "verdict": verdict,
        "signals": {
            "monotonic_growth": has_growth,
            "gc_pressure": has_gc_pressure,
            "mat_holder": has_mat,
            "jfr_support": has_jfr_support,
        },
    }
