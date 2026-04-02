"""Tests for async runtime-agent task persistence and lifecycle syncing."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.agent_mailbox import list_agent_mailbox_messages
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import (
    ensure_project_state,
    load_project_state,
    normalize_prd,
    register_project,
    save_project_prd,
    save_project_state,
)
from autopilot.core.runtime_agent_tasks import (
    RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_SOURCE_LOG,
    RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_STATE_FALLBACK,
    RUNTIME_AGENT_TASK_SETTLEMENT_REASON_RUNTIME_EXITED,
    RUNTIME_AGENT_TASK_SETTLEMENT_REASON_SUPERSEDED_RUNTIME_SESSION,
    create_or_reuse_runtime_agent_task,
    link_runtime_agent_task_run,
    list_runtime_agent_tasks,
    refresh_runtime_agent_task,
    wait_for_runtime_agent_task_mailbox_resolution,
)
from autopilot.core.task_output import get_task_output, read_task_output_text
from autopilot.core.task_transcript import get_task_transcript, read_task_transcript_text, task_transcript_id


def _seed_project(config: AutopilotConfig, project_path: Path) -> dict[str, object]:
    project_path.mkdir(parents=True, exist_ok=True)
    project = register_project(config, name="Async Project", project_path=project_path)
    prd = normalize_prd(
        {
            "title": "Async Project",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        }
    )
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")
    return project


def test_runtime_agent_task_stays_running_until_project_state_advances(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-project")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id="ors_async_1",
        runtime_agent_ids=["proj:1:worker:a"],
        output_path=str(config.autopilot_home / "logs" / "async.log"),
    )

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "running"
    assert refreshed.result_summary == ""
    assert refreshed.placeholder_result

    stored = list_runtime_agent_tasks(
        config,
        project_id=str(project["id"]),
        orchestrator_session_id="ors_async_1",
        runtime_agent_id="proj:1:worker:a",
        command="launch",
    )
    assert len(stored) == 1
    assert stored[0].id == task.id


def test_runtime_agent_task_stays_running_for_foreground_runtime_without_owner_pid(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-foreground-project")

    state = load_project_state(config, str(project["id"]))
    state["status"] = "running"
    state["paused"] = False
    state["pid"] = None
    state["runtime_session_id"] = ""
    state["started_at"] = "2026-04-01T12:00:00+00:00"
    save_project_state(config, str(project["id"]), state)

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch foreground background work.",
        orchestrator_session_id="ors_async_foreground",
        runtime_agent_ids=["proj:1:worker:a"],
    )

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "running"
    assert refreshed.settlement_reason == ""
    assert refreshed.metadata.get("project_runtime_pid") in {None, ""}


def test_runtime_agent_task_marks_failed_when_owning_background_runtime_exits(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-runtime-exited-project")

    state = load_project_state(config, str(project["id"]))
    state["status"] = "running"
    state["paused"] = False
    state["pid"] = 999_999
    state["runtime_session_id"] = "sess_background_owner"
    state["started_at"] = "2026-04-01T12:00:00+00:00"
    save_project_state(config, str(project["id"]), state)

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id="ors_async_runtime_exit",
        runtime_agent_ids=["proj:1:worker:a"],
    )

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "failed"
    assert refreshed.result_summary == "Background runtime exited before task settlement."
    assert refreshed.settlement_source == "project_state"
    assert refreshed.settlement_reason == RUNTIME_AGENT_TASK_SETTLEMENT_REASON_RUNTIME_EXITED
    assert refreshed.settlement_state_status == "running"
    assert refreshed.result_payload["settlement_reason"] == RUNTIME_AGENT_TASK_SETTLEMENT_REASON_RUNTIME_EXITED
    assert refreshed.history[-1]["extra"]["settlement_reason"] == RUNTIME_AGENT_TASK_SETTLEMENT_REASON_RUNTIME_EXITED
    assert refreshed.metadata["project_runtime_pid"] == 999_999

    mailbox = list_agent_mailbox_messages(
        config,
        project_id=str(project["id"]),
        runtime_agent_id="proj:1:worker:a",
        message_type="runtime_agent_task_resolved",
    )
    assert any(message.payload["task_id"] == task.id for message in mailbox)


def test_runtime_agent_task_marks_cancelled_when_background_runtime_session_is_superseded(
    tmp_path: Path,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-runtime-superseded-project")

    state = load_project_state(config, str(project["id"]))
    state["status"] = "running"
    state["paused"] = False
    state["pid"] = 999_999
    state["runtime_session_id"] = "sess_background_owner_a"
    state["started_at"] = "2026-04-01T12:00:00+00:00"
    save_project_state(config, str(project["id"]), state)

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id="ors_async_runtime_superseded",
        runtime_agent_ids=["proj:1:worker:a"],
    )

    state = load_project_state(config, str(project["id"]))
    state["status"] = "running"
    state["paused"] = False
    state["pid"] = 888_888
    state["runtime_session_id"] = "sess_background_owner_b"
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "cancelled"
    assert refreshed.result_summary == "Background run was superseded by another runtime session before completion."
    assert refreshed.settlement_source == "project_state"
    assert (
        refreshed.settlement_reason
        == RUNTIME_AGENT_TASK_SETTLEMENT_REASON_SUPERSEDED_RUNTIME_SESSION
    )
    assert refreshed.result_payload["settlement_reason"] == (
        RUNTIME_AGENT_TASK_SETTLEMENT_REASON_SUPERSEDED_RUNTIME_SESSION
    )
    assert refreshed.history[-1]["extra"]["settlement_reason"] == (
        RUNTIME_AGENT_TASK_SETTLEMENT_REASON_SUPERSEDED_RUNTIME_SESSION
    )


def test_runtime_agent_task_transitions_to_completed_with_terminal_summary(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-terminal-project")
    log_path = config.autopilot_home / "logs" / "resume.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("worker started\nworker finished cleanly\n", encoding="utf-8")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="resume",
        actor="founderos",
        reason="Resume background work.",
        runtime_agent_ids=["proj:1:worker:a"],
        output_path=str(log_path),
    )

    state = load_project_state(config, str(project["id"]))
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:34:56+00:00"
    state["log_path"] = str(log_path)
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "completed"
    assert refreshed.placeholder_result == ""
    assert refreshed.result_summary == "Background run completed."
    assert refreshed.result_payload["project_status"] == "completed"
    assert refreshed.output_artifact_id
    assert refreshed.output_origin == RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_SOURCE_LOG
    assert refreshed.output_source_available is True
    assert refreshed.result_payload["output_artifact_id"] == refreshed.output_artifact_id
    assert refreshed.result_payload["output_origin"] == RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_SOURCE_LOG
    assert refreshed.result_payload["output_source_available"] is True
    assert refreshed.result_payload["output_generated_from_project_state"] is False
    assert "worker finished cleanly" in refreshed.output_preview
    assert refreshed.completed_at == "2026-04-01T12:34:56+00:00"

    output_record = get_task_output(config, refreshed.output_artifact_id)
    assert output_record is not None
    assert output_record.owner_kind == "runtime_agent_task"
    assert output_record.source_path == str(log_path)
    assert output_record.metadata["output_origin"] == RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_SOURCE_LOG
    assert output_record.metadata["output_source_available"] is True
    assert "worker finished cleanly" in read_task_output_text(config, refreshed.output_artifact_id)


def test_runtime_agent_task_marks_fallback_output_provenance_when_source_log_is_missing(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-fallback-project")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        runtime_agent_ids=["proj:1:worker:a"],
    )

    state = load_project_state(config, str(project["id"]))
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:40:00+00:00"
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "completed"
    assert refreshed.output_artifact_id
    assert refreshed.output_origin == RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_STATE_FALLBACK
    assert refreshed.output_source_available is False
    assert refreshed.settlement_source == "project_state"
    assert refreshed.settlement_reason == "completed"
    assert refreshed.settlement_state_status == "completed"
    assert refreshed.settlement_state_timestamp == "2026-04-01T12:40:00+00:00"
    assert refreshed.result_payload["output_origin"] == RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_STATE_FALLBACK
    assert refreshed.result_payload["output_source_available"] is False
    assert refreshed.result_payload["output_generated_from_project_state"] is True
    assert refreshed.result_payload["settlement_reason"] == "completed"

    output_record = get_task_output(config, refreshed.output_artifact_id)
    assert output_record is not None
    assert output_record.metadata["output_origin"] == RUNTIME_AGENT_TASK_OUTPUT_ORIGIN_STATE_FALLBACK
    assert output_record.metadata["output_source_available"] is False
    assert output_record.metadata["settlement_reason"] == "completed"
    output_text = read_task_output_text(config, refreshed.output_artifact_id)
    assert "Output provenance: synthesized from project state" in output_text
    assert "Settlement reason: completed" in output_text

    transcript_text = read_task_transcript_text(config, task_transcript_id("runtime_agent_task", task.id))
    assert "Output Origin: project_state_fallback" in transcript_text
    assert "Output Source Available: no" in transcript_text
    assert "Settlement Reason: completed" in transcript_text


def test_runtime_agent_task_marks_cancelled_settlement_provenance_when_project_is_paused(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-paused-project")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        runtime_agent_ids=["proj:1:worker:a"],
    )

    state = load_project_state(config, str(project["id"]))
    state["status"] = "paused"
    state["paused"] = True
    state["paused_at"] = "2026-04-01T12:42:00+00:00"
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "cancelled"
    assert refreshed.result_summary == "Background run was paused before completion."
    assert refreshed.settlement_source == "project_state"
    assert refreshed.settlement_reason == "paused"
    assert refreshed.settlement_state_status == "paused"
    assert refreshed.settlement_state_timestamp == "2026-04-01T12:42:00+00:00"
    assert refreshed.result_payload["settlement_reason"] == "paused"
    assert refreshed.result_payload["settlement_state_status"] == "paused"
    assert refreshed.history[-1]["extra"]["settlement_reason"] == "paused"

    transcript_text = read_task_transcript_text(config, task_transcript_id("runtime_agent_task", task.id))
    assert "Settlement Reason: paused" in transcript_text


def test_runtime_agent_task_marks_failed_settlement_provenance_when_project_fails(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-failed-project")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="resume",
        actor="founderos",
        reason="Resume background work.",
        runtime_agent_ids=["proj:1:worker:a"],
    )

    state = load_project_state(config, str(project["id"]))
    state["status"] = "failed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:43:00+00:00"
    state["last_error"] = "Verifier rejected the implementation."
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "failed"
    assert refreshed.result_summary == "Verifier rejected the implementation."
    assert refreshed.settlement_source == "project_state"
    assert refreshed.settlement_reason == "failed"
    assert refreshed.settlement_state_status == "failed"
    assert refreshed.settlement_state_timestamp == "2026-04-01T12:43:00+00:00"
    assert refreshed.result_payload["settlement_reason"] == "failed"
    assert refreshed.result_payload["last_error"] == "Verifier rejected the implementation."
    assert refreshed.history[-1]["extra"]["settlement_reason"] == "failed"


def test_runtime_agent_task_persists_transcript_history_and_run_link(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-transcript-project")
    log_path = config.autopilot_home / "logs" / "launch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("launch started\nlaunch finished\n", encoding="utf-8")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id="ors_async_transcript",
        runtime_agent_ids=["proj:1:worker:a", "proj:1:critic:b"],
        output_path=str(log_path),
    )
    linked = link_runtime_agent_task_run(config, task.id, agent_action_run_id="aar_transcript_1")

    state = load_project_state(config, str(project["id"]))
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:34:56+00:00"
    state["log_path"] = str(log_path)
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)
    transcript_id = task_transcript_id("runtime_agent_task", task.id)
    transcript_record = get_task_transcript(config, transcript_id)

    assert linked.agent_action_run_id == "aar_transcript_1"
    assert transcript_record is not None
    assert transcript_record.owner_kind == "runtime_agent_task"
    assert transcript_record.owner_id == task.id
    assert transcript_record.metadata["agent_action_run_id"] == "aar_transcript_1"
    transcript_text = read_task_transcript_text(config, transcript_id)
    assert f"Task ID: {task.id}" in transcript_text
    assert "Agent Action Run: aar_transcript_1" in transcript_text
    assert "Background run completed." in transcript_text
    assert "task_started" in transcript_text
    assert "linked_agent_action_run" in transcript_text
    assert "task_completed" in transcript_text
    assert refreshed.history[-1]["event"] == "task_completed"


def test_runtime_agent_task_terminal_transition_publishes_resolution_mailbox(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-mailbox-project")
    log_path = config.autopilot_home / "logs" / "mailbox.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("launch started\nlaunch finished\n", encoding="utf-8")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id="ors_async_mailbox",
        runtime_agent_ids=["proj:1:worker:a"],
        output_path=str(log_path),
    )
    link_runtime_agent_task_run(config, task.id, agent_action_run_id="aar_mailbox_1")

    state = load_project_state(config, str(project["id"]))
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:34:56+00:00"
    state["log_path"] = str(log_path)
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)
    messages = list_agent_mailbox_messages(
        config,
        project_id=str(project["id"]),
        runtime_agent_id="proj:1:worker:a",
    )

    assert refreshed.status == "completed"
    assert any(message.message_type == "runtime_agent_task_resolved" for message in messages)
    specific = next(message for message in messages if message.message_type == "runtime_agent_task_completed")
    assert specific.payload["task_id"] == task.id
    assert specific.payload["agent_action_run_id"] == "aar_mailbox_1"
    assert specific.payload["resume_contract"]["task_id"] == task.id


def test_wait_for_runtime_agent_task_mailbox_resolution_refreshes_terminal_task_without_prior_mailbox_event(
    tmp_path: Path,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-mailbox-wait-project")
    log_path = config.autopilot_home / "logs" / "mailbox-wait.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("resume started\nresume finished\n", encoding="utf-8")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="resume",
        actor="founderos",
        reason="Resume background work.",
        runtime_agent_ids=["proj:1:worker:a"],
        output_path=str(log_path),
    )

    state = load_project_state(config, str(project["id"]))
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:36:00+00:00"
    state["log_path"] = str(log_path)
    save_project_state(config, str(project["id"]), state)

    resolved = wait_for_runtime_agent_task_mailbox_resolution(
        config,
        runtime_agent_id="proj:1:worker:a",
        task_id=task.id,
        wait_timeout_sec=0.1,
    )

    assert resolved.id == task.id
    assert resolved.status == "completed"
    mailbox = list_agent_mailbox_messages(
        config,
        project_id=str(project["id"]),
        runtime_agent_id="proj:1:worker:a",
        message_type="runtime_agent_task_resolved",
    )
    assert any(message.payload["task_id"] == task.id for message in mailbox)
