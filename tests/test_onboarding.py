"""Tests for onboarding and tooling detection helpers."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.onboarding import detect_project_tooling


def test_detect_project_tooling_for_node_project(tmp_path: Path) -> None:
    project = tmp_path / "web"
    project.mkdir()
    (project / ".git").mkdir()
    (project / "package.json").write_text(
        json.dumps(
            {
                "name": "web",
                "scripts": {
                    "lint": "eslint .",
                    "test": "vitest run",
                    "build": "next build",
                },
                "dependencies": {
                    "next": "16.2.1",
                    "react": "19.2.4",
                },
                "devDependencies": {
                    "typescript": "^5.0.0",
                },
            }
        )
    )
    (project / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'")

    report = detect_project_tooling(project)

    assert report.package_manager == "pnpm"
    assert {"node", "nextjs", "react", "typescript"} <= set(report.stacks)
    assert [gate["cmd"] for gate in report.gates] == [
        "pnpm run lint",
        "pnpm run test",
        "pnpm run build",
    ]


def test_detect_project_tooling_for_python_project(tmp_path: Path) -> None:
    project = tmp_path / "api"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        """
[project]
name = "api"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
""".strip()
    )
    (project / "tests").mkdir()

    report = detect_project_tooling(project)

    assert "python" in report.stacks
    assert [gate["cmd"] for gate in report.gates] == ["pytest", "ruff check ."]
    assert any("No .agents/tasks/prd.json file found yet." == note for note in report.notes)
