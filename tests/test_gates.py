"""Tests for auto-gates runner."""

import subprocess
from pathlib import Path
from stat import S_IXUSR
from unittest.mock import MagicMock, patch

from autopilot.core.gates import run_gates, run_single_gate
from autopilot.core.models import GateResult


class TestRunSingleGate:
    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_passes(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        result = run_single_gate("build", "npm run build", Path("/tmp"), required=True)
        assert result.passed is True
        assert result.name == "build"
        assert mock_run.call_args.args[0] == ["npm", "run", "build"]

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_fails(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: build failed")
        result = run_single_gate("build", "npm run build", Path("/tmp"), required=True)
        assert result.passed is False
        assert "build failed" in result.output
        assert result.exit_code == 1
        assert result.exit_semantics == "error"

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_treats_grep_no_match_as_semantic_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        result = run_single_gate("grep-check", "grep needle README.md", Path("/tmp"), required=True)

        assert result.passed is True
        assert "no matches were found" in result.output.lower()
        assert result.exit_semantics == "no_match"

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_treats_diff_changes_as_semantic_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="1c1", stderr="")

        result = run_single_gate("diff-check", "diff -u old.txt new.txt", Path("/tmp"), required=True)

        assert result.passed is True
        assert "differences were found" in result.output.lower()
        assert result.exit_semantics == "difference"

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=120)
        result = run_single_gate("test", "npm test", Path("/tmp"), required=True)
        assert result.passed is False
        assert "timeout" in result.output.lower()

    def test_gate_uses_project_local_venv_bin(self, tmp_path: Path) -> None:
        marker = tmp_path / "local-ruff-used"
        bin_dir = tmp_path / ".venv" / "bin"
        bin_dir.mkdir(parents=True)
        script = bin_dir / "ruff"
        script.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
        script.chmod(script.stat().st_mode | S_IXUSR)

        result = run_single_gate("lint", "ruff check .", tmp_path, required=True)

        assert result.passed is True
        assert marker.exists()

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_rejects_shell_control_operator_before_execution(self, mock_run: MagicMock) -> None:
        result = run_single_gate("test", "pytest && rm -rf dist", Path("/tmp"), required=True)

        assert result.passed is False
        assert result.exit_semantics == "denied"
        assert "control operator" in result.output.lower()
        mock_run.assert_not_called()

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_rejects_path_expansion_before_execution(self, mock_run: MagicMock) -> None:
        result = run_single_gate("test", "pytest ~/tests", Path("/tmp"), required=True)

        assert result.passed is False
        assert result.exit_semantics == "denied"
        assert "shell expansion" in result.output.lower()
        mock_run.assert_not_called()

    def test_gate_supports_leading_env_assignments(self, tmp_path: Path) -> None:
        result = run_single_gate(
            "env-check",
            "FOUNDEROS_GATE_OK=1 python3 -c 'import os; print(os.environ[\"FOUNDEROS_GATE_OK\"])'",
            tmp_path,
            required=True,
        )

        assert result.passed is True
        assert result.output == "1"

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_reports_grep_no_match_semantics(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        result = run_single_gate("probe", "grep needle README.md", Path("/tmp"), required=False)

        assert result.passed is True
        assert result.exit_semantics == "no_match"
        assert "no matches were found" in result.output.lower()

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_reports_diff_semantics(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        result = run_single_gate("diff", "diff a.txt b.txt", Path("/tmp"), required=False)

        assert result.passed is True
        assert result.exit_semantics == "difference"
        assert "differences were found" in result.output.lower()


class TestRunGates:
    @patch("autopilot.core.gates.run_single_gate")
    def test_all_pass(self, mock_gate: MagicMock) -> None:
        mock_gate.return_value = GateResult(name="build", cmd="x", passed=True, output="ok", required=True)

        gates_config = [
            {"name": "build", "cmd": "npm run build", "required": True},
            {"name": "test", "cmd": "npm test", "required": True},
        ]
        all_passed, results = run_gates(gates_config, Path("/tmp"))
        assert all_passed is True
        assert len(results) == 2

    @patch("autopilot.core.gates.run_single_gate")
    def test_required_fails(self, mock_gate: MagicMock) -> None:
        def side_effect(
            name: str,
            cmd: str,
            workdir: Path,
            required: bool,
            base_env: dict[str, str] | None = None,
        ) -> GateResult:
            if name == "test":
                return GateResult(name=name, cmd=cmd, passed=False, output="fail", required=True)
            return GateResult(name=name, cmd=cmd, passed=True, output="ok", required=required)

        mock_gate.side_effect = side_effect
        gates_config = [
            {"name": "build", "cmd": "npm run build", "required": True},
            {"name": "test", "cmd": "npm test", "required": True},
        ]
        all_passed, results = run_gates(gates_config, Path("/tmp"))
        assert all_passed is False
        assert len(results) == 2

    @patch("autopilot.core.gates.run_single_gate")
    def test_optional_fails_still_passes(self, mock_gate: MagicMock) -> None:
        def side_effect(
            name: str,
            cmd: str,
            workdir: Path,
            required: bool,
            base_env: dict[str, str] | None = None,
        ) -> GateResult:
            if name == "lint":
                return GateResult(name=name, cmd=cmd, passed=False, output="warn", required=False)
            return GateResult(name=name, cmd=cmd, passed=True, output="ok", required=required)

        mock_gate.side_effect = side_effect
        gates_config = [
            {"name": "build", "cmd": "npm run build", "required": True},
            {"name": "lint", "cmd": "npm run lint", "required": False},
        ]
        all_passed, results = run_gates(gates_config, Path("/tmp"))
        assert all_passed is True
        assert len(results) == 2

    @patch("autopilot.core.gates.run_single_gate")
    def test_required_gate_regression_is_flagged(self, mock_gate: MagicMock) -> None:
        mock_gate.return_value = GateResult(name="build", cmd="npm run build", passed=False, output="fail", required=True)

        all_passed, results = run_gates(
            [{"name": "build", "cmd": "npm run build", "required": True}],
            Path("/tmp"),
            quality_baseline={"build": True},
        )

        assert all_passed is False
        assert results[0].baseline_passed is True
        assert results[0].regression is True

    @patch("autopilot.core.gates.run_single_gate")
    def test_first_time_required_failure_is_not_regression(self, mock_gate: MagicMock) -> None:
        mock_gate.return_value = GateResult(name="build", cmd="npm run build", passed=False, output="fail", required=True)

        all_passed, results = run_gates(
            [{"name": "build", "cmd": "npm run build", "required": True}],
            Path("/tmp"),
            quality_baseline={},
        )

        assert all_passed is False
        assert results[0].baseline_passed is None
        assert results[0].regression is False

    @patch("autopilot.core.gates.run_single_gate")
    def test_run_gates_forwards_base_env(self, mock_gate: MagicMock) -> None:
        mock_gate.return_value = GateResult(name="lint", cmd="ruff check .", passed=True, output="ok", required=True)

        run_gates(
            [{"name": "lint", "cmd": "ruff check .", "required": True}],
            Path("/tmp"),
            base_env={"PATH": "/tmp/bin"},
        )

        assert mock_gate.call_args.kwargs["base_env"] == {"PATH": "/tmp/bin"}
