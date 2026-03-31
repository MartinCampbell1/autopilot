"""Onboarding helpers for doctor/init flows."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProjectToolingReport:
    path: str
    exists: bool
    git_present: bool
    prd_present: bool
    ralph_initialized: bool
    package_manager: str | None = None
    stacks: list[str] = field(default_factory=list)
    files_found: list[str] = field(default_factory=list)
    gates: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _add_gate(
    gates: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    *,
    name: str,
    cmd: str,
    required: bool = True,
    source: str,
) -> None:
    key = (name, cmd)
    if key in seen:
        return
    seen.add(key)
    gates.append(
        {
            "name": name,
            "cmd": cmd,
            "required": required,
            "source": source,
        }
    )


def _detect_package_manager(project_path: Path) -> str:
    if (project_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (project_path / "yarn.lock").exists():
        return "yarn"
    if (project_path / "bun.lockb").exists() or (project_path / "bun.lock").exists():
        return "bun"
    return "npm"


def _script_command(package_manager: str, script_name: str) -> str:
    return f"{package_manager} run {script_name}"


def _looks_like_placeholder_test(script: str) -> bool:
    normalized = " ".join(script.strip().lower().split())
    return normalized in {
        'echo "error: no test specified" && exit 1',
        "echo error: no test specified && exit 1",
        "exit 1",
    }


def _read_package_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _read_pyproject(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text())
    except Exception:
        return {}


def detect_project_tooling(project_path: Path) -> ProjectToolingReport:
    """Infer project stacks and likely gate commands from repository files."""
    project_path = project_path.expanduser().resolve()
    report = ProjectToolingReport(
        path=str(project_path),
        exists=project_path.exists(),
        git_present=(project_path / ".git").exists(),
        prd_present=(project_path / ".agents" / "tasks" / "prd.json").exists(),
        ralph_initialized=(project_path / ".agents" / "ralph" / "loop.sh").exists(),
    )
    if not report.exists:
        report.notes.append("Project path does not exist.")
        return report

    files_found: list[str] = []
    gates: list[dict[str, Any]] = []
    seen_gates: set[tuple[str, str]] = set()
    stacks: set[str] = set()

    package_json_path = project_path / "package.json"
    if package_json_path.exists():
        files_found.append("package.json")
        package_data = _read_package_json(package_json_path)
        scripts = package_data.get("scripts") or {}
        package_manager = _detect_package_manager(project_path)
        report.package_manager = package_manager
        stacks.add("node")

        dependencies = {
            **(package_data.get("dependencies") or {}),
            **(package_data.get("devDependencies") or {}),
        }
        if "typescript" in dependencies:
            stacks.add("typescript")
        if "next" in dependencies:
            stacks.add("nextjs")
        if "react" in dependencies:
            stacks.add("react")

        if "lint" in scripts:
            _add_gate(
                gates,
                seen_gates,
                name="lint",
                cmd=_script_command(package_manager, "lint"),
                source="package.json:scripts.lint",
            )
        if "test" in scripts and not _looks_like_placeholder_test(str(scripts["test"])):
            _add_gate(
                gates,
                seen_gates,
                name="test",
                cmd=_script_command(package_manager, "test"),
                source="package.json:scripts.test",
            )
        if "build" in scripts:
            _add_gate(
                gates,
                seen_gates,
                name="build",
                cmd=_script_command(package_manager, "build"),
                source="package.json:scripts.build",
            )

    pyproject_path = project_path / "pyproject.toml"
    pyproject_data: dict[str, Any] = {}
    if pyproject_path.exists():
        files_found.append("pyproject.toml")
        pyproject_data = _read_pyproject(pyproject_path)
        stacks.add("python")

    if (project_path / "requirements.txt").exists():
        files_found.append("requirements.txt")
        stacks.add("python")

    python_tests_present = (
        (project_path / "tests").exists()
        or (project_path / "pytest.ini").exists()
        or bool(pyproject_data.get("tool", {}).get("pytest", {}).get("ini_options"))
        or bool(pyproject_data.get("tool", {}).get("pytest", {}).get("ini-options"))
    )
    if python_tests_present:
        _add_gate(gates, seen_gates, name="test", cmd="pytest", source="python:test-discovery")

    ruff_present = (
        (project_path / "ruff.toml").exists()
        or (project_path / ".ruff.toml").exists()
        or "ruff" in (pyproject_data.get("tool", {}) or {})
    )
    if ruff_present:
        _add_gate(gates, seen_gates, name="lint", cmd="ruff check .", source="python:ruff")

    cargo_path = project_path / "Cargo.toml"
    if cargo_path.exists():
        files_found.append("Cargo.toml")
        stacks.add("rust")
        _add_gate(gates, seen_gates, name="lint", cmd="cargo clippy --all-targets --all-features -- -D warnings", source="cargo")
        _add_gate(gates, seen_gates, name="test", cmd="cargo test", source="cargo")
        _add_gate(gates, seen_gates, name="build", cmd="cargo build", source="cargo")

    go_mod_path = project_path / "go.mod"
    if go_mod_path.exists():
        files_found.append("go.mod")
        stacks.add("go")
        _add_gate(gates, seen_gates, name="lint", cmd="go vet ./...", source="go.mod")
        _add_gate(gates, seen_gates, name="test", cmd="go test ./...", source="go.mod")
        _add_gate(gates, seen_gates, name="build", cmd="go build ./...", source="go.mod")

    if not report.git_present:
        report.notes.append("No Git repository detected yet.")
    if not report.prd_present:
        report.notes.append("No .agents/tasks/prd.json file found yet.")
    if not report.ralph_initialized:
        report.notes.append("Ralph has not been fully initialized for this project yet.")
    if not gates:
        report.notes.append("No build/test/lint commands were auto-detected.")

    report.files_found = sorted(files_found)
    report.stacks = sorted(stacks)
    report.gates = gates
    return report
