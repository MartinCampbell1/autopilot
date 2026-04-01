"""Tests for loop runner."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from autopilot.core.loop_runner import (
    apply_autopilot_ralph_overrides,
    append_guardrail,
    build_primary_prompt,
    build_retry_prompt,
    check_git_diff_empty,
    check_ralph_installed,
    get_last_commit_diff,
    init_ralph_project,
    read_quality_ratchet,
    read_progress,
    run_ralph_iteration,
    run_retry_iteration,
    summarize_quality_regressions,
    update_quality_ratchet,
    write_critic_feedback,
)
from autopilot.core.file_snapshot_store import FileSnapshotStaleError
from autopilot.core.models import GateResult


class TestLoopRunner:
    @patch("autopilot.core.loop_runner.shutil.which")
    def test_check_ralph_installed(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/opt/homebrew/bin/ralph"
        assert check_ralph_installed() is True

    @patch("autopilot.core.loop_runner.shutil.which")
    def test_check_ralph_not_installed(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        assert check_ralph_installed() is False

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_init_ralph_project(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert init_ralph_project(tmp_path) is True
        assert (tmp_path / ".agents" / "ralph" / "PROMPT_build.md").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / ".ralph" / "errors.log").exists()

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_init_ralph_project_tty_error_but_agents_installed(self, mock_run: MagicMock, tmp_path: Path) -> None:
        agents_dir = tmp_path / ".agents" / "ralph"
        agents_dir.mkdir(parents=True)
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERR_TTY_INIT_FAILED")
        assert init_ralph_project(tmp_path) is True
        assert (agents_dir / "PROMPT_build.md").exists()
        assert (tmp_path / ".ralph" / "critic-feedback.md").exists()

    def test_apply_autopilot_ralph_overrides_preserves_existing_agents_doc(self, tmp_path: Path) -> None:
        agents_doc = tmp_path / "AGENTS.md"
        agents_doc.write_text("custom")
        loop_script = tmp_path / ".agents" / "ralph" / "loop.sh"
        loop_script.parent.mkdir(parents=True, exist_ok=True)
        loop_script.write_text('for k, v in repl.items():\n    src = src.replace("{{" + k + "}}", v)\n')
        config_script = tmp_path / ".agents" / "ralph" / "config.sh"
        config_script.write_text("# config\n")

        apply_autopilot_ralph_overrides(tmp_path)

        assert agents_doc.read_text() == "custom"
        prompt = (tmp_path / ".agents" / "ralph" / "PROMPT_build.md").read_text()
        assert ".ralph/critic-feedback.md" in prompt
        assert "Read each file from disk before editing it." in prompt
        assert "Do not peek at unfinished sub-work" in prompt
        assert 'str(v)' in loop_script.read_text()
        assert 'ACTIVITY_CMD=".agents/ralph/log-activity.sh"' in config_script.read_text()

    def test_apply_autopilot_ralph_overrides_ignores_stale_safe_edit_failures(self, tmp_path: Path) -> None:
        agents_doc = tmp_path / "AGENTS.md"
        agents_doc.write_text("custom")
        loop_script = tmp_path / ".agents" / "ralph" / "loop.sh"
        loop_script.parent.mkdir(parents=True, exist_ok=True)
        loop_script.write_text('for k, v in repl.items():\n    src = src.replace("{{" + k + "}}", v)\n')
        config_script = tmp_path / ".agents" / "ralph" / "config.sh"
        config_script.write_text("# config\n")

        with (
            patch("autopilot.core.loop_runner.apply_exact_edit", side_effect=FileSnapshotStaleError("stale")),
            patch("autopilot.core.loop_runner.append_with_fresh_snapshot", side_effect=FileSnapshotStaleError("stale")),
        ):
            apply_autopilot_ralph_overrides(tmp_path)

        assert agents_doc.read_text() == "custom"
        assert 'str(v)' not in loop_script.read_text()
        assert 'ACTIVITY_CMD=".agents/ralph/log-activity.sh"' not in config_script.read_text()

    def test_append_guardrail_appends_entries_without_clobbering_existing_lines(self, tmp_path: Path) -> None:
        append_guardrail(tmp_path, "Run tests first.")
        append_guardrail(tmp_path, "Keep diffs narrow.")

        guardrails = (tmp_path / ".ralph" / "guardrails.md").read_text()

        assert guardrails.startswith("# Guardrails\n\nDo not repeat these mistakes:\n\n")
        assert "- Run tests first." in guardrails
        assert guardrails.rstrip().endswith("- Keep diffs narrow.")

    def test_write_and_read_critic_feedback(self, tmp_path: Path) -> None:
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()

        write_critic_feedback(tmp_path, "- callback URL hardcoded\n- no tests")
        content = (ralph_dir / "critic-feedback.md").read_text()
        assert "callback URL" in content

    def test_quality_ratchet_persists_previous_green_gates(self, tmp_path: Path) -> None:
        update_quality_ratchet(
            tmp_path,
            [GateResult(name="pytest", cmd="pytest", passed=True, output="ok", required=True)],
        )
        update_quality_ratchet(
            tmp_path,
            [GateResult(name="pytest", cmd="pytest", passed=False, output="1 failed", required=True)],
        )

        ratchet = read_quality_ratchet(tmp_path)
        assert ratchet["pytest"] is True

    def test_summarize_quality_regressions(self) -> None:
        summary = summarize_quality_regressions(
            [
                GateResult(
                    name="pytest",
                    cmd="pytest",
                    passed=False,
                    output="1 failed",
                    required=True,
                    baseline_passed=True,
                    regression=True,
                )
            ]
        )

        assert "pytest regressed" in summary

    def test_read_progress_missing(self, tmp_path: Path) -> None:
        result = read_progress(tmp_path)
        assert result == ""

    def test_read_progress_exists(self, tmp_path: Path) -> None:
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "progress.md").write_text("# Progress\n- Story 1 done")

        result = read_progress(tmp_path)
        assert "Story 1 done" in result

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_git_diff_empty_true(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert check_git_diff_empty(Path("/tmp")) is True

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_git_diff_empty_false(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="+new line")
        assert check_git_diff_empty(Path("/tmp")) is False

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_run_ralph_iteration_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        success, output, rate_limited = run_ralph_iteration(tmp_path, {"PATH": "/usr/bin"})
        assert success is True
        assert output == "done"
        assert rate_limited is False
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == ["ralph", "build", "1"]

    @patch("autopilot.core.loop_runner._run_command_with_progress")
    def test_run_ralph_iteration_uses_progress_runner_when_callback_provided(
        self,
        mock_progress: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_progress.return_value = (True, "done", False)

        success, output, rate_limited = run_ralph_iteration(
            tmp_path,
            {"PATH": "/usr/bin"},
            on_progress=lambda *_: None,
        )

        assert success is True
        assert output == "done"
        assert rate_limited is False
        mock_progress.assert_called_once()

    @patch("autopilot.core.loop_runner._committed_diff")
    @patch("autopilot.core.loop_runner._working_tree_diff")
    def test_get_last_commit_diff_prefers_worktree(self, mock_worktree: MagicMock, mock_committed: MagicMock) -> None:
        mock_worktree.return_value = "diff --git a/new.py b/new.py"
        mock_committed.return_value = "old commit diff"

        result = get_last_commit_diff(Path("/tmp"))

        assert result == "diff --git a/new.py b/new.py"
        mock_committed.assert_not_called()

    @patch("autopilot.core.loop_runner._committed_diff")
    @patch("autopilot.core.loop_runner._working_tree_diff")
    def test_get_last_commit_diff_falls_back_to_commit(self, mock_worktree: MagicMock, mock_committed: MagicMock) -> None:
        mock_worktree.return_value = ""
        mock_committed.return_value = "commit diff"

        result = get_last_commit_diff(Path("/tmp"))

        assert result == "commit diff"

    def test_build_retry_prompt_includes_story_context(self) -> None:
        prompt = build_retry_prompt(7, "Fix login", "Add OAuth callback validation")
        assert "story #7" in prompt
        assert "Fix login" in prompt
        assert "OAuth callback validation" in prompt
        assert ".ralph/critic-feedback.md" in prompt
        assert "do not patch from memory or stale snippets" in prompt.lower()
        assert "launch or delegate background work" in prompt

    def test_build_primary_prompt_includes_read_before_edit_guardrails(self) -> None:
        prompt = build_primary_prompt(3, "Fix callback", "Tighten OAuth callback validation")
        assert "Read each file from disk before editing it." in prompt
        assert "smallest precise change" in prompt
        assert "report it as launched/running" in prompt
        assert "invent fork results" in prompt

    @patch("autopilot.core.loop_runner.get_adapter")
    def test_run_retry_iteration_success(self, mock_get_adapter: MagicMock, tmp_path: Path) -> None:
        mock_adapter = MagicMock()
        mock_adapter.provider_family = "codex"
        mock_adapter.adapter_id = "codex_local"
        mock_adapter.execute.return_value = SimpleNamespace(success=True, output="fixed", rate_limited=False)
        mock_adapter.parse_output.return_value = SimpleNamespace(text="fixed", rate_limited=False)
        mock_get_adapter.return_value = mock_adapter

        success, output, rate_limited = run_retry_iteration(
            tmp_path,
            {"PATH": "/usr/bin"},
            "codex",
            1,
            "Create README and notes",
            "Create both files",
        )
        assert success is True
        assert output == "fixed"
        assert rate_limited is False
        request = mock_adapter.execute.call_args.args[0]
        assert request.profile.provider == "codex"
        assert "story #1" in request.prompt
        assert "Create README and notes" in request.prompt
