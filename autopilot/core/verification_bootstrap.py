"""Verifier bootstrap helpers for `autopilot init-verifiers`."""

from __future__ import annotations

import json
import shlex
import shutil
import tomllib
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.onboarding import ProjectToolingReport, detect_project_tooling
from autopilot.core.project_store import resolve_runtime_project_entry, update_project_entry, utcnow_iso
from autopilot.core.repo_registry import find_canonical_git_root, get_github_repo

VERIFICATION_BOOTSTRAP_RELPATH = ".agents/tasks/verifiers.json"


class VerificationBootstrapError(RuntimeError):
    """Raised when verifier bootstrap cannot proceed safely."""


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text())
    except Exception:
        return {}


def _command_tool_name(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        return ""
    return str(parts[0] if parts else "").strip()


def _tool_available(command: str) -> bool:
    tool_name = _command_tool_name(command)
    if not tool_name:
        return False
    return shutil.which(tool_name) is not None


def _append_check(
    checks: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    *,
    name: str,
    command: str,
    category: str,
    source: str,
    required: bool = True,
    kind: str = "quality_gate",
) -> None:
    key = (name, command)
    if key in seen:
        return
    seen.add(key)
    checks.append(
        {
            "name": name,
            "command": command,
            "category": category,
            "required": required,
            "kind": kind,
            "source": source,
            "tool_name": _command_tool_name(command),
            "tool_available": _tool_available(command),
        }
    )


def _bootstrap_checks(project_path: Path, tooling: ProjectToolingReport) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for gate in tooling.gates:
        name = str(gate.get("name") or "check").strip() or "check"
        command = str(gate.get("cmd") or "").strip()
        if not command:
            continue
        _append_check(
            checks,
            seen,
            name=name,
            command=command,
            category=name,
            required=bool(gate.get("required", True)),
            source=str(gate.get("source") or "tooling"),
            kind="quality_gate",
        )

    if tooling.git_present:
        _append_check(
            checks,
            seen,
            name="patch_hygiene",
            command="git diff --check -- .",
            category="acceptance",
            source="git:patch_hygiene",
            kind="acceptance_check",
        )

    package_json = _read_json(project_path / "package.json")
    scripts = dict(package_json.get("scripts") or {})
    package_manager = str(tooling.package_manager or "").strip()
    for script_name in ("typecheck", "check-types", "check"):
        raw = str(scripts.get(script_name) or "").strip()
        if not raw:
            continue
        command = f"{package_manager} run {script_name}" if package_manager else raw
        _append_check(
            checks,
            seen,
            name="typecheck",
            command=command,
            category="typecheck",
            source=f"package.json:scripts.{script_name}",
            kind="acceptance_check",
        )
        break

    pyproject = _read_toml(project_path / "pyproject.toml")
    tool_section = dict(pyproject.get("tool") or {})
    if (project_path / "pyrightconfig.json").exists() or (project_path / "pyrightconfig.toml").exists():
        _append_check(
            checks,
            seen,
            name="typecheck",
            command="pyright",
            category="typecheck",
            source="python:pyright",
            kind="acceptance_check",
        )
    if (project_path / "mypy.ini").exists() or (project_path / ".mypy.ini").exists() or "mypy" in tool_section:
        _append_check(
            checks,
            seen,
            name="typecheck",
            command="mypy .",
            category="typecheck",
            source="python:mypy",
            kind="acceptance_check",
        )

    return checks


def _build_recommendations(
    tooling: ProjectToolingReport,
    checks: list[dict[str, Any]],
    *,
    project_registered: bool,
) -> list[str]:
    recommendations: list[str] = []
    if not tooling.gates:
        recommendations.append(
            "Add at least one reproducible build, test, or lint command so verifier bootstrap can produce command-backed checks."
        )
    if not project_registered:
        recommendations.append(
            "Run `autopilot init` to register this checkout so detected gates and verifier metadata persist in the project registry."
        )
    unavailable = [check for check in checks if not bool(check.get("tool_available"))]
    if unavailable:
        missing_tools = sorted({str(check.get("tool_name") or "").strip() for check in unavailable if str(check.get("tool_name") or "").strip()})
        if missing_tools:
            recommendations.append(
                f"Install or expose these verifier tools before relying on the generated checks: {', '.join(missing_tools)}."
            )
    if not any(str(check.get("category") or "") == "typecheck" for check in checks) and any(
        stack in {"typescript", "python"} for stack in tooling.stacks
    ):
        recommendations.append(
            "Add an explicit typecheck command if this repo depends on typed interfaces; verifier bootstrap could not discover one automatically."
        )
    if not tooling.git_present:
        recommendations.append(
            "Initialize a Git repository so verifier bootstrap can add patch-hygiene checks and align review/ship flows."
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for item in recommendations:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _artifact_payload(
    *,
    project_path: Path,
    repo_root: Path | None,
    github_repo: str,
    project: dict[str, Any] | None,
    tooling: ProjectToolingReport,
    checks: list[dict[str, Any]],
    recommendations: list[str],
) -> dict[str, Any]:
    return {
        "generated_at": utcnow_iso(),
        "project_path": str(project_path),
        "project_id": str(project.get("id") or "") if project is not None else "",
        "repo_root": str(repo_root) if repo_root is not None else "",
        "github_repo": github_repo,
        "package_manager": tooling.package_manager,
        "stacks": list(tooling.stacks),
        "files_found": list(tooling.files_found),
        "gates": list(tooling.gates),
        "checks": list(checks),
        "notes": list(tooling.notes),
        "recommendations": list(recommendations),
    }


def build_verification_bootstrap(
    config: AutopilotConfig,
    *,
    project_path: Path | str = ".",
    project_id: str | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    """Bootstrap repo-local verifier checks and persist them when requested."""

    normalized_path = _normalize_path(project_path)
    if not normalized_path.exists():
        raise VerificationBootstrapError(f"Directory not found: {normalized_path}")
    if not normalized_path.is_dir():
        raise VerificationBootstrapError(f"Not a directory: {normalized_path}")

    try:
        project = resolve_runtime_project_entry(
            config,
            project_path=normalized_path,
            project_id=project_id,
            include_archived=True,
        )
    except ValueError as exc:
        raise VerificationBootstrapError(str(exc)) from exc
    if project_id and project is None:
        raise VerificationBootstrapError("Project not found in the Autopilot registry for this checkout.")

    tooling = detect_project_tooling(normalized_path)
    checks = _bootstrap_checks(normalized_path, tooling)
    recommendations = _build_recommendations(tooling, checks, project_registered=project is not None)
    repo_root = find_canonical_git_root(normalized_path)
    github_repo = get_github_repo(repo_root) if repo_root is not None else ""

    artifact_path = normalized_path / VERIFICATION_BOOTSTRAP_RELPATH
    artifact_written = False
    artifact_payload = _artifact_payload(
        project_path=normalized_path,
        repo_root=repo_root,
        github_repo=github_repo,
        project=project,
        tooling=tooling,
        checks=checks,
        recommendations=recommendations,
    )
    if write_artifact:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(artifact_payload, indent=2, ensure_ascii=False) + "\n")
        artifact_written = True

    if project is not None:
        project["gates"] = list(tooling.gates)
        project["verification_bootstrap"] = {
            "artifact_relpath": VERIFICATION_BOOTSTRAP_RELPATH if artifact_written else "",
            "updated_at": utcnow_iso(),
            "stack_count": len(tooling.stacks),
            "gate_count": len(tooling.gates),
            "check_count": len(checks),
        }
        update_project_entry(config, project)

    return {
        "project_path": str(normalized_path),
        "project_id": str(project.get("id") or "") if project is not None else "",
        "project_registered": project is not None,
        "artifact_path": str(artifact_path),
        "artifact_written": artifact_written,
        "repo": {
            "repo_root": str(repo_root) if repo_root is not None else "",
            "github_repo": github_repo,
        },
        "tooling": tooling.to_dict(),
        "checks": checks,
        "recommendations": recommendations,
    }
