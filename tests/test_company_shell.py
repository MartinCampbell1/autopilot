"""Tests for the always-on company shell builders."""

from pathlib import Path

from autopilot.core.audit_chain import append_jsonl_audit_record
from autopilot.core.company import build_company_shell
from autopilot.core.config import AutopilotConfig, NotificationChannelConfig
from autopilot.core.team_messages import upsert_team_message


def test_build_company_shell_surfaces_goals_routines_channels_and_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        notifications=[
            NotificationChannelConfig(
                name="Slack Alerts",
                kind="slack_webhook",
                webhook_url_env="AUTOPILOT_SLACK_WEBHOOK",
            )
        ],
    )
    monkeypatch.setenv("AUTOPILOT_SLACK_WEBHOOK", "https://hooks.slack.test/services/demo")
    project_path = tmp_path / "company-project"
    project_path.mkdir(parents=True)

    upsert_team_message(
        project_path,
        dedupe_key="kickoff",
        source_role="coordinator",
        message_type="status",
        title="Kickoff",
        content="Start the implementation routine.",
    )
    append_jsonl_audit_record(
        config.events_log_path,
        {
            "project_id": "proj_company",
            "runtime_session_id": "sess_company",
            "event": "run_started",
            "message": "Company shell started the execution loop.",
            "timestamp": "2026-04-02T08:00:00+00:00",
            "story_id": 1,
        },
        chain_kind="events",
        config=config,
    )

    payload = build_company_shell(
        config,
        project={"id": "proj_company", "name": "Company Project", "path": str(project_path)},
        prd={
            "title": "Company Project",
            "description": "Ship the company shell.",
            "phases": [{"id": "phase-1", "title": "Foundation", "goal": "Stand up the runtime shell"}],
        },
        stories=[
            {"id": 1, "title": "Bootstrap shell", "phase_id": "phase-1", "status": "in_progress"},
            {"id": 2, "title": "Document operators", "phase_id": "phase-1", "status": "open"},
        ],
        state={
            "status": "running",
            "paused": False,
            "runtime_session_id": "sess_company",
            "current_story_id": 1,
            "updated_at": "2026-04-02T08:10:00+00:00",
            "timeline": [],
        },
        delivery_status={"status": "in_review"},
        latest_handoff={"url": "https://github.com/founderos/autopilot/pull/12"},
        bootstrap={
            "verification": {"artifact_exists": True},
            "github": {
                "workflow_exists": True,
                "github_repo": "founderos/autopilot",
                "compare_url": "https://github.com/founderos/autopilot/compare/main...feature",
            },
        },
        runtime_diagnostics={"summary": {"error_count": 0, "warning_count": 1, "info_count": 0}},
        runtime_control={"stories": []},
    )

    assert payload["status"]["always_on_ready"] is True
    assert payload["status"]["runtime_wall_enforced"] is True
    assert payload["goals"]["items"][0]["title"] == "Foundation"
    assert payload["goals"]["items"][0]["status"] == "active"
    assert any(item["id"] == "run_loop" for item in payload["routines"]["items"])
    assert any(item["id"] == "dashboard" for item in payload["channels"]["items"])
    assert any(item["id"] == "team_messages" for item in payload["channels"]["items"])
    assert payload["channels"]["summary"]["ready_count"] >= 3
    assert payload["live_events"]["items"][0]["kind"] == "run_started"


def test_build_company_shell_surfaces_missing_channel_secrets(tmp_path: Path) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        notifications=[
            NotificationChannelConfig(
                name="Telegram Ops",
                kind="telegram",
                token_env="AUTOPILOT_TELEGRAM_TOKEN",
                chat_id_env="AUTOPILOT_TELEGRAM_CHAT_ID",
            )
        ],
    )
    project_path = tmp_path / "secrets-project"
    project_path.mkdir(parents=True)

    payload = build_company_shell(
        config,
        project={"id": "proj_secret", "name": "Secrets Project", "path": str(project_path)},
        prd={"title": "Secrets Project", "stories": []},
        stories=[],
        state={"status": "idle", "paused": False, "runtime_session_id": "", "timeline": []},
        delivery_status={"status": "ready_to_run"},
        bootstrap={"verification": {"artifact_exists": False}, "github": {}},
        runtime_diagnostics={"summary": {"error_count": 0, "warning_count": 0, "info_count": 0}},
        runtime_control={"stories": []},
    )

    assert payload["secrets"]["summary"]["missing_count"] == 2
    assert payload["channels"]["summary"]["ready_count"] >= 2
    assert payload["routines"]["items"][-1]["blocked_by"] == ["channel_secrets_missing"]

