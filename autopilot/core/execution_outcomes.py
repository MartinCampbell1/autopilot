"""Durable export helpers for FounderOS execution outcome bundles."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopilot.core.atomic_io import atomic_write_json as _shared_atomic_write_json
from autopilot.core.brief_metadata import (
    find_project_by_execution_brief_id,
    get_execution_brief_project_metadata,
    get_execution_brief_v2_metadata,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.learning_postback import dispatch_learning_postback
from autopilot.core.monitoring.traces import RUN_END_EVENTS, build_trace_monitor
from autopilot.core.shared_contract_codec import dump_shared_contract, load_shared_execution_outcome_bundle
from autopilot.core.shared_contracts import (
    Confidence,
    EvidenceBundle,
    EvidenceItem,
    ExecutionOutcomeBundle,
    IdeaOutcomeStatus,
    VerdictStatus,
)

_STALLED_EVENTS = {"budget_paused", "interrupt_paused", "paused", "run_paused", "timeout_paused"}
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def execution_outcome_path(config: AutopilotConfig, brief_id: str) -> Path:
    """Return the durable export path for one shared execution outcome."""

    return config.autopilot_home / "execution-outcomes" / f"{brief_id}.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _shared_atomic_write_json(path, payload)


def _latest_terminal_event(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in reversed(entries):
        if str(entry.get("event") or "") in RUN_END_EVENTS:
            return entry
    return None


def _resolve_run_id(detail: dict[str, Any], terminal_event: dict[str, Any] | None) -> str:
    monitoring = dict(detail.get("monitoring") or {})
    latest_run = dict(monitoring.get("latest_run") or {})
    return (
        str((terminal_event or {}).get("run_id") or "").strip()
        or str(latest_run.get("run_id") or "").strip()
        or str(detail.get("runtime_session_id") or "").strip()
    )


def _stories_summary(stories: list[dict[str, Any]]) -> tuple[int, int, int]:
    attempted = sum(1 for story in stories if str(story.get("status") or "") != "open")
    passed = sum(1 for story in stories if str(story.get("status") or "") == "done")
    failed = sum(1 for story in stories if str(story.get("status") or "") in {"stuck", "merge_blocked"})
    return attempted, passed, failed


def _resolve_verdict(
    feedback_records: list[dict[str, Any]],
    terminal_event: dict[str, Any] | None,
) -> VerdictStatus:
    judge_records = [record for record in feedback_records if str(record.get("kind") or "") == "judge_outcome"]
    if judge_records:
        verdict = str(judge_records[-1].get("judge_verdict") or "").strip().upper()
        if verdict == "PASS":
            return VerdictStatus.PASS
        if verdict == "FAIL":
            return VerdictStatus.FAIL
        if verdict == "PARTIAL":
            return VerdictStatus.PARTIAL
        if verdict == "SKIP":
            return VerdictStatus.SKIP

    review_records = [record for record in feedback_records if str(record.get("kind") or "") == "review_phase"]
    if review_records:
        approvals = [bool(record.get("approved")) for record in review_records]
        if approvals and all(approvals):
            return VerdictStatus.PASS
        if any(approvals):
            return VerdictStatus.PARTIAL
        return VerdictStatus.FAIL

    event = str((terminal_event or {}).get("event") or "").strip()
    if event == "run_completed":
        return VerdictStatus.PASS
    if event == "run_failed":
        return VerdictStatus.FAIL
    if event in _STALLED_EVENTS:
        return VerdictStatus.SKIP
    if event == "run_finished":
        return VerdictStatus.PARTIAL
    return VerdictStatus.PARTIAL


def _resolve_status(
    verdict: VerdictStatus,
    terminal_event: dict[str, Any] | None,
    *,
    shipped_artifacts: list[str],
) -> IdeaOutcomeStatus:
    event = str((terminal_event or {}).get("event") or "").strip()
    if event in _STALLED_EVENTS:
        return IdeaOutcomeStatus.STALLED
    if verdict == VerdictStatus.FAIL or event == "run_failed":
        return IdeaOutcomeStatus.INVALIDATED
    if verdict == VerdictStatus.PASS:
        return IdeaOutcomeStatus.VALIDATED
    return IdeaOutcomeStatus.IN_PROGRESS


def _critic_pass_rate(trace_monitor: dict[str, Any], run_id: str, verdict: VerdictStatus) -> float:
    runs = [
        dict(run)
        for run in list(trace_monitor.get("runs") or [])
        if str(run.get("run_id") or "").strip() == str(run_id or "").strip()
    ]
    if runs:
        run = runs[-1]
        iteration_count = int(run.get("iteration_count") or 0)
        rejections = int(run.get("critic_rejection_count") or 0)
        if iteration_count > 0:
            return round(max(iteration_count - rejections, 0) / iteration_count, 4)
    if verdict == VerdictStatus.PASS:
        return 1.0
    if verdict == VerdictStatus.FAIL:
        return 0.0
    return 0.5


def _shipped_artifacts(detail: dict[str, Any]) -> list[str]:
    artifacts: list[str] = []
    delivery_loop = dict(detail.get("delivery_loop") or {})
    artifact = dict(delivery_loop.get("artifact") or {})
    handoff = dict(delivery_loop.get("handoff") or {})

    for candidate in (
        str(artifact.get("path") or "").strip(),
        str(artifact.get("url") or "").strip(),
        str((artifact.get("handoff") or {}).get("url") or "").strip(),
        str(handoff.get("url") or "").strip(),
    ):
        if candidate and candidate not in artifacts:
            artifacts.append(candidate)
    return artifacts


def _failure_modes(
    feedback_records: list[dict[str, Any]],
    trace_monitor: dict[str, Any],
    terminal_event: dict[str, Any] | None,
) -> list[str]:
    messages: list[str] = []
    for record in feedback_records:
        if str(record.get("severity") or "") != "error":
            continue
        summary = str(record.get("summary") or "").strip()
        if summary and summary not in messages:
            messages.append(summary)
    for failure in list(trace_monitor.get("recent_failures") or []):
        message = str(failure.get("message") or failure.get("event") or "").strip()
        if message and message not in messages:
            messages.append(message)
    terminal_message = str((terminal_event or {}).get("message") or "").strip()
    if terminal_message and terminal_message not in messages and str((terminal_event or {}).get("event") or "") == "run_failed":
        messages.append(terminal_message)
    return messages[:10]


def _lessons_learned(feedback_records: list[dict[str, Any]], failure_modes: list[str]) -> list[str]:
    lessons: list[str] = []
    for record in feedback_records:
        summary = str(record.get("summary") or "").strip()
        if not summary:
            continue
        if summary not in lessons:
            lessons.append(summary)
    for failure in failure_modes:
        if failure not in lessons:
            lessons.append(failure)
    return lessons[:10]


def _build_evidence_bundle(
    *,
    brief_id: str,
    run_id: str,
    terminal_event: dict[str, Any] | None,
    feedback_records: list[dict[str, Any]],
    shipped_artifacts: list[str],
) -> EvidenceBundle | None:
    items: list[EvidenceItem] = []
    if terminal_event is not None:
        items.append(
            EvidenceItem(
                evidence_id=f"{brief_id}:terminal:{str(terminal_event.get('event') or 'event')}",
                kind="critic_verdict",
                summary=str(terminal_event.get("message") or terminal_event.get("event") or "Terminal run event"),
                raw_content=str(terminal_event.get("message") or "").strip() or None,
                source="autopilot.project_event",
                confidence=Confidence.MEDIUM,
                tags=[str(terminal_event.get("event") or "").strip(), run_id],
            )
        )
    for index, record in enumerate(feedback_records[-3:], start=1):
        summary = str(record.get("summary") or "").strip()
        if not summary:
            continue
        items.append(
            EvidenceItem(
                evidence_id=f"{brief_id}:feedback:{index}",
                kind="test_result" if str(record.get("kind") or "") == "review_phase" else "source_observation",
                summary=summary,
                raw_content=summary,
                source=f"autopilot.feedback.{str(record.get('kind') or 'unknown')}",
                confidence=Confidence.MEDIUM if bool(record.get("approved")) else Confidence.LOW,
                tags=[
                    str(record.get("kind") or "").strip(),
                    str(record.get("run_id") or "").strip(),
                ],
            )
        )
    for index, artifact in enumerate(shipped_artifacts, start=1):
        items.append(
            EvidenceItem(
                evidence_id=f"{brief_id}:artifact:{index}",
                kind="external_link",
                summary=f"Shipped artifact {index}",
                artifact_path=artifact if not artifact.startswith("http") else None,
                raw_content=artifact if artifact.startswith("http") else None,
                source="autopilot.delivery",
                confidence=Confidence.HIGH,
                tags=["artifact"],
            )
        )
    if not items:
        return None
    created_at = _utcnow()
    return EvidenceBundle(
        bundle_id=f"evidence_{brief_id}",
        parent_id=brief_id,
        items=items,
        overall_confidence=Confidence.MEDIUM,
        created_at=created_at,
        updated_at=created_at,
    )


def build_execution_outcome_bundle(config: AutopilotConfig, brief_id: str) -> ExecutionOutcomeBundle | None:
    """Build one exportable shared outcome bundle for a brief-backed project."""

    from autopilot.core.evals.feedback import read_feedback_records
    from autopilot.core.project_store import build_project_detail
    from autopilot.core.run_trace import read_trace_entries

    project = find_project_by_execution_brief_id(config, brief_id)
    if project is None:
        return None
    metadata = get_execution_brief_project_metadata(project)
    if str(metadata.get("brief_id") or "").strip() != str(brief_id or "").strip():
        return None

    detail = build_project_detail(config, str(project["id"]))
    trace_entries = read_trace_entries(config, str(project["id"]), limit=4000)
    terminal_event = _latest_terminal_event(trace_entries)
    run_id = _resolve_run_id(detail, terminal_event)
    feedback_records = read_feedback_records(config, str(project["id"]), limit=800)
    if run_id:
        scoped_feedback = [
            record
            for record in feedback_records
            if str(record.get("run_id") or "").strip() == run_id
        ]
        if scoped_feedback:
            feedback_records = scoped_feedback

    trace_monitor = build_trace_monitor(trace_entries)
    stories_attempted, stories_passed, stories_failed = _stories_summary(list(detail.get("stories") or []))
    shipped_artifacts = _shipped_artifacts(detail)
    verdict = _resolve_verdict(feedback_records, terminal_event)
    failure_modes = _failure_modes(feedback_records, trace_monitor, terminal_event)
    lessons_learned = _lessons_learned(feedback_records, failure_modes)
    evidence = _build_evidence_bundle(
        brief_id=brief_id,
        run_id=run_id,
        terminal_event=terminal_event,
        feedback_records=feedback_records,
        shipped_artifacts=shipped_artifacts,
    )
    bugs_found = len(
        {
            str(record.get("summary") or "").strip()
            for record in feedback_records
            if str(record.get("severity") or "") == "error" and str(record.get("summary") or "").strip()
        }
    )
    total_cost_usd = float(
        (dict((detail.get("monitoring") or {}).get("latest_run") or {}).get("cost") or {}).get("estimated_cost_usd")
        or (dict((detail.get("cost_usage") or {}).get("run") or {}).get("estimated_cost_usd"))
        or (dict((detail.get("cost_usage") or {}).get("project") or {}).get("estimated_cost_usd"))
        or 0.0
    )
    total_duration_seconds = float(
        (dict((detail.get("monitoring") or {}).get("latest_run") or {}).get("elapsed_sec") or 0.0)
    )
    if total_duration_seconds <= 0 and terminal_event is not None:
        started_at = str(terminal_event.get("run_started_at") or detail.get("started_at") or "").strip()
        finished_at = str(terminal_event.get("timestamp") or detail.get("finished_at") or "").strip()
        if started_at and finished_at:
            try:
                total_duration_seconds = max(
                    (
                        datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                        - datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    ).total_seconds(),
                    0.0,
                )
            except ValueError:
                total_duration_seconds = 0.0

    outcome_seed = f"{brief_id}:{project['id']}"
    return ExecutionOutcomeBundle(
        outcome_id=f"outcome_{uuid.uuid5(uuid.NAMESPACE_URL, outcome_seed).hex[:24]}",
        brief_id=str(metadata.get("brief_id") or brief_id),
        idea_id=str(metadata.get("idea_id") or metadata.get("initiative_id") or ""),
        status=_resolve_status(verdict, terminal_event, shipped_artifacts=shipped_artifacts),
        verdict=verdict,
        total_cost_usd=round(total_cost_usd, 8),
        total_duration_seconds=round(total_duration_seconds, 4),
        stories_attempted=stories_attempted,
        stories_passed=stories_passed,
        stories_failed=stories_failed,
        bugs_found=bugs_found,
        critic_pass_rate=_critic_pass_rate(trace_monitor, run_id, verdict),
        shipped_artifacts=shipped_artifacts,
        failure_modes=failure_modes,
        lessons_learned=lessons_learned,
        evidence=evidence,
        created_at=_utcnow(),
    )


def persist_execution_outcome_bundle(config: AutopilotConfig, bundle: ExecutionOutcomeBundle) -> Path:
    """Persist one shared execution outcome bundle keyed by brief id."""

    path = execution_outcome_path(config, bundle.brief_id)
    payload = dump_shared_contract(bundle)
    _atomic_write_json(path, payload)
    return path


def refresh_execution_outcome_bundle(config: AutopilotConfig, brief_id: str) -> ExecutionOutcomeBundle | None:
    """Rebuild and persist the latest outcome export for one brief-backed project."""

    bundle = build_execution_outcome_bundle(config, brief_id)
    if bundle is None:
        return None
    persist_execution_outcome_bundle(config, bundle)
    return bundle


def maybe_refresh_execution_outcome_bundle_for_event(
    config: AutopilotConfig,
    *,
    project_id: str,
    event: str,
) -> ExecutionOutcomeBundle | None:
    """Update the exported outcome bundle after terminal-ish project events.

    Also triggers automatic learning postback to Quorum when an outcome is
    successfully built for a brief-origin project.
    """
    from autopilot.core.project_store import get_project_entry

    if event not in RUN_END_EVENTS:
        return None
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        return None
    metadata = get_execution_brief_project_metadata(project)
    brief_id = str(metadata.get("brief_id") or "").strip()
    if not brief_id:
        return None
    bundle = refresh_execution_outcome_bundle(config, brief_id)

    if bundle is not None:
        initiative_id = str(metadata.get("initiative_id") or "").strip()
        if initiative_id:
            try:
                from autopilot.core.initiative_lineage import upsert_initiative_lineage
                from founderos_contracts.lifecycle import FounderMode, InitiativeLifecycleState

                upsert_initiative_lineage(
                    config,
                    initiative_id,
                    outcome_id=bundle.outcome_id,
                    lifecycle_state=InitiativeLifecycleState.OUTCOME_EMITTED,
                    current_mode=FounderMode.LEARN,
                )
            except Exception as exc:
                logger.warning("Initiative lineage outcome update failed: %s", exc)

        idea_id = str(metadata.get("idea_id") or "").strip()
        if idea_id:
            try:
                outcome_payload = dump_shared_contract(bundle)
                project_name = str(project.get("name") or project.get("id") or "")
                def _mark_learning_applied() -> None:
                    if not initiative_id:
                        return
                    from autopilot.core.initiative_lineage import upsert_initiative_lineage
                    from founderos_contracts.lifecycle import FounderMode, InitiativeLifecycleState

                    upsert_initiative_lineage(
                        config,
                        initiative_id,
                        outcome_id=bundle.outcome_id,
                        lifecycle_state=InitiativeLifecycleState.LEARNING_APPLIED,
                        current_mode=FounderMode.LEARN,
                    )

                dispatch_learning_postback(
                    idea_id=idea_id,
                    outcome=outcome_payload,
                    project_id=project_id,
                    project_name=project_name,
                    on_success=_mark_learning_applied,
                )
            except Exception as exc:
                logger.warning("Learning postback trigger failed: %s", exc)

    return bundle


def load_execution_outcome_bundle(config: AutopilotConfig, brief_id: str) -> ExecutionOutcomeBundle | None:
    """Load one persisted execution outcome bundle by brief id."""

    path = execution_outcome_path(config, brief_id)
    if not path.exists():
        return None
    return load_shared_execution_outcome_bundle(_read_json(path))


# ---------------------------------------------------------------------------
# Founder-grade proof bundle
# ---------------------------------------------------------------------------


def build_execution_proof_bundle(
    config: AutopilotConfig, brief_id: str
) -> dict[str, Any] | None:
    """Build a founder-facing ``ExecutionProofBundle`` from project state.

    Aggregates outcome bundle, project detail, approvals, issues, CI/review
    summaries, changed files, and tests into one inspectable artifact.

    Returns a dict (JSON-safe) or None if the project cannot be found.
    """
    from autopilot.core.evals.feedback import read_feedback_records
    from autopilot.core.project_store import build_project_detail
    from autopilot.core.run_trace import read_trace_entries
    from founderos_contracts.proof_bundle import ExecutionProofBundle

    project = find_project_by_execution_brief_id(config, brief_id)
    if project is None:
        return None

    project_id = str(project["id"])
    metadata = get_execution_brief_project_metadata(project)
    detail = build_project_detail(config, project_id)

    # Resolve outcome bundle (build fresh if needed)
    outcome = build_execution_outcome_bundle(config, brief_id)

    # Trace / feedback data
    trace_entries = read_trace_entries(config, project_id, limit=4000)
    terminal_event = _latest_terminal_event(trace_entries)
    _resolve_run_id(detail, terminal_event)
    feedback_records = read_feedback_records(config, project_id, limit=800)

    # Changed files from trace
    changed_files: list[str] = []
    for entry in trace_entries:
        if str(entry.get("event") or "") == "file_changed":
            path = str(entry.get("path") or "").strip()
            if path and path not in changed_files:
                changed_files.append(path)

    # Tests from stories and feedback
    tests_executed: list[str] = []
    tests_passed = 0
    tests_failed = 0
    for story in list(detail.get("stories") or []):
        title = str(story.get("title") or "").strip()
        status = str(story.get("status") or "").strip()
        if title:
            tests_executed.append(f"{title} [{status}]")
        if status == "done":
            tests_passed += 1
        elif status in ("stuck", "merge_blocked"):
            tests_failed += 1

    # CI / review summaries from feedback
    review_summaries: list[str] = []
    for record in feedback_records:
        kind = str(record.get("kind") or "")
        summary = str(record.get("summary") or "").strip()
        if kind == "review_phase" and summary:
            review_summaries.append(summary)

    # Approvals
    approvals: list[str] = []
    v2_meta = get_execution_brief_v2_metadata(project)
    if v2_meta.get("brief_approval_status") == "approved":
        approvals.append(f"Brief approved (V2): {v2_meta.get('brief_id', '')}")

    # Linked issues
    linked_issues: list[str] = []
    for entry in trace_entries:
        if str(entry.get("event") or "") in ("issue_opened", "issue_linked"):
            issue_ref = str(entry.get("issue_ref") or entry.get("url") or "").strip()
            if issue_ref and issue_ref not in linked_issues:
                linked_issues.append(issue_ref)

    # Build proof bundle
    initiative_id = str(v2_meta.get("initiative_id") or metadata.get("initiative_id") or metadata.get("idea_id") or "")
    bundle = ExecutionProofBundle(
        bundle_id=f"proof_{uuid.uuid5(uuid.NAMESPACE_URL, f'{brief_id}:{project_id}').hex[:24]}",
        brief_id=brief_id,
        initiative_id=initiative_id,
        project_id=project_id,
        run_summary=str((terminal_event or {}).get("message") or detail.get("summary") or ""),
        total_cost_usd=outcome.total_cost_usd if outcome else 0.0,
        total_duration_seconds=outcome.total_duration_seconds if outcome else 0.0,
        changed_files=changed_files,
        tests_executed=tests_executed,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        ci_summary="",
        review_summary="; ".join(review_summaries[:3]) if review_summaries else "",
        approvals=approvals,
        linked_issues=linked_issues,
        unresolved_risks=[],
        shipped_artifacts=outcome.shipped_artifacts if outcome else [],
        outcome_status=outcome.status.value if outcome else "",
        outcome_verdict=outcome.verdict.value if outcome else "",
        failure_modes=outcome.failure_modes if outcome else [],
        lessons_learned=outcome.lessons_learned if outcome else [],
        operator_summary="",
        next_recommended_action="",
    )
    return bundle.model_dump(mode="json")
