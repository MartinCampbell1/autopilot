"""GitHub-oriented renderers for structured local review payloads."""

from __future__ import annotations

from typing import Any, Mapping


def github_review_event_for_verdict(verdict: str) -> str:
    normalized = str(verdict or "").strip().upper()
    if normalized == "PASS":
        return "APPROVE"
    if normalized == "FAIL":
        return "REQUEST_CHANGES"
    return "COMMENT"


def build_github_review_markdown(payload: Mapping[str, Any]) -> str:
    verdict = str(payload.get("verdict") or "PARTIAL").upper()
    repo = dict(payload.get("repo") or {})
    summary = dict(payload.get("summary") or {})
    judge = dict(payload.get("judge") or {})
    findings = [dict(item) for item in list(payload.get("findings") or [])]
    gates = [dict(item) for item in list(payload.get("gates") or [])]
    checks = [dict(item) for item in list(payload.get("checks") or [])]

    lines = [
        "## Autopilot Review",
        "",
        f"- Verdict: `{verdict}`",
        f"- Review event: `{github_review_event_for_verdict(verdict)}`",
    ]
    repo_root = str(repo.get("repo_root") or "").strip()
    if repo_root:
        lines.append(f"- Repo root: `{repo_root}`")
    github_repo = str(repo.get("github_repo") or "").strip()
    if github_repo:
        lines.append(f"- GitHub repo: `{github_repo}`")
    lines.extend(
        [
            f"- Command-backed evidence: `{'yes' if bool(summary.get('command_backed_evidence')) else 'no'}`",
            f"- Adversarial probe: `{str(summary.get('adversarial_probe_status') or '-').upper()}`",
        ]
    )
    if judge:
        lines.extend(
            [
                f"- Judge pack: `{judge.get('pack_id')}`",
                f"- Judge verdict: `{judge.get('verdict')}`",
            ]
        )

    if findings:
        lines.extend(["", "### Findings"])
        for finding in findings:
            severity = str(finding.get("severity") or "info").upper()
            code = str(finding.get("code") or "")
            message = str(finding.get("message") or "").strip()
            fix = str(finding.get("fix") or "").strip()
            bullet = f"- [{severity}] `{code}`: {message}" if code else f"- [{severity}] {message}"
            if fix:
                bullet += f" Fix: {fix}"
            lines.append(bullet)

    if gates:
        lines.extend(["", "### Gate Evidence"])
        for gate in gates:
            lines.append(f"- `{gate.get('name')}`: `{'PASS' if bool(gate.get('passed')) else 'FAIL'}` via `{gate.get('cmd')}`")

    if checks:
        lines.extend(["", "### Checks"])
        for check in checks:
            lines.append(f"- `{check.get('name')}`: `{check.get('status')}` via `{check.get('command')}`")

    if judge and str(judge.get("summary") or "").strip():
        lines.extend(["", "### Judge Summary", str(judge.get("summary"))])
    return "\n".join(lines).strip() + "\n"
