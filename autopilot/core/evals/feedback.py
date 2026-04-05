"""Structured evaluation feedback persistence for runtime review outcomes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import IterationRecord


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def feedback_path(config: AutopilotConfig, project_id: str) -> Path:
    return config.autopilot_home / "evals" / "feedback" / f"{project_id}.jsonl"


def read_feedback_records(
    config: AutopilotConfig,
    project_id: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    path = feedback_path(config, project_id)
    if not path.exists():
        return []
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if limit is not None and limit > 0:
        return records[-limit:]
    return records


def append_feedback_record(
    config: AutopilotConfig,
    project_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "feedback_id": str(record.get("feedback_id") or ""),
        "timestamp": record.get("timestamp") or _utcnow_iso(),
        "project_id": project_id,
        **record,
    }
    path = feedback_path(config, project_id)
    existing_ids = {str(item.get("feedback_id") or "") for item in read_feedback_records(config, project_id)}
    if payload["feedback_id"] and payload["feedback_id"] in existing_ids:
        return payload
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def _feedback_id(
    *,
    project_id: str,
    run_id: str,
    story_id: int,
    iteration: int,
    kind: str,
    discriminator: str,
) -> str:
    raw = f"{project_id}:{run_id}:{story_id}:{iteration}:{kind}:{discriminator}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def record_iteration_feedback(
    config: AutopilotConfig,
    project_id: str,
    *,
    run_id: str,
    iteration_record: IterationRecord,
) -> list[dict[str, Any]]:
    """Persist structured feedback/eval artifacts for one iteration."""

    written: list[dict[str, Any]] = []
    story_id = int(iteration_record.story_id)
    iteration = int(iteration_record.iteration)
    timestamp = _utcnow_iso()

    critic_feedback = str(iteration_record.critic_feedback or "").strip()
    if critic_feedback:
        written.append(
            append_feedback_record(
                config,
                project_id,
                {
                    "feedback_id": _feedback_id(
                        project_id=project_id,
                        run_id=run_id,
                        story_id=story_id,
                        iteration=iteration,
                        kind="critic_feedback",
                        discriminator=critic_feedback,
                    ),
                    "timestamp": timestamp,
                    "run_id": run_id,
                    "story_id": story_id,
                    "iteration": iteration,
                    "kind": "critic_feedback",
                    "severity": "error" if iteration_record.critic_approved is False else "info",
                    "summary": critic_feedback,
                    "approved": bool(iteration_record.critic_approved),
                },
            )
        )

    if bool(iteration_record.quality_regression):
        written.append(
            append_feedback_record(
                config,
                project_id,
                {
                    "feedback_id": _feedback_id(
                        project_id=project_id,
                        run_id=run_id,
                        story_id=story_id,
                        iteration=iteration,
                        kind="quality_regression",
                        discriminator=str(iteration_record.regression_summary or "quality_regression"),
                    ),
                    "timestamp": timestamp,
                    "run_id": run_id,
                    "story_id": story_id,
                    "iteration": iteration,
                    "kind": "quality_regression",
                    "severity": "error",
                    "summary": str(iteration_record.regression_summary or "Quality regression detected."),
                    "approved": False,
                },
            )
        )

    judge_verdict = str(iteration_record.judge_verdict or "").strip().upper()
    if judge_verdict:
        written.append(
            append_feedback_record(
                config,
                project_id,
                {
                    "feedback_id": _feedback_id(
                        project_id=project_id,
                        run_id=run_id,
                        story_id=story_id,
                        iteration=iteration,
                        kind="judge_outcome",
                        discriminator=judge_verdict,
                    ),
                    "timestamp": timestamp,
                    "run_id": run_id,
                    "story_id": story_id,
                    "iteration": iteration,
                    "kind": "judge_outcome",
                    "severity": "error" if judge_verdict != "PASS" else "success",
                    "summary": str(iteration_record.judge_summary or judge_verdict),
                    "approved": judge_verdict == "PASS",
                    "judge_pack": str(iteration_record.judge_pack or ""),
                    "judge_verdict": judge_verdict,
                    "judge_findings": list(iteration_record.judge_findings or []),
                },
            )
        )

    for review_result in list(iteration_record.review_results or []):
        feedback = str(getattr(review_result, "feedback", "") or "").strip()
        if not feedback and bool(getattr(review_result, "approved", False)):
            continue
        phase = str(getattr(review_result, "phase", "") or "review")
        written.append(
            append_feedback_record(
                config,
                project_id,
                {
                    "feedback_id": _feedback_id(
                        project_id=project_id,
                        run_id=run_id,
                        story_id=story_id,
                        iteration=iteration,
                        kind="review_phase",
                        discriminator=phase,
                    ),
                    "timestamp": timestamp,
                    "run_id": run_id,
                    "story_id": story_id,
                    "iteration": iteration,
                    "kind": "review_phase",
                    "phase": phase,
                    "severity": "error" if not bool(getattr(review_result, "approved", False)) else "info",
                    "summary": feedback or f"{phase} approved",
                    "approved": bool(getattr(review_result, "approved", False)),
                    "verification_checks": [
                        {
                            "name": getattr(check, "name", ""),
                            "command": getattr(check, "command", ""),
                            "status": getattr(check, "status", ""),
                        }
                        for check in list(getattr(review_result, "verification_checks", []) or [])
                    ],
                },
            )
        )

    return written


def build_feedback_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts_by_kind = Counter(str(record.get("kind") or "unknown") for record in records)
    judge_outcomes = Counter(str(record.get("judge_verdict") or "").upper() for record in records if record.get("judge_verdict"))
    phases = Counter(str(record.get("phase") or "") for record in records if record.get("phase"))
    blocking_count = sum(1 for record in records if str(record.get("severity") or "") == "error")
    approved_count = sum(1 for record in records if bool(record.get("approved")))
    return {
        "count": len(records),
        "blocking_count": blocking_count,
        "approved_count": approved_count,
        "by_kind": dict(counts_by_kind),
        "judge_outcomes": {key: value for key, value in judge_outcomes.items() if key},
        "phases": {key: value for key, value in phases.items() if key},
        "recent": records[-10:],
    }


from collections import Counter

__all__ = [
    "append_feedback_record",
    "build_feedback_summary",
    "feedback_path",
    "read_feedback_records",
    "record_iteration_feedback",
]
