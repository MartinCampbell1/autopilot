"""Auto-gates runner for build, test, and lint checks."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from autopilot.core.command_semantics import classify_command_exit
from autopilot.core.models import GateResult


def _gate_env(workdir: Path, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build a gate environment that can see project-local toolchains first."""
    env = dict(base_env or os.environ)
    local_bins = [
        workdir / ".venv" / "bin",
        workdir / "venv" / "bin",
        workdir / "env" / "bin",
        workdir / ".venv" / "Scripts",
        workdir / "venv" / "Scripts",
        workdir / "env" / "Scripts",
        workdir / "node_modules" / ".bin",
    ]
    resolved_bins = [str(path) for path in local_bins if path.exists()]
    existing_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join([*resolved_bins, existing_path] if existing_path else resolved_bins)

    for venv_dir in (workdir / ".venv", workdir / "venv", workdir / "env"):
        if venv_dir.exists():
            env.setdefault("VIRTUAL_ENV", str(venv_dir))
            break

    return env


def run_single_gate(
    name: str,
    cmd: str,
    workdir: Path,
    required: bool = True,
    timeout: int = 120,
    base_env: Mapping[str, str] | None = None,
) -> GateResult:
    """Run a single gate command and return its structured result."""
    started_at = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_gate_env(workdir, base_env),
        )
        semantics = classify_command_exit(cmd, int(result.returncode))
        passed = not semantics.treat_as_error
        output = result.stdout + result.stderr
        if result.returncode != 0 and semantics.summary:
            output = f"{output.rstrip()}\nExit semantics: {semantics.summary}".strip()
        exit_code = result.returncode
        exit_semantics = semantics.status
        exit_semantics_summary = semantics.summary
    except subprocess.TimeoutExpired:
        passed = False
        output = f"Timeout after {timeout}s"
        exit_code = None
        exit_semantics = "timeout"
        exit_semantics_summary = f"Command timed out after {timeout}s."
    except Exception as exc:
        passed = False
        output = str(exc)
        exit_code = None
        exit_semantics = "error"
        exit_semantics_summary = str(exc)

    return GateResult(
        name=name,
        cmd=cmd,
        passed=passed,
        output=output.strip()[:2000],
        required=required,
        elapsed_sec=round(time.time() - started_at, 2),
        exit_code=exit_code,
        exit_semantics=exit_semantics,
        exit_semantics_summary=exit_semantics_summary,
    )


def run_gates(
    gates_config: list[dict],
    workdir: Path,
    *,
    quality_baseline: dict[str, bool] | None = None,
    base_env: Mapping[str, str] | None = None,
) -> tuple[bool, list[GateResult]]:
    """Run all configured gates and return overall pass state plus details."""
    results: list[GateResult] = []
    quality_baseline = quality_baseline or {}

    for gate in gates_config:
        result = run_single_gate(
            name=gate.get("name", gate["cmd"]),
            cmd=gate["cmd"],
            workdir=workdir,
            required=gate.get("required", True),
            base_env=base_env,
        )
        baseline_passed = quality_baseline.get(result.name)
        result.baseline_passed = baseline_passed
        result.regression = bool(result.required and baseline_passed is True and not result.passed)
        results.append(result)

    all_required_passed = all(result.passed for result in results if result.required)
    return all_required_passed, results
