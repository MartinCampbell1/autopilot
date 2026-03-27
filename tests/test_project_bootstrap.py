"""Tests for project bootstrap helpers."""

import json
from pathlib import Path

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_bootstrap import create_project_from_prd, slugify_project_name


class TestProjectBootstrap:
    def test_slugify_project_name(self) -> None:
        assert slugify_project_name("Graph RAG + Solana") == "graph-rag-solana"

    def test_create_project_from_prd_registers_project(self, tmp_path: Path, monkeypatch) -> None:
        config = AutopilotConfig(
            autopilot_home_override=str(tmp_path / ".autopilot"),
            profiles_dir_override=str(tmp_path / ".cli-profiles"),
        )
        prd = {
            "title": "Graph RAG Platform",
            "description": "Build a platform",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start project", "status": "open"}],
        }

        monkeypatch.setattr("autopilot.core.project_bootstrap.check_ralph_installed", lambda: False)
        created = create_project_from_prd(config=config, prd=prd, launch=False)

        assert created.name == "Graph RAG Platform"
        assert created.path.exists()
        assert created.prd_path.exists()
        assert json.loads(created.prd_path.read_text())["title"] == "Graph RAG Platform"

        projects_yaml = config.projects_yaml_path
        data = yaml.safe_load(projects_yaml.read_text())
        assert data["projects"][0]["name"] == "Graph RAG Platform"
        assert Path(data["projects"][0]["path"]) == created.path
