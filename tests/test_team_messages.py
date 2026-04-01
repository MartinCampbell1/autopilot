"""Tests for explicit teammate message storage."""

from pathlib import Path

from autopilot.core.team_messages import (
    TEAM_MESSAGE_LIMIT,
    load_team_messages,
    team_messages_path,
    upsert_team_message,
)


def test_upsert_team_message_reuses_dedupe_key(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)

    first = upsert_team_message(
        project_dir,
        dedupe_key="story:3:specialist:notes",
        story_id=3,
        source_role="specialist",
        message_type="specialist_notes",
        title="Initial notes",
        content="Use the typed client.",
    )
    second = upsert_team_message(
        project_dir,
        dedupe_key="story:3:specialist:notes",
        story_id=3,
        source_role="specialist",
        message_type="specialist_notes",
        title="Updated notes",
        content="Use the typed client and reuse retries.",
    )

    messages = load_team_messages(project_dir)

    assert first.id == second.id
    assert len(messages) == 1
    assert messages[0].title == "Updated notes"
    assert messages[0].content == "Use the typed client and reuse retries."
    assert team_messages_path(project_dir).exists()


def test_upsert_team_message_truncates_and_limits_retention(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)

    for index in range(TEAM_MESSAGE_LIMIT + 5):
        upsert_team_message(
            project_dir,
            dedupe_key=f"story:9:specialist:{index}",
            story_id=9,
            source_role="specialist",
            message_type="specialist_notes",
            title=f"Note {index}",
            content="x" * 13050 if index == TEAM_MESSAGE_LIMIT + 4 else f"note {index}",
        )

    messages = load_team_messages(project_dir)

    assert len(messages) == TEAM_MESSAGE_LIMIT
    assert messages[0].dedupe_key == "story:9:specialist:5"
    assert messages[-1].content.endswith("[truncated]")
