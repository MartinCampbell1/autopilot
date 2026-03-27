"""Tests for project bootstrap helpers."""

import json
from pathlib import Path

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_bootstrap import create_project_from_prd, slugify_project_name


class TestProjectBootstrap:
    def test_slugify_project_name(self) -> None:
        assert slugify_project_name("Graph RAG + Solana") == "graph-rag-solana"

    def test_create_project_from_prd_registers_project(self, tmp_path: Path) -> None:
        config = AutopilotConfig(
            autopilot_home_override=str(tmp_path / ".autopilot"),
            profiles_dir_override=str(tmp_path / ".cli-profiles"),
        )
        prd = {
            "title": "Graph RAG Platform",
            "description": "Build a platform",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start project", "status": "open"}],
        }

        created = create_project_from_prd(config=config, prd=prd, launch=False)

        assert created.name == "Graph RAG Platform"
        assert created.project_id
        assert created.path.exists()
        assert created.prd_path.exists()
        assert json.loads(created.prd_path.read_text())["title"] == "Graph RAG Platform"

        projects_yaml = config.projects_yaml_path
        data = yaml.safe_load(projects_yaml.read_text())
        assert data["projects"][0]["id"] == created.project_id
        assert data["projects"][0]["name"] == "Graph RAG Platform"
        assert Path(data["projects"][0]["path"]) == created.path

        state_path = config.runtime_state_dir / f"{created.project_id}.json"
        assert state_path.exists()
        assert (created.path / "AGENTS.md").exists()
        assert (created.path / ".agents" / "ralph" / "PROMPT_build.md").exists()
        assert (created.path / ".ralph" / "errors.log").exists()
        assert (created.path / ".ralph" / "critic-feedback.md").exists()
