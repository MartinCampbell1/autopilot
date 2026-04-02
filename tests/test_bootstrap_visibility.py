"""Tests for bootstrap visibility helpers."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.bootstrap_visibility import build_bootstrap_status


def test_build_bootstrap_status_detects_verifier_artifact_and_github_workflow(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    verifier_path = project_dir / ".agents" / "tasks"
    verifier_path.mkdir(parents=True)
    (verifier_path / "verifiers.json").write_text("{}")
    workflow_path = project_dir / ".github" / "workflows"
    workflow_path.mkdir(parents=True)
    (workflow_path / "autopilot-bootstrap.yml").write_text("name: Autopilot Checks\n")

    payload = build_bootstrap_status(
        project_path=project_dir,
        project={
            "verification_bootstrap": {"updated_at": "2026-04-02T00:00:00+00:00", "check_count": 4},
            "github_bootstrap": {
                "updated_at": "2026-04-02T00:00:00+00:00",
                "github_repo": "founderos/autopilot",
                "current_branch": "feature/bootstrap",
                "default_branch": "main",
            },
        },
    )

    assert payload["verification"]["artifact_exists"] is True
    assert payload["verification"]["check_count"] == 4
    assert payload["github"]["workflow_exists"] is True
    assert payload["github"]["github_repo"] == "founderos/autopilot"
