"""Validation and JSON helpers for shared Quorum/Autopilot contracts."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import TypeAdapter

from founderos_contracts.shared_v1 import EvidenceBundle, ExecutionBrief, ExecutionOutcomeBundle

_EVIDENCE_BUNDLE_ADAPTER = TypeAdapter(EvidenceBundle)
_EXECUTION_BRIEF_ADAPTER = TypeAdapter(ExecutionBrief)
_EXECUTION_OUTCOME_ADAPTER = TypeAdapter(ExecutionOutcomeBundle)


def _dump_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: _dump_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _dump_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_dump_value(item) for item in value]
    return value


def dump_shared_contract(value: Any) -> dict[str, Any]:
    """Serialize one shared-contract dataclass into a JSON-safe dict."""

    dumped = _dump_value(value)
    if not isinstance(dumped, dict):
        raise TypeError("Shared contract payload must serialize into a mapping.")
    return dumped


def load_shared_evidence_bundle(payload: dict[str, Any]) -> EvidenceBundle:
    """Validate one evidence bundle payload into the shared dataclass."""

    return _EVIDENCE_BUNDLE_ADAPTER.validate_python(payload)


def load_shared_execution_brief(payload: dict[str, Any]) -> ExecutionBrief:
    """Validate one execution brief payload into the shared dataclass."""

    return _EXECUTION_BRIEF_ADAPTER.validate_python(payload)


def load_shared_execution_outcome_bundle(payload: dict[str, Any]) -> ExecutionOutcomeBundle:
    """Validate one execution outcome payload into the shared dataclass."""

    return _EXECUTION_OUTCOME_ADAPTER.validate_python(payload)


def shared_execution_brief_json_schema() -> dict[str, Any]:
    """Expose the shared execution-brief JSON schema for external callers."""

    return _EXECUTION_BRIEF_ADAPTER.json_schema()
