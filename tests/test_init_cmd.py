"""Tests for the init CLI helper."""

from __future__ import annotations

from pathlib import Path

from autopilot.cli.init_cmd import init
from autopilot.core.config import AutopilotConfig
from autopilot.core.onboarding import ProjectToolingReport


def _normalize_output(text: str) -> str:
    return "".join(text.split())


def test_init_prints_bootstrap_next_steps_for_gated_github_repo(monkeypatch, tmp_path: Path, capsys) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    monkeypatch.setattr("autopilot.cli.init_cmd.Path.home", lambda: tmp_path)
    monkeypatch.setattr("autopilot.cli.init_cmd.load_config", lambda path: config)
    monkeypatch.setattr("autopilot.cli.init_cmd.save_config", lambda config_obj, path: None)
    monkeypatch.setattr("autopilot.cli.init_cmd.check_ralph_installed", lambda: False)
    monkeypatch.setattr("autopilot.cli.init_cmd.init_ralph_project", lambda project: False)
    monkeypatch.setattr("autopilot.cli.init_cmd.apply_autopilot_ralph_overrides", lambda project: None)
    monkeypatch.setattr(
        "autopilot.cli.init_cmd.detect_project_tooling",
        lambda project: ProjectToolingReport(
            path=str(project),
            exists=True,
            git_present=True,
            prd_present=False,
            ralph_initialized=False,
            package_manager="pnpm",
            stacks=["node", "typescript"],
            files_found=["package.json"],
            gates=[{"name": "test", "cmd": "pnpm run test", "source": "package.json:scripts.test"}],
            notes=[],
        ),
    )
    monkeypatch.setattr("autopilot.cli.init_cmd.get_github_repo", lambda project: "founderos/autopilot")

    init(str(project_dir), idea="", bootstrap_only=False)
    output = _normalize_output(capsys.readouterr().out)

    assert _normalize_output("Run `autopilot doctor` to verify provider sessions and detected gates.") in output
    assert _normalize_output(
        f"Run `autopilot init-verifiers {project_dir}` to persist verifier checks for this checkout."
    ) in output
    assert _normalize_output(
        f"If you want managed CI bootstrap, switch to a feature branch and run `autopilot github {project_dir}`."
    ) in output
    assert _normalize_output(f"Run `autopilot run {project_dir}` when the PRD is ready.") in output


def test_init_prints_non_github_no_gate_guidance(monkeypatch, tmp_path: Path, capsys) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    monkeypatch.setattr("autopilot.cli.init_cmd.Path.home", lambda: tmp_path)
    monkeypatch.setattr("autopilot.cli.init_cmd.load_config", lambda path: config)
    monkeypatch.setattr("autopilot.cli.init_cmd.save_config", lambda config_obj, path: None)
    monkeypatch.setattr("autopilot.cli.init_cmd.check_ralph_installed", lambda: False)
    monkeypatch.setattr("autopilot.cli.init_cmd.init_ralph_project", lambda project: False)
    monkeypatch.setattr("autopilot.cli.init_cmd.apply_autopilot_ralph_overrides", lambda project: None)
    monkeypatch.setattr(
        "autopilot.cli.init_cmd.detect_project_tooling",
        lambda project: ProjectToolingReport(
            path=str(project),
            exists=True,
            git_present=False,
            prd_present=False,
            ralph_initialized=False,
            package_manager=None,
            stacks=[],
            files_found=[],
            gates=[],
            notes=["No build/test/lint commands were auto-detected."],
        ),
    )
    monkeypatch.setattr("autopilot.cli.init_cmd.get_github_repo", lambda project: "")

    init(str(project_dir), idea="", bootstrap_only=False)
    output = _normalize_output(capsys.readouterr().out)

    assert _normalize_output(
        "Add at least one reproducible build, test, or lint command, then re-run `autopilot init-verifiers`."
    ) in output
    assert _normalize_output("autopilot github") not in output
