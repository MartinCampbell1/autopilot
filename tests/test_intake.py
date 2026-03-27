"""Tests for intake backend."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.intake import IntakeSession, run_intake_turn, save_prd


class TestIntake:
    @patch("autopilot.core.intake.subprocess.run")
    def test_run_intake_turn_records_messages(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="What stack do you want to use?", stderr="")
        session = IntakeSession(session_id="abc123")

        response = run_intake_turn(
            session=session,
            user_message="I want a bug tracker",
            provider="codex",
            env={"PATH": "/usr/bin"},
        )

        assert response == "What stack do you want to use?"
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"

    @patch("autopilot.core.intake.subprocess.run")
    def test_run_intake_turn_parses_prd_json(self, mock_run: MagicMock) -> None:
        prd = {
            "title": "Bug Tracker",
            "description": "Track bugs",
            "stories": [{"id": 1, "title": "Create project", "description": "Init", "status": "open"}],
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(prd), stderr="")
        session = IntakeSession(session_id="abc123")

        response = run_intake_turn(
            session=session,
            user_message="Generate PRD",
            provider="codex",
            env={"PATH": "/usr/bin"},
        )

        assert json.loads(response)["title"] == "Bug Tracker"
        assert session.prd is not None
        assert session.prd["stories"][0]["status"] == "open"

    def test_save_prd(self, tmp_path: Path) -> None:
        prd = {
            "title": "Bug Tracker",
            "description": "Track bugs",
            "stories": [{"id": 1, "title": "Create project", "description": "Init", "status": "open"}],
        }
        prd_path = save_prd(prd, tmp_path)

        assert prd_path.exists()
        assert prd_path.name.startswith("prd-bug-tracker")
        saved = json.loads(prd_path.read_text())
        assert saved["title"] == "Bug Tracker"
