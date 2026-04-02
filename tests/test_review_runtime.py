"""Tests for local review runtime helpers."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import GateResult
from autopilot.core.onboarding import ProjectToolingReport
from autopilot.core.review_runtime import build_local_review


def test_build_local_review_passes_with_gate_evidence_and_probe(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr("autopilot.core.review_runtime.resolve_runtime_project_entry", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "autopilot.core.review_runtime.detect_project_tooling",
        lambda path: ProjectToolingReport(
            path=str(path),
            exists=True,
            git_present=True,
            prd_present=True,
            ralph_initialized=True,
            gates=[{"name": "test", "cmd": "pytest", "required": True, "source": "python:test-discovery"}],
        ),
    )
    monkeypatch.setattr(
        "autopilot.core.review_runtime.run_gates",
        lambda gates, workdir: (True, [GateResult(name="test", cmd="pytest", passed=True, output="ok", required=True)]),
    )
    monkeypatch.setattr("autopilot.core.review_runtime.find_canonical_git_root", lambda path: project)
    monkeypatch.setattr("autopilot.core.review_runtime.get_current_branch", lambda path: "feature/review")
    monkeypatch.setattr("autopilot.core.review_runtime.get_default_branch", lambda path, explicit_base_branch=None: "main")
    monkeypatch.setattr("autopilot.core.review_runtime.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.review_runtime._resolve_base_ref", lambda repo_root, base_branch: "origin/main")
    monkeypatch.setattr("autopilot.core.review_runtime._diff_file_count", lambda repo_root, base_ref: 3)
    monkeypatch.setattr("autopilot.core.review_runtime._working_tree_dirty", lambda repo_root: False)
    monkeypatch.setattr(
        "autopilot.core.review_runtime._run_adversarial_probe",
        lambda repo_root, base_ref: {
            "name": "adversarial probe - diff hygiene",
            "command": "git diff --check origin/main...HEAD --",
            "status": "PASS",
            "output": "clean",
            "command_backed": True,
        },
    )

    payload = build_local_review(config, project_path=project)

    assert payload["verdict"] == "PASS"
    assert payload["summary"]["command_backed_evidence"] is True
    assert payload["summary"]["adversarial_probe_status"] == "PASS"
    assert payload["summary"]["finding_counts"]["error"] == 0


def test_build_local_review_is_partial_without_gates(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr("autopilot.core.review_runtime.resolve_runtime_project_entry", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "autopilot.core.review_runtime.detect_project_tooling",
        lambda path: ProjectToolingReport(
            path=str(path),
            exists=True,
            git_present=False,
            prd_present=False,
            ralph_initialized=False,
            gates=[],
        ),
    )
    monkeypatch.setattr("autopilot.core.review_runtime.find_canonical_git_root", lambda path: None)

    payload = build_local_review(config, project_path=project)

    assert payload["verdict"] == "PARTIAL"
    codes = {finding["code"] for finding in payload["findings"]}
    assert "review_evidence_missing" in codes
    assert "git_repository_missing" in codes


def test_build_local_review_fails_when_required_gate_fails(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr("autopilot.core.review_runtime.resolve_runtime_project_entry", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "autopilot.core.review_runtime.detect_project_tooling",
        lambda path: ProjectToolingReport(
            path=str(path),
            exists=True,
            git_present=True,
            prd_present=True,
            ralph_initialized=True,
            gates=[{"name": "test", "cmd": "pytest", "required": True, "source": "python:test-discovery"}],
        ),
    )
    monkeypatch.setattr(
        "autopilot.core.review_runtime.run_gates",
        lambda gates, workdir: (
            False,
            [
                GateResult(
                    name="test",
                    cmd="pytest",
                    passed=False,
                    output="2 tests failed",
                    required=True,
                    exit_semantics="error",
                )
            ],
        ),
    )
    monkeypatch.setattr("autopilot.core.review_runtime.find_canonical_git_root", lambda path: project)
    monkeypatch.setattr("autopilot.core.review_runtime.get_current_branch", lambda path: "feature/review")
    monkeypatch.setattr("autopilot.core.review_runtime.get_default_branch", lambda path, explicit_base_branch=None: "main")
    monkeypatch.setattr("autopilot.core.review_runtime.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.review_runtime._resolve_base_ref", lambda repo_root, base_branch: "origin/main")
    monkeypatch.setattr("autopilot.core.review_runtime._diff_file_count", lambda repo_root, base_ref: 2)
    monkeypatch.setattr("autopilot.core.review_runtime._working_tree_dirty", lambda repo_root: False)
    monkeypatch.setattr(
        "autopilot.core.review_runtime._run_adversarial_probe",
        lambda repo_root, base_ref: {
            "name": "adversarial probe - diff hygiene",
            "command": "git diff --check origin/main...HEAD --",
            "status": "PASS",
            "output": "clean",
            "command_backed": True,
        },
    )

    payload = build_local_review(config, project_path=project)

    assert payload["verdict"] == "FAIL"
    assert any(finding["code"] == "required_gate_failed" for finding in payload["findings"])
