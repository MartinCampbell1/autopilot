"""Tests for GitHub-oriented review renderers."""

from autopilot.core.github_review import build_github_review_markdown, github_review_event_for_verdict


def test_github_review_event_for_verdict_maps_expected_actions() -> None:
    assert github_review_event_for_verdict("PASS") == "APPROVE"
    assert github_review_event_for_verdict("FAIL") == "REQUEST_CHANGES"
    assert github_review_event_for_verdict("PARTIAL") == "COMMENT"


def test_build_github_review_markdown_renders_structured_sections() -> None:
    payload = {
        "verdict": "FAIL",
        "project_path": "/tmp/project",
        "repo": {"repo_root": "/tmp/project", "github_repo": "founderos/autopilot"},
        "summary": {"command_backed_evidence": True, "adversarial_probe_status": "PASS"},
        "judge": {
            "pack_id": "execution_claims",
            "verdict": "FAIL",
            "summary": "Judge rejected the review.",
        },
        "findings": [
            {
                "severity": "error",
                "code": "required_gate_failed",
                "message": "Required gate `pytest` failed.",
                "fix": "Inspect the test failure before shipping.",
            }
        ],
        "gates": [{"name": "pytest", "passed": False, "cmd": "pytest -q"}],
        "checks": [
            {
                "name": "adversarial probe - diff hygiene",
                "status": "PASS",
                "command": "git diff --check origin/main...HEAD --",
            }
        ],
    }

    output = build_github_review_markdown(payload)

    assert "## Autopilot Review" in output
    assert "Review event: `REQUEST_CHANGES`" in output
    assert "### Findings" in output
    assert "### Gate Evidence" in output
    assert "### Checks" in output
    assert "### Judge Summary" in output
