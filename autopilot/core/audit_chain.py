"""Append-only audit chain helpers for trace and event log integrity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autopilot.core.artifact_store import get_artifact
from autopilot.core.config import AutopilotConfig
from autopilot.core.cost_accounting import usage_record_digest

AUDIT_CHAIN_SCHEMA_VERSION = 1
_AUDIT_EXCLUDED_KEYS = {"audit"}
_ARTIFACT_ID_KEYS = {
    "artifact_id",
    "artifact_ref",
    "output_artifact_id",
    "transcript_artifact_id",
    "stored_result_artifact_id",
}
_JSON_DIGEST_KEYS = {
    "gate_results",
    "handoff",
    "iteration_usage",
    "payload",
    "request",
    "response",
    "review_results",
    "verification_checks",
    "worker_usage",
    "critic_usage",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(_canonical_json(value))


def sanitize_audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(payload or {}).items() if key not in _AUDIT_EXCLUDED_KEYS}


def build_audit_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract stable provenance fields from one audit payload."""

    payload = dict(payload or {})
    return {
        "project_id": str(payload.get("project_id") or "").strip(),
        "run_id": str(payload.get("run_id") or payload.get("runtime_session_id") or "").strip(),
        "story_id": payload.get("story_id"),
        "kind": str(payload.get("kind") or "").strip(),
        "event": str(payload.get("event") or "").strip(),
        "timestamp": str(payload.get("timestamp") or "").strip(),
        "source": str(payload.get("source") or "").strip(),
        "status": str(payload.get("status") or "").strip(),
    }


def build_artifact_digests(
    payload: dict[str, Any],
    *,
    config: AutopilotConfig | None = None,
) -> dict[str, Any]:
    """Resolve digest metadata for artifacts and structured output blobs referenced by one payload."""

    payload = dict(payload or {})
    digests: dict[str, Any] = {}

    for key in _ARTIFACT_ID_KEYS:
        artifact_id = str(payload.get(key) or "").strip()
        if not artifact_id or config is None:
            continue
        artifact = get_artifact(config, artifact_id)
        if artifact is not None and artifact.sha256:
            digests[key] = artifact.sha256

    linked_ids = [str(item).strip() for item in list(payload.get("linked_artifact_ids") or []) if str(item).strip()]
    if linked_ids and config is not None:
        linked_digests = {
            artifact_id: artifact.sha256
            for artifact_id in linked_ids
            for artifact in [get_artifact(config, artifact_id)]
            if artifact is not None and artifact.sha256
        }
        if linked_digests:
            digests["linked_artifact_ids"] = linked_digests

    for key in _JSON_DIGEST_KEYS:
        value = payload.get(key)
        if value in (None, "", [], {}):
            continue
        if key in {"iteration_usage", "worker_usage", "critic_usage"} and isinstance(value, dict):
            digests[f"{key}_sha256"] = usage_record_digest(value)
            continue
        digests[f"{key}_sha256"] = _sha256_json(value)

    diff_signature = str(payload.get("diff_signature") or "").strip()
    if diff_signature:
        digests["diff_signature_sha256"] = _sha256_text(diff_signature)

    for key in ("approval_id", "issue_id", "shadow_audit_id", "tool_use_id", "request_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            digests[f"{key}_sha256"] = _sha256_text(value)

    return digests


def build_audit_metadata(
    payload: dict[str, Any],
    *,
    sequence: int,
    previous_hash: str = "",
    chain_kind: str = "trace",
    config: AutopilotConfig | None = None,
) -> dict[str, Any]:
    """Build one canonical audit envelope for an append-only JSONL record."""

    sanitized = sanitize_audit_payload(payload)
    provenance = build_audit_provenance(sanitized)
    artifact_digests = build_artifact_digests(sanitized, config=config)
    payload_sha256 = _sha256_json(sanitized)
    entry_hash = _sha256_json(
        {
            "schema_version": AUDIT_CHAIN_SCHEMA_VERSION,
            "chain_kind": chain_kind,
            "sequence": int(sequence),
            "previous_hash": str(previous_hash or ""),
            "payload_sha256": payload_sha256,
            "artifact_digests": artifact_digests,
            "provenance": provenance,
        }
    )
    return {
        "schema_version": AUDIT_CHAIN_SCHEMA_VERSION,
        "chain_kind": chain_kind,
        "sequence": int(sequence),
        "previous_hash": str(previous_hash or ""),
        "payload_sha256": payload_sha256,
        "artifact_digests": artifact_digests,
        "provenance": provenance,
        "entry_hash": entry_hash,
    }


def _package_audit_entries(
    entries: list[dict[str, Any]],
    *,
    chain_kind: str,
    config: AutopilotConfig | None = None,
) -> list[dict[str, Any]]:
    packaged: list[dict[str, Any]] = []
    previous_hash = ""
    package_chain_kind = f"{chain_kind}_export"

    for sequence, entry in enumerate(entries, start=1):
        packaged_entry = sanitize_audit_payload(entry)
        source_audit = dict(entry.get("audit") or {})
        if source_audit:
            packaged_entry["source_audit"] = source_audit
        packaged_entry["audit"] = build_audit_metadata(
            packaged_entry,
            sequence=sequence,
            previous_hash=previous_hash,
            chain_kind=package_chain_kind,
            config=config,
        )
        previous_hash = str((packaged_entry.get("audit") or {}).get("entry_hash") or "")
        packaged.append(packaged_entry)

    return packaged


def _load_json_record(line: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = _load_json_record(line)
            if payload is not None:
                records.append(payload)
    return records


def _last_audit_state(path: Path) -> tuple[int, str]:
    last_sequence = 0
    last_hash = ""
    for record in read_jsonl_records(path):
        audit = dict(record.get("audit") or {})
        last_sequence = int(audit.get("sequence") or last_sequence or 0)
        last_hash = str(audit.get("entry_hash") or last_hash or "")
    return last_sequence, last_hash


def append_jsonl_audit_record(
    path: Path,
    payload: dict[str, Any],
    *,
    chain_kind: str,
    config: AutopilotConfig | None = None,
) -> dict[str, Any]:
    """Append one JSONL record enriched with append-only audit metadata."""

    path.parent.mkdir(parents=True, exist_ok=True)
    sequence, previous_hash = _last_audit_state(path)
    record = sanitize_audit_payload(payload)
    record["audit"] = build_audit_metadata(
        record,
        sequence=sequence + 1,
        previous_hash=previous_hash,
        chain_kind=chain_kind,
        config=config,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def verify_audit_chain(
    entries: list[dict[str, Any]],
    *,
    chain_kind: str | None = None,
    config: AutopilotConfig | None = None,
    allow_partial: bool = True,
) -> dict[str, Any]:
    """Verify chain hashes and optionally referenced artifact digests."""

    verified = True
    errors: list[dict[str, Any]] = []
    previous_hash = ""
    expected_sequence = 1

    for index, entry in enumerate(entries, start=1):
        audit = dict(entry.get("audit") or {})
        if not audit:
            verified = False
            errors.append({"index": index, "reason": "missing_audit"})
            break
        resolved_chain_kind = str(chain_kind or audit.get("chain_kind") or "trace")
        if chain_kind is not None and str(audit.get("chain_kind") or "") != resolved_chain_kind:
            verified = False
            errors.append(
                {
                    "index": index,
                    "reason": "chain_kind_mismatch",
                    "expected": resolved_chain_kind,
                    "actual": str(audit.get("chain_kind") or ""),
                }
            )
            break
        actual_sequence = int(audit.get("sequence") or 0)
        if index == 1 and allow_partial:
            expected_sequence = actual_sequence
        if actual_sequence != expected_sequence:
            verified = False
            errors.append(
                {
                    "index": index,
                    "reason": "sequence_mismatch",
                    "expected": expected_sequence,
                    "actual": actual_sequence,
                }
            )
            break
        actual_previous_hash = str(audit.get("previous_hash") or "")
        if index > 1 and actual_previous_hash != previous_hash:
            verified = False
            errors.append(
                {
                    "index": index,
                    "reason": "previous_hash_mismatch",
                    "expected": previous_hash,
                    "actual": actual_previous_hash,
                }
            )
            break
        sanitized = sanitize_audit_payload(entry)
        recomputed_payload_sha256 = _sha256_json(sanitized)
        if recomputed_payload_sha256 != str(audit.get("payload_sha256") or ""):
            verified = False
            errors.append({"index": index, "reason": "payload_digest_mismatch"})
            break
        recomputed_provenance = build_audit_provenance(sanitized)
        if recomputed_provenance != dict(audit.get("provenance") or {}):
            verified = False
            errors.append({"index": index, "reason": "provenance_mismatch"})
            break
        stored_digests = dict(audit.get("artifact_digests") or {})
        artifact_digests = stored_digests
        if config is not None:
            current_digests = build_artifact_digests(sanitized, config=config)
            if current_digests != stored_digests:
                verified = False
                errors.append(
                    {
                        "index": index,
                        "reason": "artifact_digest_mismatch",
                        "expected": stored_digests,
                        "actual": current_digests,
                    }
                )
                break
            artifact_digests = current_digests
        recomputed_entry_hash = _sha256_json(
            {
                "schema_version": AUDIT_CHAIN_SCHEMA_VERSION,
                "chain_kind": resolved_chain_kind,
                "sequence": actual_sequence,
                "previous_hash": actual_previous_hash if index == 1 and allow_partial else previous_hash,
                "payload_sha256": recomputed_payload_sha256,
                "artifact_digests": artifact_digests,
                "provenance": recomputed_provenance,
            }
        )
        if recomputed_entry_hash != str(audit.get("entry_hash") or ""):
            verified = False
            errors.append({"index": index, "reason": "entry_hash_mismatch"})
            break
        previous_hash = str(audit.get("entry_hash") or "")
        expected_sequence += 1

    return {
        "verified": verified,
        "entry_count": len(entries),
        "latest_hash": previous_hash if verified else "",
        "errors": errors,
    }


def build_audit_bundle(
    entries: list[dict[str, Any]],
    *,
    chain_kind: str,
    project_id: str = "",
    run_id: str = "",
    story_id: int | None = None,
    config: AutopilotConfig | None = None,
    include_entries: bool = True,
    source_verification: dict[str, Any] | None = None,
    source_entry_count: int | None = None,
) -> dict[str, Any]:
    """Build an export-ready audit bundle with verification metadata."""

    package_chain_kind = f"{chain_kind}_export"
    packaged_entries = _package_audit_entries(entries, chain_kind=chain_kind, config=config)
    verification = verify_audit_chain(
        packaged_entries,
        chain_kind=package_chain_kind,
        config=config,
        allow_partial=False,
    )
    return {
        "audit_chain": {
            "schema_version": AUDIT_CHAIN_SCHEMA_VERSION,
            "chain_kind": chain_kind,
            "package_chain_kind": package_chain_kind,
            "project_id": project_id,
            "run_id": run_id,
            "story_id": story_id,
            "entry_count": len(packaged_entries),
            "source_entry_count": int(source_entry_count or len(entries)),
            "verification": verification,
            "source_verification": dict(source_verification or {}),
        },
        "entries": packaged_entries if include_entries else [],
    }


__all__ = [
    "append_jsonl_audit_record",
    "build_artifact_digests",
    "build_audit_bundle",
    "build_audit_metadata",
    "build_audit_provenance",
    "read_jsonl_records",
    "sanitize_audit_payload",
    "verify_audit_chain",
]
