"""Tests for run CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from autopilot.cli.run import (
    _apply_requested_headless_interrupt,
    _project_branch_policy,
    _ready_open_stories,
    _should_use_story_worktree,
    _write_ralph_story_snapshot,
    _write_team_context,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.headless_control import create_headless_control_session
from autopilot.core.project_store import load_project_state, register_project


def _create_project(config: AutopilotConfig, root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    prd_path = root / ".agents" / "tasks" / "prd.json"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        json.dumps(
            {
                "title": "Demo",
                "stories": [
                    {
                        "id": 1,
                        "title": "Bootstrap",
                        "description": "Create the app shell",
                        "status": "open",
                    }
                ],
            }
        )
    )
    return register_project(
        config,
        name="Demo",
        project_path=root,
        prd_relpath=".agents/tasks/prd.json",
    )


def test_write_ralph_story_snapshot_selects_only_requested_story(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    prd_path = project_dir / ".agents" / "tasks" / "prd.json"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        json.dumps(
            {
                "title": "Demo",
                "description": "Demo project",
                "phases": [{"id": "phase-1", "title": "Foundation", "goal": "Bootstrap"}],
                "stories": [
                    {"id": 1, "title": "One", "description": "A", "position": 0, "status": "stuck"},
                    {
                        "id": 2,
                        "title": "Two",
                        "description": "B",
                        "position": 1,
                        "phase_id": "phase-1",
                        "phase_title": "Foundation",
                        "acceptance_criteria": ["Pass a smoke check"],
                        "tags": ["backend", "api"],
                        "role": "backend_worker",
                        "skill_packs": ["fastapi-backend"],
                        "connectors": ["shell_exec", "python_exec"],
                        "status": "open",
                    },
                    {"id": 3, "title": "Three", "description": "C", "position": 2, "status": "done"},
                ],
            }
        )
    )

    snapshot_path = _write_ralph_story_snapshot(
        {
            "name": "Demo",
            "path": str(project_dir),
            "prd": ".agents/tasks/prd.json",
        },
        2,
    )

    snapshot = json.loads(Path(snapshot_path).read_text())

    assert snapshot["phases"][0]["title"] == "Foundation"
    assert [story["status"] for story in snapshot["stories"]] == ["done", "open", "done"]
    assert snapshot["stories"][1]["role"] == "backend_worker"
    assert snapshot["stories"][1]["acceptance_criteria"] == ["Pass a smoke check"]
    assert snapshot["stories"][1]["blocked_by"] == []


def test_ready_open_stories_skips_blocked_dependencies(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    prd_path = project_dir / ".agents" / "tasks" / "prd.json"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        json.dumps(
            {
                "title": "Demo",
                "stories": [
                    {"id": 1, "title": "Foundation", "description": "Bootstrap"},
                    {"id": 2, "title": "Dashboard", "description": "Build UI", "blocked_by": [1]},
                    {"id": 3, "title": "Infra", "description": "Set up CI"},
                ],
            }
        )
    )

    ready = _ready_open_stories(
        {
            "name": "Demo",
            "path": str(project_dir),
            "prd": ".agents/tasks/prd.json",
        },
        {
            "story_state": {
                "1": {"status": "open", "blocked_on": []},
                "2": {"status": "open", "blocked_on": [1]},
                "3": {"status": "open", "blocked_on": []},
            }
        },
    )

    assert [story["id"] for story in ready] == [1, 3]


def test_run_headless_returns_exit_code_and_emits_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.run._run_impl",
        lambda *args, **kwargs: {
            "kind": "run_summary",
            "project_id": "demo",
            "exit_code": 2,
        },
    )

    from autopilot.cli.run import run

    exit_code = run("/tmp/demo", ".agents/tasks/prd.json", "demo", headless=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert exit_code == 2
    assert payload["project_id"] == "demo"
    assert payload["exit_code"] == 2


def test_run_headless_structured_emits_result_envelope(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.run._run_impl",
        lambda *args, **kwargs: {
            "kind": "run_summary",
            "project_id": "demo",
            "exit_code": 0,
        },
    )

    from autopilot.cli.run import run

    exit_code = run("/tmp/demo", ".agents/tasks/prd.json", "demo", headless=True, structured=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert exit_code == 0
    assert payload["type"] == "result"
    assert payload["summary"]["project_id"] == "demo"
    assert payload["is_error"] is False


def test_run_headless_structured_enables_bridge_first_permission_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _StructuredRuntimeStub:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "autopilot.cli.run._run_impl",
        lambda *args, **kwargs: {
            "kind": "run_summary",
            "project_id": "demo",
            "exit_code": 0,
        },
    )

    def _structured_runtime_stub(*, enabled: bool, session_id: str | None = None, metadata: dict[str, object] | None = None):
        captured["enabled"] = enabled
        captured["session_id"] = session_id
        captured["metadata"] = dict(metadata or {})
        return _StructuredRuntimeStub()

    monkeypatch.setattr("autopilot.cli.run.structured_headless_runtime", _structured_runtime_stub)

    from autopilot.cli.run import run

    exit_code = run("/tmp/demo", ".agents/tasks/prd.json", "demo", headless=True, structured=True)

    assert exit_code == 0
    assert captured["enabled"] is True
    assert captured["metadata"] == {
        "mode": "run",
        "permission_bridge_mode": "bridge_first",
    }


def test_run_all_headless_returns_exit_code_and_emits_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.run._run_all_impl",
        lambda **kwargs: {
            "kind": "run_all_summary",
            "exit_code": 1,
            "project_count": 1,
        },
    )

    from autopilot.cli.run import run_all

    exit_code = run_all(headless=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert exit_code == 1
    assert payload["kind"] == "run_all_summary"
    assert payload["project_count"] == 1


def test_run_all_headless_structured_emits_result_envelope(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.run._run_all_impl",
        lambda **kwargs: {
            "kind": "run_all_summary",
            "exit_code": 1,
            "project_count": 1,
        },
    )

    from autopilot.cli.run import run_all

    exit_code = run_all(headless=True, structured=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert exit_code == 1
    assert payload["type"] == "result"
    assert payload["summary"]["kind"] == "run_all_summary"
    assert payload["is_error"] is True


def test_run_all_scheduled_headless_emits_final_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.run.run_scheduled_job",
        lambda **kwargs: {
            "kind": "scheduled_run_summary",
            "exit_code": 1,
            "run_count": 2,
            "runs": [
                {"kind": "run_all_summary", "exit_code": 0, "scheduled_run_index": 1},
                {"kind": "run_all_summary", "exit_code": 1, "scheduled_run_index": 2},
            ],
        },
    )

    from autopilot.cli.run import run_all

    exit_code = run_all(headless=True, schedule="1h", max_runs=2)
    payloads = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]

    assert exit_code == 1
    assert payloads[-1]["kind"] == "scheduled_run_summary"
    assert payloads[-1]["run_count"] == 2
    assert payloads[-1]["exit_code"] == 1


def test_run_structured_requires_headless() -> None:
    from autopilot.cli.run import run

    try:
        run("/tmp/demo", ".agents/tasks/prd.json", "demo", structured=True)
    except Exception as exc:
        assert "--structured requires --headless" in str(exc)
    else:
        raise AssertionError("Expected structured mode to require headless mode.")


def test_apply_requested_headless_interrupt_pauses_project_in_process(tmp_path: Path, monkeypatch) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(
        "autopilot.cli.run._emit_runtime_message",
        lambda **payload: emitted.append(payload),
    )

    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project")
    session = create_headless_control_session(config, project_entry=project, session_id="sess_headless")
    session.request_interrupt("req_interrupt")

    applied = _apply_requested_headless_interrupt(
        control_session=session,
        config=config,
        project_id=project["id"],
        headless=True,
        story_id=1,
    )

    state = load_project_state(config, project["id"])
    assert applied is True
    assert state["paused"] is True
    assert state["status"] == "paused"
    assert state["last_error"] == "Project paused by structured control interrupt."
    assert emitted[0]["event"] == "run_interrupted"


def test_write_team_context_includes_shared_discoveries(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)

    _write_team_context(
        project_dir,
        {"team_mode": "team", "story_pipeline": ["research", "implement", "review"]},
        discoveries=[
            {
                "id": "discovery-1",
                "kind": "warning",
                "title": "Rate limit",
                "detail": "Provider throttles burst traffic.",
                "source": "specialist",
            }
        ],
    )

    payload = json.loads((project_dir / ".ralph" / "team-context.json").read_text())

    assert payload["team_mode"] == "team"
    assert payload["shared_discovery_summary"]["warning"] == 1
    assert payload["shared_discoveries"][0]["title"] == "Rate limit"
    assert payload["team_messages_path"] == ".ralph/team-messages.json"
    assert payload["communication_law"]["explicit_teammate_channel"] == ".ralph/team-messages.json"
    assert payload["communication_law"]["non_channel_artifacts"] == [".ralph/specialist-notes.md"]


def test_write_team_context_summarizes_explicit_team_messages(tmp_path: Path) -> None:
    from autopilot.cli.run import _write_team_context
    from autopilot.core.team_messages import upsert_team_message

    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    upsert_team_message(
        project_dir,
        dedupe_key="story:7:specialist:notes",
        story_id=7,
        source_role="specialist",
        target_role="worker",
        message_type="specialist_notes",
        title="Implementation notes",
        content="Prefer the existing callback validator.",
    )
    upsert_team_message(
        project_dir,
        dedupe_key="story:7:specialist:warning",
        story_id=7,
        source_role="specialist",
        target_role="worker",
        message_type="specialist_warning",
        title="Rate limit risk",
        content="Do not burst the upstream provider.",
    )

    _write_team_context(project_dir, {"team_mode": "team"})

    payload = json.loads((project_dir / ".ralph" / "team-context.json").read_text())

    assert payload["shared_message_summary"] == {
        "specialist_notes": 1,
        "specialist_warning": 1,
    }


def test_project_branch_policy_uses_task_source_contract() -> None:
    policy = _project_branch_policy(
        {
            "task_source": {
                "source_kind": "github_issue",
                "external_id": "42",
                "repo": "martin/autopilot",
                "branch_policy": "isolated_worktree",
                "brief_ref": "",
            }
        }
    )

    assert policy == "isolated_worktree"


def test_should_use_story_worktree_for_isolated_branch_policy(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    (project_dir / ".git").write_text("gitdir: .git")

    should_use = _should_use_story_worktree(
        {
            "task_source": {
                "source_kind": "local_brief",
                "external_id": "",
                "repo": str(project_dir),
                "branch_policy": "isolated_worktree",
                "brief_ref": ".agents/tasks/prd.json",
            }
        },
        project_dir,
        SimpleNamespace(project_concurrency_mode="sequential"),
        parallel_slot=False,
    )

    assert should_use is True
