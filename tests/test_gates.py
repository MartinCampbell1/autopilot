"""Tests for auto-gates runner."""

import subprocess
from pathlib import Path
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

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_fails(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: build failed")
        result = run_single_gate("build", "npm run build", Path("/tmp"), required=True)
        assert result.passed is False
        assert "build failed" in result.output

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=120)
        result = run_single_gate("test", "npm test", Path("/tmp"), required=True)
        assert result.passed is False
        assert "timeout" in result.output.lower()


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
        def side_effect(name: str, cmd: str, workdir: Path, required: bool) -> GateResult:
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
        def side_effect(name: str, cmd: str, workdir: Path, required: bool) -> GateResult:
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
