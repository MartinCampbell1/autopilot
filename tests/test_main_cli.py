"""Tests for the Typer CLI entrypoint."""

from __future__ import annotations

from typer.testing import CliRunner

from autopilot.cli.main import app

runner = CliRunner()


def test_run_command_passes_headless_option(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        project_path: str,
        prd: str,
        project_id: str | None,
        *,
        headless: bool = False,
        structured: bool = False,
        schedule: str | None = None,
        max_runs: int | None = None,
    ) -> int:
        captured.update(
            {
                "project_path": project_path,
                "prd": prd,
                "project_id": project_id,
                "headless": headless,
                "structured": structured,
                "schedule": schedule,
                "max_runs": max_runs,
            }
        )
        return 0

    monkeypatch.setattr("autopilot.cli.run.run", fake_run)

    result = runner.invoke(app, ["run", "/tmp/project", "--headless"])

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "prd": ".agents/tasks/prd.json",
        "project_id": None,
        "headless": True,
        "structured": False,
        "schedule": None,
        "max_runs": None,
    }


def test_run_command_uses_returned_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(
        "autopilot.cli.run.run",
        lambda project_path, prd, project_id, *, headless=False, structured=False, schedule=None, max_runs=None: 3,
    )

    result = runner.invoke(app, ["run", "/tmp/project", "--headless"])

    assert result.exit_code == 3


def test_run_all_command_passes_headless_option(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_all(
        *,
        headless: bool = False,
        structured: bool = False,
        schedule: str | None = None,
        max_runs: int | None = None,
    ) -> int:
        captured["headless"] = headless
        captured["structured"] = structured
        captured["schedule"] = schedule
        captured["max_runs"] = max_runs
        return 0

    monkeypatch.setattr("autopilot.cli.run.run_all", fake_run_all)

    result = runner.invoke(app, ["run-all", "--headless"])

    assert result.exit_code == 0
    assert captured["headless"] is True
    assert captured["structured"] is False
    assert captured["schedule"] is None
    assert captured["max_runs"] is None


def test_run_all_command_passes_schedule_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_all(
        *,
        headless: bool = False,
        structured: bool = False,
        schedule: str | None = None,
        max_runs: int | None = None,
    ) -> int:
        captured.update({"headless": headless, "structured": structured, "schedule": schedule, "max_runs": max_runs})
        return 0

    monkeypatch.setattr("autopilot.cli.run.run_all", fake_run_all)

    result = runner.invoke(app, ["run-all", "--schedule", "6h", "--max-runs", "3"])

    assert result.exit_code == 0
    assert captured == {
        "headless": False,
        "structured": False,
        "schedule": "6h",
        "max_runs": 3,
    }


def test_run_command_passes_structured_option(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        project_path: str,
        prd: str,
        project_id: str | None,
        *,
        headless: bool = False,
        structured: bool = False,
        schedule: str | None = None,
        max_runs: int | None = None,
    ) -> int:
        captured.update(
            {
                "project_path": project_path,
                "prd": prd,
                "project_id": project_id,
                "headless": headless,
                "structured": structured,
                "schedule": schedule,
                "max_runs": max_runs,
            }
        )
        return 0

    monkeypatch.setattr("autopilot.cli.run.run", fake_run)

    result = runner.invoke(app, ["run", "/tmp/project", "--headless", "--structured"])

    assert result.exit_code == 0
    assert captured["headless"] is True
    assert captured["structured"] is True


def test_run_all_command_passes_structured_option(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_all(
        *,
        headless: bool = False,
        structured: bool = False,
        schedule: str | None = None,
        max_runs: int | None = None,
    ) -> int:
        captured.update(
            {
                "headless": headless,
                "structured": structured,
                "schedule": schedule,
                "max_runs": max_runs,
            }
        )
        return 0

    monkeypatch.setattr("autopilot.cli.run.run_all", fake_run_all)

    result = runner.invoke(app, ["run-all", "--headless", "--structured"])

    assert result.exit_code == 0
    assert captured["headless"] is True
    assert captured["structured"] is True


def test_init_command_passes_bootstrap_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_init(project_path: str, *, idea: str = "", bootstrap_only: bool = False) -> None:
        captured.update(
            {
                "project_path": project_path,
                "idea": idea,
                "bootstrap_only": bootstrap_only,
            }
        )

    monkeypatch.setattr("autopilot.cli.init_cmd.init", fake_init)

    result = runner.invoke(
        app,
        ["init", "/tmp/project", "--idea", "Build a FastAPI bug tracker", "--bootstrap-only"],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "idea": "Build a FastAPI bug tracker",
        "bootstrap_only": True,
    }


def test_init_verifiers_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_init_verifiers(
        project_path: str = ".",
        *,
        project_id: str | None = None,
        write_artifact: bool = True,
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "project_path": project_path,
                "project_id": project_id,
                "write_artifact": write_artifact,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.init_verifiers.init_verifiers", fake_init_verifiers)

    result = runner.invoke(
        app,
        ["init-verifiers", "/tmp/project", "--project-id", "proj_123", "--no-write", "--json"],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "project_id": "proj_123",
        "write_artifact": False,
        "json_output": True,
    }


def test_live_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_live(*, refresh_sec: float = 2.0, once: bool = False) -> None:
        captured.update({"refresh_sec": refresh_sec, "once": once})

    monkeypatch.setattr("autopilot.cli.live.live", fake_live)

    result = runner.invoke(app, ["live", "--refresh-sec", "5", "--once"])

    assert result.exit_code == 0
    assert captured == {"refresh_sec": 5.0, "once": True}


def test_resume_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resume(project_path: str = ".", *, project_id: str | None = None, json_output: bool = False) -> None:
        captured.update(
            {
                "project_path": project_path,
                "project_id": project_id,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.resume.resume", fake_resume)

    result = runner.invoke(app, ["resume", "/tmp/project", "--project-id", "proj_123", "--json"])

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "project_id": "proj_123",
        "json_output": True,
    }


def test_ship_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_ship(
        project_path: str = ".",
        *,
        message: str | None = None,
        title: str | None = None,
        body: str | None = None,
        draft: bool = False,
        base_branch: str | None = None,
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "project_path": project_path,
                "message": message,
                "title": title,
                "body": body,
                "draft": draft,
                "base_branch": base_branch,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.ship.ship", fake_ship)

    result = runner.invoke(
        app,
        [
            "ship",
            "/tmp/project",
            "--message",
            "Ship it",
            "--title",
            "PR title",
            "--body",
            "PR body",
            "--draft",
            "--base-branch",
            "release",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "message": "Ship it",
        "title": "PR title",
        "body": "PR body",
        "draft": True,
        "base_branch": "release",
        "json_output": True,
    }


def test_review_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_review(
        project_path: str = ".",
        *,
        project_id: str | None = None,
        base_branch: str | None = None,
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "project_path": project_path,
                "project_id": project_id,
                "base_branch": base_branch,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.review.review", fake_review)

    result = runner.invoke(
        app,
        [
            "review",
            "/tmp/project",
            "--project-id",
            "proj_123",
            "--base-branch",
            "release",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "project_id": "proj_123",
        "base_branch": "release",
        "json_output": True,
    }


def test_context_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_context(
        project_path: str = ".",
        *,
        project_id: str | None = None,
        event_limit: int = 12,
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "project_path": project_path,
                "project_id": project_id,
                "event_limit": event_limit,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.context.context", fake_context)

    result = runner.invoke(
        app,
        [
            "context",
            "/tmp/project",
            "--project-id",
            "proj_123",
            "--event-limit",
            "5",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "project_id": "proj_123",
        "event_limit": 5,
        "json_output": True,
    }


def test_github_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_github(
        project_path: str = ".",
        *,
        project_id: str | None = None,
        install_workflow: bool = True,
        overwrite: bool = False,
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "project_path": project_path,
                "project_id": project_id,
                "install_workflow": install_workflow,
                "overwrite": overwrite,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.github.github", fake_github)

    result = runner.invoke(
        app,
        [
            "github",
            "/tmp/project",
            "--project-id",
            "proj_123",
            "--no-install",
            "--overwrite",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "project_id": "proj_123",
        "install_workflow": False,
        "overwrite": True,
        "json_output": True,
    }


def test_preview_actions_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_preview_actions(
        session_id: str,
        *,
        actor: str = "cli-control-plane",
        reason: str = "",
        approval_required: bool = False,
        policy_profile: str | None = None,
        limit: int = 20,
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "session_id": session_id,
                "actor": actor,
                "reason": reason,
                "approval_required": approval_required,
                "policy_profile": policy_profile,
                "limit": limit,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.execution_preview.preview_actions", fake_preview_actions)

    result = runner.invoke(
        app,
        [
            "preview-actions",
            "sess_123",
            "--approval-required",
            "--policy-profile",
            "budget_maintenance_with_high_priority_escalation",
            "--limit",
            "5",
            "--actor",
            "founderos",
            "--reason",
            "Preview before apply",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "session_id": "sess_123",
        "actor": "founderos",
        "reason": "Preview before apply",
        "approval_required": True,
        "policy_profile": "budget_maintenance_with_high_priority_escalation",
        "limit": 5,
        "json_output": True,
    }


def test_apply_preview_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_apply_preview(
        preview_id: str,
        *,
        actor: str = "cli-control-plane",
        reason: str = "",
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "preview_id": preview_id,
                "actor": actor,
                "reason": reason,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.execution_preview.apply_preview", fake_apply_preview)

    result = runner.invoke(
        app,
        ["apply-preview", "aar_preview_1", "--actor", "founderos", "--reason", "Apply reviewed preview", "--json"],
    )

    assert result.exit_code == 0
    assert captured == {
        "preview_id": "aar_preview_1",
        "actor": "founderos",
        "reason": "Apply reviewed preview",
        "json_output": True,
    }


def test_approvals_command_passes_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_list_execution_approvals(
        *,
        project_id: str | None = None,
        initiative_id: str | None = None,
        orchestrator: str | None = None,
        status: str | None = "pending",
        action: str | None = None,
        issue_id: str | None = None,
        runtime_agent_id: str | None = None,
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "project_id": project_id,
                "initiative_id": initiative_id,
                "orchestrator": orchestrator,
                "status": status,
                "action": action,
                "issue_id": issue_id,
                "runtime_agent_id": runtime_agent_id,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.execution_approval.list_execution_approvals", fake_list_execution_approvals)

    result = runner.invoke(
        app,
        [
            "approvals",
            "--project-id",
            "proj_123",
            "--initiative-id",
            "init_123",
            "--orchestrator",
            "founderos",
            "--status",
            "approved",
            "--action",
            "update_budget_policy",
            "--issue-id",
            "iss_123",
            "--runtime-agent-id",
            "agent_123",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_id": "proj_123",
        "initiative_id": "init_123",
        "orchestrator": "founderos",
        "status": "approved",
        "action": "update_budget_policy",
        "issue_id": "iss_123",
        "runtime_agent_id": "agent_123",
        "json_output": True,
    }


def test_show_approval_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_show_approval(
        approval_id: str,
        *,
        json_output: bool = False,
    ) -> None:
        captured.update({"approval_id": approval_id, "json_output": json_output})

    monkeypatch.setattr("autopilot.cli.execution_approval.show_approval", fake_show_approval)

    result = runner.invoke(app, ["show-approval", "apr_123", "--json"])

    assert result.exit_code == 0
    assert captured == {"approval_id": "apr_123", "json_output": True}


def test_approve_approval_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_approve_approval(
        approval_id: str,
        *,
        actor: str = "cli-control-plane",
        note: str = "",
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "approval_id": approval_id,
                "actor": actor,
                "note": note,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.execution_approval.approve_approval", fake_approve_approval)

    result = runner.invoke(
        app,
        ["approve-approval", "apr_123", "--actor", "founderos", "--note", "approved", "--json"],
    )

    assert result.exit_code == 0
    assert captured == {
        "approval_id": "apr_123",
        "actor": "founderos",
        "note": "approved",
        "json_output": True,
    }


def test_reject_approval_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_reject_approval(
        approval_id: str,
        *,
        actor: str = "cli-control-plane",
        note: str = "",
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "approval_id": approval_id,
                "actor": actor,
                "note": note,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.execution_approval.reject_approval", fake_reject_approval)

    result = runner.invoke(
        app,
        ["reject-approval", "apr_123", "--actor", "founderos", "--note", "rejected", "--json"],
    )

    assert result.exit_code == 0
    assert captured == {
        "approval_id": "apr_123",
        "actor": "founderos",
        "note": "rejected",
        "json_output": True,
    }


def test_apply_approval_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_apply_approval(
        approval_id: str,
        *,
        actor: str = "cli-control-plane",
        json_output: bool = False,
    ) -> None:
        captured.update(
            {
                "approval_id": approval_id,
                "actor": actor,
                "json_output": json_output,
            }
        )

    monkeypatch.setattr("autopilot.cli.execution_approval.apply_approval", fake_apply_approval)

    result = runner.invoke(app, ["apply-approval", "apr_123", "--actor", "founderos", "--json"])

    assert result.exit_code == 0
    assert captured == {
        "approval_id": "apr_123",
        "actor": "founderos",
        "json_output": True,
    }
