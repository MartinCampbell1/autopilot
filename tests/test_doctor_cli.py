"""Tests for the doctor CLI/report helpers."""

from __future__ import annotations

from pathlib import Path

from autopilot.cli.doctor import _doctor_report
from autopilot.core.onboarding import ProjectToolingReport


def test_doctor_report_includes_runtime_diagnostics_and_dedupes_recommendations(monkeypatch, tmp_path: Path) -> None:
    fake_config = type(
        "_Config",
        (),
        {
            "autopilot_home": tmp_path / ".autopilot",
            "profiles_dir": tmp_path / ".autopilot" / "profiles",
            "projects_yaml_path": tmp_path / ".autopilot" / "projects.yaml",
        },
    )()

    monkeypatch.setattr("autopilot.cli.doctor.load_config", lambda path: fake_config)
    monkeypatch.setattr("autopilot.cli.doctor.AccountManager", lambda profiles_dir, config: type("_Mgr", (), {"discover": lambda self: None})())
    monkeypatch.setattr(
        "autopilot.cli.doctor.build_provider_setup_snapshot",
        lambda config, manager, refresh=False: {
            "provider_configs": [],
            "runtime_profiles": [],
            "providers": {
                "codex": {
                    "cli_probe": {"status": "missing"},
                    "source_session_required": True,
                    "source_session_available": False,
                    "managed_profile_count": 0,
                }
            },
        },
    )
    monkeypatch.setattr(
        "autopilot.cli.doctor.detect_project_tooling",
        lambda project_path: ProjectToolingReport(
            path=str(project_path),
            exists=True,
            git_present=True,
            prd_present=False,
            ralph_initialized=False,
            gates=[{"name": "test", "cmd": "pytest", "source": "python:test-discovery"}],
            notes=["No build/test/lint commands were auto-detected."],
        ),
    )
    monkeypatch.setattr(
        "autopilot.cli.doctor.build_bootstrap_status",
        lambda **kwargs: {
            "verification": {
                "artifact_exists": False,
                "artifact_path": str(tmp_path / "project" / ".agents" / "tasks" / "verifiers.json"),
            },
            "github": {
                "workflow_exists": False,
                "workflow_path": str(tmp_path / "project" / ".github" / "workflows" / "autopilot-bootstrap.yml"),
            },
        },
    )
    monkeypatch.setattr(
        "autopilot.cli.doctor.build_runtime_diagnostics",
        lambda **kwargs: {
            "diagnostics": [
                {
                    "code": "stale_runtime_pid",
                    "severity": "warning",
                    "scope": "runtime",
                    "message": "Stale runtime detected.",
                    "fix": "Resume or pause this project to reconcile state before relying on its runtime status.",
                },
                {
                    "code": "same_repo_multiple_paths",
                    "severity": "info",
                    "scope": "resume",
                    "message": "Same repo observed in multiple paths.",
                    "fix": "Use `autopilot resume` or `autopilot run --project-id ...` to disambiguate the intended clone/worktree.",
                },
                {
                    "code": "github_cli_missing",
                    "severity": "warning",
                    "scope": "ship",
                    "message": "GitHub CLI is missing.",
                    "fix": "Install GitHub CLI and run `gh auth login` before relying on `autopilot ship`.",
                },
            ],
            "summary": {"error_count": 0, "warning_count": 2, "info_count": 1},
        },
    )

    report = _doctor_report(
        config_path=tmp_path / "config.yaml",
        project_path=tmp_path / "project",
        refresh=False,
    )

    assert report["runtime_diagnostics"]["summary"]["warning_count"] == 2
    assert report["bootstrap"]["verification"]["artifact_exists"] is False
    assert "Install or repair the codex CLI." in report["recommendations"]
    assert "Run `autopilot init` to create a starter PRD and register the project." in report["recommendations"]
    assert "Run `autopilot init-verifiers` to persist generated verifier checks for this repo." in report["recommendations"]
    assert "Resume or pause this project to reconcile state before relying on its runtime status." in report["recommendations"]
    assert "Install GitHub CLI and run `gh auth login` before relying on `autopilot ship`." in report["recommendations"]
    assert len(report["recommendations"]) == len(set(report["recommendations"]))
