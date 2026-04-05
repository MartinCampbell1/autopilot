#!/usr/bin/env python3
"""Create deterministic execution attention records for live parity runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autopilot.core.approval_runtime import annotate_approval_runtime, create_or_reuse_approval_runtime
from autopilot.core.approvals import ApprovalRecord, create_approval, list_approvals
from autopilot.core.config import load_config
from autopilot.core.control_plane_issues import create_issue
from autopilot.core.project_store import get_project_entry
from autopilot.core.tool_permission_runtime import tool_permission_runtime_key


def _find_seed_approval(
    approvals: list[ApprovalRecord],
    seed_key: str,
) -> ApprovalRecord | None:
    for approval in approvals:
        payload = dict(approval.payload or {})
        if str(payload.get("seed_key") or "").strip() == seed_key:
            return approval
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--seed-key", required=True)
    parser.add_argument("--story-id", type=int, default=1)
    parser.add_argument("--tool-name", default="shell_exec")
    args = parser.parse_args()

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    project = get_project_entry(config, project_id=args.project_id, include_archived=True)
    if project is None:
        raise SystemExit(f"Unknown project: {args.project_id}")

    project_id = str(project["id"])
    project_name = str(project["name"])
    story_id = int(args.story_id)
    seed_key = str(args.seed_key).strip()
    runtime_agent_id = f"{project_id}:{story_id}:worker:parity"
    runtime_agent_ids = [runtime_agent_id]
    issue_dedupe_key = f"{seed_key}:issue:policy-approval"
    tool_use_id = f"toolu_{seed_key.replace(':', '_')}"
    permission_runtime_key = tool_permission_runtime_key(project_id, args.tool_name, tool_use_id)

    issue = create_issue(
        config,
        project=project,
        title="Operator approval required for parity delivery loop",
        description=(
            "Synthetic execution issue for live parity. Keeps dashboard, inbox, review, "
            "and portfolio attention surfaces populated with one stable blocking record."
        ),
        root_cause="Parity seed intentionally leaves one operator approval and tool permission pending.",
        category="policy_approval",
        severity="critical",
        source_event="parity_seed",
        related_command="launch",
        story_id=story_id,
        runtime_agent_id=runtime_agent_id,
        runtime_agent_ids=runtime_agent_ids,
        dedupe_key=issue_dedupe_key,
        context={
            "seed_key": seed_key,
            "kind": "parity_seed_issue",
            "story": {
                "id": story_id,
                "title": "Verify full linked-chain parity",
            },
        },
    )

    runtime = create_or_reuse_approval_runtime(
        config,
        key=permission_runtime_key,
        project_id=project_id,
        issue_id=issue.id,
        runtime_agent_ids=runtime_agent_ids,
        metadata={
            "kind": "tool_permission_request",
            "tool_name": args.tool_name,
            "tool_use_id": tool_use_id,
            "seed_key": seed_key,
        },
        publish_pending=True,
        pending_message_type="tool_permission_pending",
        pending_payload={
            "tool_name": args.tool_name,
            "tool_use_id": tool_use_id,
            "behavior": "pending_user",
            "message": "Parity seed requires an operator tool-permission decision.",
            "seed_key": seed_key,
        },
    )

    existing_approval = _find_seed_approval(
        list_approvals(config, project_id=project_id, status="pending"),
        seed_key,
    )
    approval = existing_approval or create_approval(
        config,
        project=project,
        action="launch",
        payload={
            "seed_key": seed_key,
            "story_id": story_id,
            "launch_profile": "parity-review",
        },
        requested_by="parity-seed",
        reason="Synthetic pending approval for operator-rich live parity.",
        issue_id=issue.id,
        approval_runtime_id=runtime.id,
        runtime_agent_ids=runtime_agent_ids,
        policy_reasons=["parity_seed_requires_operator_decision"],
    )

    runtime = create_or_reuse_approval_runtime(
        config,
        key=permission_runtime_key,
        project_id=project_id,
        approval_id=approval.id,
        issue_id=issue.id,
        runtime_agent_ids=runtime_agent_ids,
        metadata={
            "kind": "tool_permission_request",
            "tool_name": args.tool_name,
            "tool_use_id": tool_use_id,
            "seed_key": seed_key,
        },
    )
    annotate_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        metadata_updates={
            "pending": {
                "stage": "pending_user",
                "tool_name": args.tool_name,
                "tool_use_id": tool_use_id,
                "resolved_behavior": "",
                "seed_key": seed_key,
            },
            "seed": {
                "key": seed_key,
                "project_id": project_id,
                "project_name": project_name,
            },
        },
    )

    issue = create_issue(
        config,
        project=project,
        title="Operator approval required for parity delivery loop",
        description=(
            "Synthetic execution issue for live parity. Keeps dashboard, inbox, review, "
            "and portfolio attention surfaces populated with one stable blocking record."
        ),
        root_cause="Parity seed intentionally leaves one operator approval and tool permission pending.",
        category="policy_approval",
        severity="critical",
        source_event="parity_seed",
        related_command="launch",
        story_id=story_id,
        runtime_agent_id=runtime_agent_id,
        runtime_agent_ids=runtime_agent_ids,
        approval_id=approval.id,
        dedupe_key=issue_dedupe_key,
        context={
            "seed_key": seed_key,
            "kind": "parity_seed_issue",
            "story": {
                "id": story_id,
                "title": "Verify full linked-chain parity",
            },
            "approval": {
                "id": approval.id,
                "action": approval.action,
            },
            "tool_permission_runtime": {
                "id": runtime.id,
                "tool_name": args.tool_name,
                "tool_use_id": tool_use_id,
            },
        },
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "project_id": project_id,
                "project_name": project_name,
                "seed_key": seed_key,
                "issue_id": issue.id,
                "approval_id": approval.id,
                "approval_runtime_id": runtime.id,
                "runtime_agent_id": runtime_agent_id,
                "tool_name": args.tool_name,
                "tool_use_id": tool_use_id,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
