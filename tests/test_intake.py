"""Tests for intake backend."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.intake import IntakeSession, generate_prd_from_spec, run_intake_turn, save_prd


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
        mock_run.assert_called_once()
        assert "--skip-git-repo-check" in mock_run.call_args.args[0]

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

    @patch("autopilot.core.intake.subprocess.run")
    def test_run_intake_turn_uses_planning_context_and_normalizes_metadata(self, mock_run: MagicMock) -> None:
        prd = {
            "title": "Trading Platform",
            "description": "Automate Solana trading",
            "phases": [{"id": "phase-1", "title": "Foundation", "goal": "Ship the core API"}],
            "stories": [
                {
                    "id": 1,
                    "phase_id": "phase-1",
                    "title": "Build market ingestion API",
                    "description": "Create FastAPI endpoints for token data",
                    "status": "done",
                }
            ],
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(prd), stderr="")
        session = IntakeSession(session_id="abc123")

        run_intake_turn(
            session=session,
            user_message="Generate PRD",
            provider="codex",
            env={"PATH": "/usr/bin"},
            planning_context="Available roles:\n- backend_worker: build APIs",
        )

        prompt = mock_run.call_args.args[0][-1]
        assert "Available roles:" in prompt
        assert session.prd is not None
        assert session.prd["phases"][0]["title"] == "Foundation"
        assert session.prd["stories"][0]["status"] == "open"
        assert session.prd["stories"][0]["role"] == "backend_worker"

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

    @patch("autopilot.core.intake.subprocess.run")
    def test_run_intake_turn_returns_stderr_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Not inside a trusted directory",
        )
        session = IntakeSession(session_id="abc123")

        response = run_intake_turn(
            session=session,
            user_message="Generate PRD",
            provider="codex",
            env={"PATH": "/usr/bin"},
        )

        assert response == "Not inside a trusted directory"

    @patch("autopilot.core.intake.subprocess.run")
    def test_generate_prd_from_spec_uses_existing_json(self, mock_run: MagicMock) -> None:
        prd = {
            "title": "Bug Tracker",
            "description": "Track bugs",
            "stories": [{"id": 1, "title": "Create project", "description": "Init", "status": "open"}],
        }

        parsed = generate_prd_from_spec(json.dumps(prd), provider="codex", env={"PATH": "/usr/bin"})

        assert parsed["title"] == "Bug Tracker"
        mock_run.assert_not_called()

    @patch("autopilot.core.intake.subprocess.run")
    def test_generate_prd_from_spec_parses_model_json(self, mock_run: MagicMock) -> None:
        prd = {
            "title": "Spec Import",
            "description": "Convert spec",
            "stories": [{"id": 1, "title": "Plan", "description": "Plan it", "status": "open"}],
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(prd), stderr="")

        parsed = generate_prd_from_spec("A markdown spec", provider="codex", env={"PATH": "/usr/bin"})

        assert parsed["title"] == "Spec Import"

    @patch("autopilot.core.intake.subprocess.run")
    def test_generate_prd_from_structured_plan_without_subprocess(self, mock_run: MagicMock) -> None:
        spec = """
# Multi-Agent Orchestration Engine

Build a LangGraph-based orchestration engine with multiple orchestration modes.

### Task 1: Install dependencies and add GatewayMiniMax

- [ ] **Step 1: Install langchain-openai**

Run: `pip3 install langchain-openai`
Expected: package installs successfully

- [ ] **Step 2: Add GatewayMiniMax class**

Modify the gateway layer to add a MiniMax client via OpenRouter.

### Task 2: Create orchestrator package and models

- [ ] **Step 1: Create orchestrator package**

Create `/Users/martin/multi-agent/orchestrator/__init__.py` and `models.py`.

- [ ] **Step 2: Verify imports**

Run: `python3 -c "from orchestrator.models import store; print('ok')"`
Expected: `ok`

### Task 3: Smoke test — run a real session

- [ ] **Step 1: Run a debate session**

Expected: returns a session id and running status

- [ ] **Step 2: Poll for completion**

Expected: session completes with debate messages
"""

        parsed = generate_prd_from_spec(spec, provider="codex", env={"PATH": "/usr/bin"})

        assert parsed["title"] == "Multi-Agent Orchestration Engine"
        assert len(parsed["stories"]) == 6
        assert len(parsed["phases"]) >= 2
        assert parsed["stories"][0]["status"] == "open"
        assert parsed["stories"][0]["role"] == "backend_worker"
        assert parsed["stories"][-1]["phase_title"] == "Validation"
        mock_run.assert_not_called()

    @patch("autopilot.core.intake.subprocess.run")
    def test_generate_prd_from_spec_normalizes_rich_planning_output(self, mock_run: MagicMock) -> None:
        prd = {
            "title": "Spec Import",
            "description": "Convert spec",
            "phases": [{"title": "Gateway Integration", "goal": "Integrate the orchestrator"}],
            "stories": [
                {
                    "id": 1,
                    "phase_title": "Gateway Integration",
                    "title": "Create orchestration API endpoints",
                    "description": "Add FastAPI endpoints and gateway integration",
                    "status": "stuck",
                }
            ],
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(prd), stderr="")

        parsed = generate_prd_from_spec(
            "A markdown spec",
            provider="codex",
            env={"PATH": "/usr/bin"},
            planning_context="Available MCP connectors / tools:\n- http_api: Call APIs",
        )

        prompt = mock_run.call_args.args[0][-1]
        assert "Available MCP connectors / tools:" in prompt
        assert parsed["phases"][0]["id"] == "gateway-integration"
        assert parsed["stories"][0]["status"] == "open"
        assert parsed["stories"][0]["role"] == "backend_worker"
        assert "fastapi-backend" in parsed["stories"][0]["skill_packs"]

    @patch("autopilot.core.intake.subprocess.run")
    def test_generate_prd_from_spec_refines_coarse_complex_plan(self, mock_run: MagicMock) -> None:
        initial_prd = {
            "title": "Solana Trader",
            "description": "Build a multi-agent Solana trading platform",
            "phases": [{"id": "phase-1", "title": "Implementation", "goal": "Ship everything"}],
            "stories": [
                {"id": 1, "title": "Backend", "description": "Build the backend"},
                {"id": 2, "title": "Frontend", "description": "Build the dashboard"},
                {"id": 3, "title": "Agents", "description": "Build multi-agent orchestration"},
                {"id": 4, "title": "Deploy", "description": "Deploy the system"},
            ],
        }
        refined_prd = {
            "title": "Solana Trader",
            "description": "Build a multi-agent Solana trading platform",
            "phases": [
                {"id": "phase-1", "title": "Data Foundation", "goal": "Ingest market data"},
                {"id": "phase-2", "title": "Execution Engine", "goal": "Execute strategies safely"},
                {"id": "phase-3", "title": "Operations", "goal": "Observe and control the system"},
            ],
            "stories": [
                {
                    "id": index,
                    "phase_id": f"phase-{1 if index <= 6 else 2 if index <= 12 else 3}",
                    "phase_title": "Detailed Phase",
                    "title": f"Story {index}",
                    "description": f"Concrete task {index} for Solana trading",
                }
                for index in range(1, 19)
            ],
        }
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(initial_prd), stderr=""),
            MagicMock(returncode=0, stdout=json.dumps(refined_prd), stderr=""),
        ]

        parsed = generate_prd_from_spec(
            (
                "Build a multi-agent Solana memecoin trading system with market ingestion, "
                "strategy execution, wallet integration, dashboard, monitoring, and deployment. "
                "It must expose APIs, run orchestration loops, and manage operational controls."
            ),
            provider="codex",
            env={"PATH": "/usr/bin"},
            planning_context="Available roles:\n- backend_worker: build APIs",
        )

        assert mock_run.call_count == 2
        assert len(parsed["stories"]) == 18
        assert len(parsed["phases"]) == 3

    @patch("autopilot.core.intake.subprocess.run")
    def test_generate_prd_from_spec_surfaces_timeout_cleanly(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["codex", "exec", "huge prompt"], timeout=120)

        try:
            generate_prd_from_spec(
                "Short spec that still uses the model",
                provider="codex",
                env={"PATH": "/usr/bin"},
                timeout_sec=120,
            )
        except ValueError as exc:
            message = str(exc)
        else:
            raise AssertionError("Expected ValueError for timeout")

        assert "timed out after 120s" in message
        assert "codex', 'exec'" not in message
