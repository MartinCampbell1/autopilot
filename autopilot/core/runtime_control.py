"""Runtime control-plane primitives for ownership and atomic checkout leases."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from autopilot.core.config import AutopilotConfig


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeAgentRole(StrEnum):
    COORDINATOR = "coordinator"
    WORKER = "worker"
    CRITIC = "critic"
    SPECIALIST = "specialist"


@dataclass(slots=True)
class WorkItemLease:
    project_id: str
    story_id: int
    role: str
    owner: str
    project_path: str
    checkout_path: str | None
    branch_name: str | None
    status: str
    acquired_at: str
    updated_at: str
    runtime_pid: int | None = None


class WorkItemLeaseConflict(RuntimeError):
    """Raised when a work item is already leased by another runtime owner."""

    def __init__(self, lease: WorkItemLease):
        self.lease = lease
        super().__init__(
            f"Story #{lease.story_id} in project {lease.project_id} is already owned by {lease.owner} ({lease.role})."
        )


def work_item_lease_path(config: AutopilotConfig, project_id: str, story_id: int) -> Path:
    """Return the lease file path for one story work item."""
    return config.control_plane_state_dir / "leases" / project_id / f"story-{story_id}.json"


def load_work_item_lease(config: AutopilotConfig, project_id: str, story_id: int) -> WorkItemLease | None:
    """Load the current lease for a story if it exists."""
    path = work_item_lease_path(config, project_id, story_id)
    if not path.exists():
        return None
    return WorkItemLease(**json.loads(path.read_text()))


def claim_work_item_lease(
    config: AutopilotConfig,
    *,
    project_id: str,
    story_id: int,
    role: RuntimeAgentRole,
    owner: str,
    runtime_pid: int | None = None,
    project_path: Path,
    checkout_path: Path | None = None,
    branch_name: str | None = None,
) -> WorkItemLease:
    """Atomically claim ownership for a story work item."""
    path = work_item_lease_path(config, project_id, story_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    now = _utcnow_iso()
    lease = WorkItemLease(
        project_id=project_id,
        story_id=story_id,
        role=role.value,
        owner=owner,
        runtime_pid=runtime_pid,
        project_path=str(project_path),
        checkout_path=str(checkout_path) if checkout_path is not None else None,
        branch_name=branch_name,
        status="active",
        acquired_at=now,
        updated_at=now,
    )
    payload = json.dumps(asdict(lease), indent=2, ensure_ascii=False)

    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        existing = load_work_item_lease(config, project_id, story_id)
        if existing is None:
            raise RuntimeError(f"Lease file exists but could not be loaded: {path}") from exc
        raise WorkItemLeaseConflict(existing) from exc

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)

    return lease


def release_work_item_lease(
    config: AutopilotConfig,
    *,
    project_id: str,
    story_id: int,
    owner: str | None = None,
) -> bool:
    """Release a story work item lease if present."""
    path = work_item_lease_path(config, project_id, story_id)
    if not path.exists():
        return False

    if owner is not None:
        current = load_work_item_lease(config, project_id, story_id)
        if current is not None and current.owner != owner:
            return False

    path.unlink(missing_ok=True)
    return True


def refresh_work_item_lease(
    config: AutopilotConfig,
    *,
    project_id: str,
    story_id: int,
    owner: str | None = None,
    status: str | None = None,
    checkout_path: Path | None = None,
    branch_name: str | None = None,
) -> WorkItemLease | None:
    """Refresh the heartbeat and optional metadata for an existing work item lease."""
    current = load_work_item_lease(config, project_id, story_id)
    if current is None:
        return None
    if owner is not None and current.owner != owner:
        return None

    if status is not None:
        current.status = status
    if checkout_path is not None:
        current.checkout_path = str(checkout_path)
    if branch_name is not None:
        current.branch_name = branch_name
    current.updated_at = _utcnow_iso()

    path = work_item_lease_path(config, project_id, story_id)
    path.write_text(json.dumps(asdict(current), indent=2, ensure_ascii=False))
    return current


def list_project_work_item_leases(config: AutopilotConfig, project_id: str) -> list[WorkItemLease]:
    """List all active story leases for a project."""
    lease_dir = config.control_plane_state_dir / "leases" / project_id
    if not lease_dir.exists():
        return []

    leases: list[WorkItemLease] = []
    for path in sorted(lease_dir.glob("story-*.json")):
        try:
            leases.append(WorkItemLease(**json.loads(path.read_text())))
        except Exception:
            continue
    return leases
