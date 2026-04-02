"""Tests for verifier bootstrap helpers."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import get_project_entry, register_project
from autopilot.core.verification_bootstrap import VERIFICATION_BOOTSTRAP_RELPATH, build_verification_bootstrap


def test_build_verification_bootstrap_writes_artifact_and_refreshes_registered_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "web"
    project_dir.mkdir(parents=True)
    (project_dir / ".git").mkdir()
    (project_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "web",
                "scripts": {
                    "lint": "eslint .",
                    "test": "vitest run",
                    "build": "next build",
                    "typecheck": "tsc --noEmit",
                },
            }
        )
    )
    (project_dir / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'")

    project = register_project(config, name="Verifier Project", project_path=project_dir)
    monkeypatch.setattr(
        "autopilot.core.verification_bootstrap.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )

    payload = build_verification_bootstrap(config, project_path=project_dir)

    assert payload["project_id"] == project["id"]
    assert payload["project_registered"] is True
    assert payload["artifact_written"] is True
    assert (project_dir / VERIFICATION_BOOTSTRAP_RELPATH).exists()
    commands = [check["command"] for check in payload["checks"]]
    assert "pnpm run lint" in commands
    assert "pnpm run test" in commands
    assert "pnpm run build" in commands
    assert "pnpm run typecheck" in commands
    assert "git diff --check -- ." in commands

    refreshed = get_project_entry(config, project_id=project["id"])
    assert refreshed is not None
    assert refreshed["verification_bootstrap"]["artifact_relpath"] == VERIFICATION_BOOTSTRAP_RELPATH
    assert refreshed["verification_bootstrap"]["check_count"] == len(payload["checks"])
    assert [gate["cmd"] for gate in refreshed["gates"]] == [
        "pnpm run lint",
        "pnpm run test",
        "pnpm run build",
    ]


def test_build_verification_bootstrap_supports_unregistered_python_repo_without_writing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "api"
    project_dir.mkdir(parents=True)
    (project_dir / ".git").mkdir()
    (project_dir / "pyproject.toml").write_text(
        """
[project]
name = "api"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.mypy]
python_version = "3.12"
""".strip()
    )
    (project_dir / "tests").mkdir()
    monkeypatch.setattr(
        "autopilot.core.verification_bootstrap.shutil.which",
        lambda name: f"/usr/bin/{name}" if name in {"pytest", "ruff", "mypy", "git"} else None,
    )

    payload = build_verification_bootstrap(config, project_path=project_dir, write_artifact=False)

    assert payload["project_registered"] is False
    assert payload["artifact_written"] is False
    assert not (project_dir / VERIFICATION_BOOTSTRAP_RELPATH).exists()
    commands = [check["command"] for check in payload["checks"]]
    assert commands == ["pytest", "ruff check .", "git diff --check -- .", "mypy ."]
    assert any("Run `autopilot init`" in item for item in payload["recommendations"])
