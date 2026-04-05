"""Tests for the shared schema-versioned artifact store."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.artifact_store import (
    get_artifact,
    list_artifacts,
    persist_artifact,
    persist_json_artifact,
    promote_artifact,
    read_artifact_text,
)
from autopilot.core.config import AutopilotConfig


def test_persist_artifact_writes_manifest_and_content(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    artifact = persist_artifact(
        config,
        artifact_id="artf_demo_1",
        content="hello shared artifact",
        artifact_type="task_output",
        stage="verified",
        owner_kind="runtime_agent_task",
        owner_id="rat_123",
        project_id="proj_123",
        orchestrator_session_id="ors_123",
        runtime_agent_ids=["agt_1"],
        metadata={"purpose": "demo"},
    )

    stored = get_artifact(config, artifact.id)

    assert stored is not None
    assert stored.schema_version == 1
    assert stored.stage == "verified"
    assert stored.owner_kind == "runtime_agent_task"
    assert Path(stored.manifest_path).exists()
    assert Path(stored.content_path).exists()
    assert read_artifact_text(config, artifact.id) == "hello shared artifact"
    assert stored.metadata["purpose"] == "demo"


def test_promote_artifact_copies_content_and_lineage(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    temporary = persist_json_artifact(
        config,
        payload={"diff": ["a", "b"]},
        artifact_type="diff_bundle",
        stage="temporary",
        owner_kind="tool_result",
        owner_id="demo.diff",
        project_id="proj_diff",
    )

    verified = promote_artifact(
        config,
        temporary.id,
        stage="verified",
        metadata_updates={"reviewed_by": "critic"},
    )
    final = promote_artifact(
        config,
        verified.id,
        stage="final",
        owner_kind="agent_action_run",
        owner_id="aar_123",
        metadata_updates={"attached_to_run": "aar_123"},
    )

    verified_stored = get_artifact(config, verified.id)
    final_stored = get_artifact(config, final.id)

    assert verified_stored is not None
    assert final_stored is not None
    assert verified_stored.source_artifact_id == temporary.id
    assert final_stored.source_artifact_id == verified.id
    assert verified_stored.stage == "verified"
    assert final_stored.stage == "final"
    assert final_stored.owner_kind == "agent_action_run"
    assert final_stored.owner_id == "aar_123"
    assert final_stored.metadata["attached_to_run"] == "aar_123"
    assert json.loads(read_artifact_text(config, final.id)) == {"diff": ["a", "b"]}


def test_list_artifacts_filters_by_stage_and_session(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    persist_artifact(
        config,
        artifact_id="artf_a",
        content="one",
        artifact_type="task_output",
        stage="verified",
        orchestrator_session_id="ors_keep",
    )
    persist_artifact(
        config,
        artifact_id="artf_b",
        content="two",
        artifact_type="task_output",
        stage="temporary",
        orchestrator_session_id="ors_skip",
    )

    matching = list_artifacts(
        config,
        artifact_type="task_output",
        stage="verified",
        orchestrator_session_id="ors_keep",
    )

    assert [record.id for record in matching] == ["artf_a"]
