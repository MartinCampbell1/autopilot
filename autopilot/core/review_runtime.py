"""Local structured review helpers for first-class `autopilot review`."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.gates import run_gates
from autopilot.core.models import GateResult
from autopilot.core.onboarding import detect_project_tooling
from autopilot.core.project_store import build_project_summary, resolve_runtime_project_entry
from autopilot.core.repo_registry import find_canonical_git_root, get_github_repo
from autopilot.core.shipping import ShippingError, get_current_branch, get_default_branch


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _finding(
    *,
    code: str,
    severity: str,
    scope: str,
    message: str,
    fix: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "scope": scope,
        "message": message,
        "fix": fix,
        "metadata": dict(metadata or {}),
    }


def _gate_result_payload(result: GateResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "cmd": result.cmd,
        "passed": bool(result.passed),
        "required": bool(result.required),
        "output": str(result.output or ""),
        "elapsed_sec": float(result.elapsed_sec or 0.0),
        "exit_code": result.exit_code,
        "exit_semantics": str(result.exit_semantics or ""),
        "exit_semantics_summary": str(result.exit_semantics_summary or ""),
        "baseline_passed": result.baseline_passed,
        "regression": bool(result.regression),
    }


def _dedupe_gates(*gate_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for gate_set in gate_sets:
        for gate in gate_set:
            key = (str(gate.get("name") or ""), str(gate.get("cmd") or ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(dict(gate))
    return deduped


def _resolve_base_ref(repo_root: Path, base_branch: str) -> str:
    for candidate in (f"refs/remotes/origin/{base_branch}", f"refs/heads/{base_branch}"):
        result = _run_git(repo_root, ["rev-parse", "--verify", candidate])
        if result.returncode == 0:
            return f"origin/{base_branch}" if candidate.startswith("refs/remotes/origin/") else base_branch
    raise ShippingError(f"Base branch `{base_branch}` is not available locally.")


def _working_tree_dirty(repo_root: Path) -> bool:
    result = _run_git(repo_root, ["status", "--porcelain"])
    if result.returncode != 0:
        return False
    return bool(str(result.stdout or "").strip())


def _diff_file_count(repo_root: Path, base_ref: str) -> int | None:
    result = _run_git(repo_root, ["diff", "--name-only", f"{base_ref}...HEAD", "--"])
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in str(result.stdout or "").splitlines() if line.strip()]
    return len(lines)


def _run_adversarial_probe(repo_root: Path, base_ref: str) -> dict[str, Any]:
    result = _run_git(repo_root, ["diff", "--check", f"{base_ref}...HEAD", "--"])
    output = f"{str(result.stdout or '').strip()}\n{str(result.stderr or '').strip()}".strip()
    if result.returncode == 0:
        return {
            "name": "adversarial probe - diff hygiene",
            "command": f"git diff --check {base_ref}...HEAD --",
            "status": "PASS",
            "output": output or "No diff hygiene issues detected.",
            "command_backed": True,
        }
    if result.returncode == 1:
        return {
            "name": "adversarial probe - diff hygiene",
            "command": f"git diff --check {base_ref}...HEAD --",
            "status": "FAIL",
            "output": output or "git diff --check reported patch hygiene issues.",
            "command_backed": True,
        }
    return {
        "name": "adversarial probe - diff hygiene",
        "command": f"git diff --check {base_ref}...HEAD --",
        "status": "PARTIAL",
        "output": output or "Could not complete git diff hygiene probe.",
        "command_backed": True,
    }


def build_local_review(
    config: AutopilotConfig,
    *,
    project_path: Path | str = ".",
    project_id: str | None = None,
    base_branch: str | None = None,
) -> dict[str, Any]:
    """Build a structured local review payload for one project checkout."""

    normalized_path = _normalize_path(project_path)
    tooling = detect_project_tooling(normalized_path)
    findings: list[dict[str, Any]] = []
    registered_project: dict[str, Any] | None = None
    project_summary: dict[str, Any] | None = None

    try:
        registered_project = resolve_runtime_project_entry(
            config,
            project_path=normalized_path,
            project_id=project_id,
            include_archived=True,
        )
    except ValueError as exc:
        findings.append(
            _finding(
                code="project_identity_ambiguous",
                severity="warning",
                scope="project",
                message=str(exc),
                fix="Re-run `autopilot review` with --project-id to inspect one specific registered project.",
            )
        )
    if registered_project is not None:
        project_summary = build_project_summary(config, registered_project)

    repo_root = find_canonical_git_root(normalized_path)
    current_branch = ""
    resolved_base_branch = ""
    base_ref = ""
    diff_file_count: int | None = None
    probe: dict[str, Any] = {
        "name": "adversarial probe - diff hygiene",
        "command": "",
        "status": "PARTIAL",
        "output": "Git diff hygiene probe was not available for this path.",
        "command_backed": False,
    }

    if repo_root is None:
        findings.append(
            _finding(
                code="git_repository_missing",
                severity="warning",
                scope="repo",
                message="Current path is not inside a git repository.",
                fix="Run review from a git checkout so branch and diff context can be inspected.",
            )
        )
    else:
        try:
            current_branch = get_current_branch(repo_root)
        except ShippingError as exc:
            findings.append(
                _finding(
                    code="branch_unavailable",
                    severity="warning",
                    scope="repo",
                    message=str(exc),
                    fix="Check out a named branch before running review.",
                )
            )
        try:
            resolved_base_branch = get_default_branch(repo_root, explicit_base_branch=base_branch)
            base_ref = _resolve_base_ref(repo_root, resolved_base_branch)
            diff_file_count = _diff_file_count(repo_root, base_ref)
            probe = _run_adversarial_probe(repo_root, base_ref)
        except ShippingError as exc:
            findings.append(
                _finding(
                    code="base_branch_unavailable",
                    severity="warning",
                    scope="repo",
                    message=str(exc),
                    fix="Pass --base-branch explicitly or fetch the default branch before review.",
                )
            )
        if not str(get_github_repo(repo_root) or "").strip():
            findings.append(
                _finding(
                    code="repo_identity_missing",
                    severity="info",
                    scope="repo",
                    message="Git repository has no GitHub origin identity.",
                    fix="Add an origin remote if you want review and ship flows to align around GitHub PR state.",
                )
            )
        if _working_tree_dirty(repo_root):
            findings.append(
                _finding(
                    code="working_tree_dirty",
                    severity="info",
                    scope="repo",
                    message="Working tree has uncommitted changes.",
                    fix="Commit or stash changes before treating this review as a durable handoff.",
                )
            )

    explicit_gates = list((registered_project or {}).get("gates") or [])
    review_gates = _dedupe_gates(explicit_gates, list(tooling.gates or []))
    if not review_gates:
        findings.append(
            _finding(
                code="review_evidence_missing",
                severity="warning",
                scope="verification",
                message="No reproducible build, test, or lint gates were available for local review.",
                fix="Add at least one reproducible quality gate so local review can collect command-backed evidence.",
            )
        )
        gates_passed = False
        gate_results: list[GateResult] = []
    else:
        gates_passed, gate_results = run_gates(review_gates, normalized_path)
        for result in gate_results:
            if result.required and not result.passed:
                findings.append(
                    _finding(
                        code="required_gate_failed",
                        severity="error",
                        scope="verification",
                        message=f"Required gate `{result.name}` failed.",
                        fix="Inspect the gate output and fix the blocking issue before shipping.",
                        metadata={
                            "name": result.name,
                            "cmd": result.cmd,
                            "output": str(result.output or ""),
                            "exit_semantics": str(result.exit_semantics or ""),
                        },
                    )
                )

    if probe["status"] == "FAIL":
        findings.append(
            _finding(
                code="adversarial_probe_failed",
                severity="error",
                scope="verification",
                message="Adversarial diff hygiene probe failed.",
                fix="Resolve the patch hygiene issue before treating this change as review-ready.",
                metadata={"output": probe["output"], "command": probe["command"]},
            )
        )
    elif probe["status"] == "PARTIAL":
        findings.append(
            _finding(
                code="adversarial_probe_partial",
                severity="warning",
                scope="verification",
                message="Adversarial probe did not complete with a clean PASS result.",
                fix="Provide a valid base branch or run deeper manual verification before trusting a PASS verdict.",
                metadata={"output": probe["output"], "command": probe["command"]},
            )
        )

    has_errors = any(item["severity"] == "error" for item in findings)
    has_command_backed_evidence = bool(review_gates)
    if has_errors:
        verdict = "FAIL"
    elif has_command_backed_evidence and gates_passed and probe["status"] == "PASS":
        verdict = "PASS"
    else:
        verdict = "PARTIAL"

    return {
        "project_path": str(normalized_path),
        "project": {
            "registered": registered_project is not None,
            "project_id": str((registered_project or {}).get("id") or ""),
            "name": str((registered_project or {}).get("name") or ""),
            "path": str((registered_project or {}).get("path") or ""),
            "delivery_status": dict((project_summary or {}).get("delivery_status") or {}),
            "latest_handoff": dict((project_summary or {}).get("latest_handoff") or {}),
        },
        "repo": {
            "repo_root": str(repo_root) if repo_root is not None else "",
            "current_branch": current_branch,
            "base_branch": resolved_base_branch,
            "github_repo": get_github_repo(repo_root) if repo_root is not None else "",
            "changed_file_count": diff_file_count,
        },
        "tooling": tooling.to_dict(),
        "gates": [_gate_result_payload(result) for result in gate_results],
        "checks": [probe],
        "findings": findings,
        "verdict": verdict,
        "summary": {
            "required_gate_count": sum(1 for gate in review_gates if bool(gate.get("required", True))),
            "gate_count": len(review_gates),
            "passed_gate_count": sum(1 for result in gate_results if result.passed),
            "finding_counts": {
                "error": sum(1 for item in findings if item["severity"] == "error"),
                "warning": sum(1 for item in findings if item["severity"] == "warning"),
                "info": sum(1 for item in findings if item["severity"] == "info"),
            },
            "command_backed_evidence": has_command_backed_evidence,
            "adversarial_probe_status": probe["status"],
        },
    }
