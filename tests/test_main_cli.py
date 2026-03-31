"""Tests for the Typer CLI entrypoint."""

from __future__ import annotations

from typer.testing import CliRunner

from autopilot.cli.main import app

runner = CliRunner()


def test_run_command_passes_headless_option(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        project_path: str,
        prd: str,
        project_id: str | None,
        *,
        headless: bool = False,
        schedule: str | None = None,
        max_runs: int | None = None,
    ) -> int:
        captured.update(
            {
                "project_path": project_path,
                "prd": prd,
                "project_id": project_id,
                "headless": headless,
                "schedule": schedule,
                "max_runs": max_runs,
            }
        )
        return 0

    monkeypatch.setattr("autopilot.cli.run.run", fake_run)

    result = runner.invoke(app, ["run", "/tmp/project", "--headless"])

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "prd": ".agents/tasks/prd.json",
        "project_id": None,
        "headless": True,
        "schedule": None,
        "max_runs": None,
    }


def test_run_command_uses_returned_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(
        "autopilot.cli.run.run",
        lambda project_path, prd, project_id, *, headless=False, schedule=None, max_runs=None: 3,
    )

    result = runner.invoke(app, ["run", "/tmp/project", "--headless"])

    assert result.exit_code == 3


def test_run_all_command_passes_headless_option(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_all(*, headless: bool = False, schedule: str | None = None, max_runs: int | None = None) -> int:
        captured["headless"] = headless
        captured["schedule"] = schedule
        captured["max_runs"] = max_runs
        return 0

    monkeypatch.setattr("autopilot.cli.run.run_all", fake_run_all)

    result = runner.invoke(app, ["run-all", "--headless"])

    assert result.exit_code == 0
    assert captured["headless"] is True
    assert captured["schedule"] is None
    assert captured["max_runs"] is None


def test_run_all_command_passes_schedule_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_all(*, headless: bool = False, schedule: str | None = None, max_runs: int | None = None) -> int:
        captured.update({"headless": headless, "schedule": schedule, "max_runs": max_runs})
        return 0

    monkeypatch.setattr("autopilot.cli.run.run_all", fake_run_all)

    result = runner.invoke(app, ["run-all", "--schedule", "6h", "--max-runs", "3"])

    assert result.exit_code == 0
    assert captured == {
        "headless": False,
        "schedule": "6h",
        "max_runs": 3,
    }


def test_init_command_passes_bootstrap_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_init(project_path: str, *, idea: str = "", bootstrap_only: bool = False) -> None:
        captured.update(
            {
                "project_path": project_path,
                "idea": idea,
                "bootstrap_only": bootstrap_only,
            }
        )

    monkeypatch.setattr("autopilot.cli.init_cmd.init", fake_init)

    result = runner.invoke(
        app,
        ["init", "/tmp/project", "--idea", "Build a FastAPI bug tracker", "--bootstrap-only"],
    )

    assert result.exit_code == 0
    assert captured == {
        "project_path": "/tmp/project",
        "idea": "Build a FastAPI bug tracker",
        "bootstrap_only": True,
    }


def test_live_command_passes_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_live(*, refresh_sec: float = 2.0, once: bool = False) -> None:
        captured.update({"refresh_sec": refresh_sec, "once": once})

    monkeypatch.setattr("autopilot.cli.live.live", fake_live)

    result = runner.invoke(app, ["live", "--refresh-sec", "5", "--once"])

    assert result.exit_code == 0
    assert captured == {"refresh_sec": 5.0, "once": True}
