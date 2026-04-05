"""Pre-consumption audit helpers and quarantine storage for suspicious outputs."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import VerificationCheck
from autopilot.core.orchestrator_sessions import link_orchestrator_session_entities
from autopilot.core.task_output import persist_task_output
from autopilot.core.verification_agent import (
    NON_ACTIONABLE_ADVERSARIAL_PROBE_FEEDBACK,
    NON_ACTIONABLE_VERDICT_FEEDBACK,
    NON_ACTIONABLE_VERIFICATION_FEEDBACK,
    validate_verifier_output,
)


ShadowAuditAction = Literal["pass", "retry", "quarantine", "escalate"]
_SHADOW_AUDIT_ACTION_PRIORITY: dict[ShadowAuditAction, int] = {
    "pass": 0,
    "retry": 1,
    "quarantine": 2,
    "escalate": 3,
}
_PATCH_MARKERS = (
    "diff --git ",
    "*** Begin Patch",
    "*** Update File:",
    "*** Add File:",
    "*** Delete File:",
)
_PATCH_KEYS = {
    "patch",
    "diff",
    "patch_text",
    "unified_diff",
    "patch_bundle",
    "operations",
}


@dataclass(frozen=True)
class ShadowAuditDecision:
    """One pre-handoff audit decision for suspicious runtime output."""

    action: ShadowAuditAction
    summary: str = ""
    findings: tuple[str, ...] = ()


class ShadowAuditRecord(BaseModel):
    """Persisted quarantine record for one suspicious runtime artifact."""

    id: str
    project_id: str = ""
    orchestrator_session_id: str = ""
    runtime_agent_ids: list[str] = Field(default_factory=list)
    source_kind: str
    source_name: str = ""
    source_id: str = ""
    action: ShadowAuditAction = "quarantine"
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    artifact_id: str = ""
    blocked_artifact_id: str = ""
    blocked_artifact_owner_kind: str = ""
    blocked_artifact_owner_id: str = ""
    status: str = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    resolved_at: str | None = None
    resolution: dict[str, Any] = Field(default_factory=dict)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def shadow_audit_path(config: AutopilotConfig, audit_id: str) -> Path:
    """Return the persisted path for one shadow-audit record."""

    return config.control_plane_state_dir / "shadow_audits" / f"{audit_id}.json"


def get_shadow_audit_record(config: AutopilotConfig, audit_id: str) -> ShadowAuditRecord | None:
    """Load one shadow-audit record if it exists."""

    path = shadow_audit_path(config, audit_id)
    if not path.exists():
        return None
    try:
        return ShadowAuditRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def save_shadow_audit_record(
    config: AutopilotConfig,
    record: ShadowAuditRecord,
) -> ShadowAuditRecord:
    """Persist one shadow-audit record."""

    record.updated_at = _utcnow_iso()
    _atomic_write_json(shadow_audit_path(config, record.id), record.model_dump())
    return record


def list_shadow_audit_records(
    config: AutopilotConfig,
    *,
    audit_id: str | None = None,
    project_id: str | None = None,
    orchestrator_session_id: str | None = None,
    runtime_agent_id: str | None = None,
    status: str | None = None,
    source_kind: str | None = None,
    blocked_artifact_id: str | None = None,
) -> list[ShadowAuditRecord]:
    """List persisted shadow-audit records with lightweight filtering."""

    directory = config.control_plane_state_dir / "shadow_audits"
    if not directory.exists():
        return []

    records: list[ShadowAuditRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = ShadowAuditRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        if audit_id and record.id != audit_id:
            continue
        if project_id and record.project_id != project_id:
            continue
        if orchestrator_session_id and record.orchestrator_session_id != orchestrator_session_id:
            continue
        if runtime_agent_id and runtime_agent_id not in record.runtime_agent_ids:
            continue
        if status and record.status != status:
            continue
        if source_kind and record.source_kind != source_kind:
            continue
        if blocked_artifact_id and record.blocked_artifact_id != blocked_artifact_id:
            continue
        records.append(record)

    records.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return records


def create_shadow_audit_record(
    config: AutopilotConfig,
    *,
    project_id: str = "",
    orchestrator_session_id: str = "",
    runtime_agent_ids: list[str] | None = None,
    source_kind: str,
    source_name: str = "",
    source_id: str = "",
    action: ShadowAuditAction = "quarantine",
    summary: str = "",
    findings: list[str] | tuple[str, ...] | None = None,
    content: str = "",
    blocked_artifact_id: str = "",
    blocked_artifact_owner_kind: str = "",
    blocked_artifact_owner_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> ShadowAuditRecord:
    """Persist one open shadow-audit quarantine record and backing artifact."""

    created_at = _utcnow_iso()
    record_id = f"sha_{uuid.uuid4().hex[:12]}"
    normalized_runtime_agent_ids = sorted(
        {str(item).strip() for item in (runtime_agent_ids or []) if str(item).strip()}
    )
    record = ShadowAuditRecord(
        id=record_id,
        project_id=str(project_id or "").strip(),
        orchestrator_session_id=str(orchestrator_session_id or "").strip(),
        runtime_agent_ids=normalized_runtime_agent_ids,
        source_kind=str(source_kind or "").strip() or "runtime_output",
        source_name=str(source_name or "").strip(),
        source_id=str(source_id or "").strip(),
        action=action,
        summary=str(summary or "").strip(),
        findings=[
            str(item).strip()
            for item in (findings or [])
            if str(item).strip()
        ],
        blocked_artifact_id=str(blocked_artifact_id or "").strip(),
        blocked_artifact_owner_kind=str(blocked_artifact_owner_kind or "").strip(),
        blocked_artifact_owner_id=str(blocked_artifact_owner_id or "").strip(),
        created_at=created_at,
        updated_at=created_at,
        metadata=dict(metadata or {}),
    )
    artifact = persist_task_output(
        config,
        owner_kind="shadow_audit",
        owner_id=record.id,
        content=str(content or "").strip() or record.summary,
        metadata={
            "project_id": record.project_id,
            "orchestrator_session_id": record.orchestrator_session_id,
            "runtime_agent_ids": list(record.runtime_agent_ids),
            "source_kind": record.source_kind,
            "source_name": record.source_name,
            "source_id": record.source_id,
            "action": record.action,
            "summary": record.summary,
            "findings": list(record.findings),
            "blocked_artifact_id": record.blocked_artifact_id,
            "blocked_artifact_owner_kind": record.blocked_artifact_owner_kind,
            "blocked_artifact_owner_id": record.blocked_artifact_owner_id,
            **record.metadata,
        },
    )
    record.artifact_id = artifact.id
    save_shadow_audit_record(config, record)
    if record.orchestrator_session_id:
        try:
            link_orchestrator_session_entities(
                config,
                record.orchestrator_session_id,
                project_ids=[record.project_id] if record.project_id else None,
                linked_runtime_agent_ids=record.runtime_agent_ids,
                linked_shadow_audit_ids=[record.id],
                linked_artifact_ids=[artifact.id],
            )
        except KeyError:
            pass
    return record


def resolve_shadow_audit_record(
    config: AutopilotConfig,
    audit_id: str,
    *,
    actor: str,
    note: str = "",
    outcome: str = "resolved",
) -> ShadowAuditRecord:
    """Mark one open shadow-audit record as resolved after explicit review."""

    record = get_shadow_audit_record(config, audit_id)
    if record is None:
        raise KeyError(audit_id)
    if record.status != "open":
        raise RuntimeError(f"Shadow audit `{audit_id}` is already `{record.status}`.")
    resolved_at = _utcnow_iso()
    record.status = "resolved"
    record.resolved_at = resolved_at
    record.resolution = {
        "actor": str(actor or "").strip() or "control-plane",
        "note": str(note or "").strip(),
        "outcome": str(outcome or "").strip() or "resolved",
        "resolved_at": resolved_at,
    }
    return save_shadow_audit_record(config, record)


def extract_shadow_audit_from_metadata(
    metadata: dict[str, Any] | None,
) -> tuple[ShadowAuditDecision | None, str, dict[str, Any]]:
    """Return an optional shadow-audit decision encoded in runtime metadata."""

    normalized_metadata = dict(metadata or {})
    raw_payload = normalized_metadata.get("shadow_audit")
    payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}

    action = str(
        payload.get("action")
        or normalized_metadata.get("shadow_audit_action")
        or "pass"
    ).strip().lower()
    if action not in {"retry", "quarantine", "escalate"}:
        return None, "", {}

    summary = str(
        payload.get("summary")
        or payload.get("feedback")
        or normalized_metadata.get("shadow_audit_feedback")
        or ""
    ).strip()
    findings = [
        str(item).strip()
        for item in (payload.get("findings") or normalized_metadata.get("shadow_audit_findings") or [])
        if str(item).strip()
    ]
    content = str(
        payload.get("content")
        or payload.get("artifact_content")
        or ""
    ).strip()
    passthrough_metadata = {
        key: value
        for key, value in payload.items()
        if key not in {"action", "summary", "feedback", "findings", "content", "artifact_content"}
    }
    return (
        ShadowAuditDecision(action=action, summary=summary, findings=tuple(findings)),
        content,
        passthrough_metadata,
    )


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _contains_patch_markers(text: str) -> bool:
    normalized = str(text or "")
    return any(marker in normalized for marker in _PATCH_MARKERS)


def _payload_contains_generated_patch(value: Any, *, depth: int = 0) -> bool:
    if depth > 4:
        return False
    if isinstance(value, str):
        return _contains_patch_markers(value)
    if isinstance(value, dict):
        patch_bundle = value.get("patch_bundle")
        if isinstance(patch_bundle, dict) and isinstance(patch_bundle.get("operations"), list):
            if any(bool(item) for item in patch_bundle.get("operations") or []):
                return True
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in _PATCH_KEYS:
                if isinstance(item, (str, list, tuple, dict)) and _payload_contains_generated_patch(
                    item, depth=depth + 1
                ):
                    return True
                if normalized_key == "operations" and isinstance(item, list) and any(bool(entry) for entry in item):
                    return True
            if _payload_contains_generated_patch(item, depth=depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_payload_contains_generated_patch(item, depth=depth + 1) for item in value[:20])
    return False


def _merge_shadow_audit_decisions(
    decisions: list[ShadowAuditDecision],
) -> ShadowAuditDecision | None:
    filtered = [decision for decision in decisions if decision is not None]
    if not filtered:
        return None
    strongest = max(
        filtered,
        key=lambda decision: _SHADOW_AUDIT_ACTION_PRIORITY.get(decision.action, 0),
    )
    findings: list[str] = []
    for decision in filtered:
        for finding in decision.findings:
            if finding not in findings:
                findings.append(finding)
    summary = strongest.summary
    if not summary:
        for decision in filtered:
            if decision.summary:
                summary = decision.summary
                break
    return ShadowAuditDecision(action=strongest.action, summary=summary, findings=tuple(findings))


def compose_shadow_audit_decision(
    metadata: dict[str, Any] | None,
    *,
    payload: dict[str, Any] | None = None,
    content: str = "",
) -> tuple[ShadowAuditDecision | None, str, dict[str, Any]]:
    """Compose explicit and rule-based shadow-audit decisions for one runtime handoff."""

    explicit_decision, explicit_content, passthrough_metadata = extract_shadow_audit_from_metadata(metadata)
    normalized_metadata = dict(metadata or {})
    allow_generated_patch = any(
        _coerce_bool(normalized_metadata.get(key))
        for key in (
            "shadow_audit_allow_generated_patch",
            "verified_generated_patch",
            "verified_patch_handoff",
        )
    )

    decisions: list[ShadowAuditDecision] = []
    sources: list[str] = []
    if explicit_decision is not None:
        decisions.append(explicit_decision)
        sources.append("metadata")

    if not allow_generated_patch and (
        _payload_contains_generated_patch(payload or {})
        or _contains_patch_markers(content)
    ):
        decisions.append(
            ShadowAuditDecision(
                action="quarantine",
                summary="Generated patch output requires explicit review before downstream handoff.",
                findings=("unverified_generated_patch",),
            )
        )
        sources.append("generated_patch_rule")

    merged = _merge_shadow_audit_decisions(decisions)
    if merged is None:
        return None, "", {}

    metadata_updates = dict(passthrough_metadata)
    if sources:
        metadata_updates["decision_sources"] = sources
    return merged, explicit_content or content, metadata_updates


def audit_verifier_output(raw_output: str, checks: list[VerificationCheck]) -> tuple[str, ShadowAuditDecision]:
    """Audit verifier-style critic output before downstream consumers trust it."""

    verdict, validation_feedback = validate_verifier_output(raw_output, checks)
    if not validation_feedback:
        if not verdict:
            return "", ShadowAuditDecision(action="pass")
        return verdict, ShadowAuditDecision(
            action="pass",
            findings=(f"verdict:{verdict.lower()}",),
        )

    if validation_feedback == NON_ACTIONABLE_VERDICT_FEEDBACK:
        return verdict, ShadowAuditDecision(
            action="retry",
            summary=validation_feedback,
            findings=("invalid_verdict_contract",),
        )

    if validation_feedback == NON_ACTIONABLE_VERIFICATION_FEEDBACK:
        return verdict, ShadowAuditDecision(
            action="quarantine",
            summary=validation_feedback,
            findings=("missing_command_evidence",),
        )

    if validation_feedback == NON_ACTIONABLE_ADVERSARIAL_PROBE_FEEDBACK:
        return verdict, ShadowAuditDecision(
            action="quarantine",
            summary=validation_feedback,
            findings=("missing_adversarial_probe",),
        )

    return verdict, ShadowAuditDecision(
        action="retry",
        summary=validation_feedback,
        findings=("verification_contract_error",),
    )


__all__ = [
    "ShadowAuditAction",
    "ShadowAuditDecision",
    "ShadowAuditRecord",
    "audit_verifier_output",
    "compose_shadow_audit_decision",
    "create_shadow_audit_record",
    "extract_shadow_audit_from_metadata",
    "get_shadow_audit_record",
    "list_shadow_audit_records",
    "resolve_shadow_audit_record",
    "save_shadow_audit_record",
    "shadow_audit_path",
]
