from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_STATUS = {"ok", "warn", "error"}
VALID_CONFIDENCE = {"none", "low", "medium", "high"}


@dataclass(slots=True)
class ToolResult:
    status: str
    evidence: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    confidence: str = "none"
    next_recommended_action: str = ""
    raw_artifact_path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status if self.status in VALID_STATUS else "error"
        confidence = self.confidence if self.confidence in VALID_CONFIDENCE else "none"
        payload: dict[str, Any] = {
            "status": status,
            "evidence": self.evidence,
            "metrics": self.metrics,
            "confidence": confidence,
            "next_recommended_action": self.next_recommended_action,
            "raw_artifact_path": self.raw_artifact_path,
        }
        if self.details:
            payload["details"] = self.details
        return payload


def ok_result(
    *,
    evidence: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    confidence: str = "low",
    next_recommended_action: str = "",
    raw_artifact_path: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ToolResult(
        status="ok",
        evidence=evidence or [],
        metrics=metrics or {},
        confidence=confidence,
        next_recommended_action=next_recommended_action,
        raw_artifact_path=raw_artifact_path,
        details=details or {},
    ).to_dict()


def warn_result(
    *,
    evidence: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    confidence: str = "low",
    next_recommended_action: str = "",
    raw_artifact_path: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ToolResult(
        status="warn",
        evidence=evidence or [],
        metrics=metrics or {},
        confidence=confidence,
        next_recommended_action=next_recommended_action,
        raw_artifact_path=raw_artifact_path,
        details=details or {},
    ).to_dict()


def error_result(
    message: str,
    *,
    next_recommended_action: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ToolResult(
        status="error",
        evidence=[message],
        metrics={},
        confidence="none",
        next_recommended_action=next_recommended_action,
        raw_artifact_path=None,
        details=details or {},
    ).to_dict()
