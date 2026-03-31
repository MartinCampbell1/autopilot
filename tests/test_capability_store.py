"""Tests for runtime connector activation and story team resolution."""

from autopilot.core.capability_store import (
    DEFAULT_CONNECTORS,
    DEFAULT_ROUTING_POLICIES,
    LaunchProfile,
    MCPConnector,
    RoutingPolicy,
    normalize_launch_profile,
    normalize_review_phases,
    activate_connector_set,
    resolve_story_runtime_plan,
)


def test_frontend_story_prefers_browser_and_twenty_first_dev() -> None:
    runtime = resolve_story_runtime_plan(
        {
            "id": 1,
            "title": "Build landing page",
            "description": "Create a responsive UI shell and component library integration.",
            "tags": ["frontend", "ui"],
            "role": "frontend_worker",
        },
        launch_profile={"preset": "team"},
    )

    story = runtime["story"]
    assert "browser_devtools" in story["connectors"]
    assert "twenty_first_dev" in story["connectors"]
    assert runtime["story_pipeline"] == ["research", "implement", "review"]
    assert runtime["review_phases"] == ["security", "architecture", "tests"]
    assert any(member["execution_role"] == "specialist" for member in runtime["team_members"])


def test_custom_context7_connector_is_auto_selected_for_backend_docs_story() -> None:
    context7 = MCPConnector(
        id="context7",
        name="Context7",
        connector_type="custom",
        description="Backend documentation context.",
        transport="http",
        tags=["backend", "docs", "api"],
        providers=["codex", "claude", "gemini"],
        risk_level="low",
        scopes=["network"],
        enabled=True,
        config={"base_url": "https://context7.example.com"},
    )
    runtime = resolve_story_runtime_plan(
        {
            "id": 2,
            "title": "Document FastAPI integration",
            "description": "Research and implement backend API docs flow.",
            "tags": ["backend", "docs", "api"],
            "role": "backend_worker",
        },
        connectors=[*DEFAULT_CONNECTORS, context7],
        routing_policies=[
            *DEFAULT_ROUTING_POLICIES,
            RoutingPolicy(
                role_id="backend_worker",
                preferred_skill_packs=["fastapi-backend"],
                preferred_connectors=["context7"],
            ),
        ],
    )

    assert "context7" in runtime["story"]["connectors"]
    assert any(connector["id"] == "context7" and connector["status"] == "active" for connector in runtime["active_connectors"])


def test_invalid_required_connector_blocks_activation() -> None:
    broken_connector = MCPConnector(
        id="broken_http",
        name="Broken HTTP",
        connector_type="http_api",
        description="Broken required connector.",
        transport="http",
        tags=["backend", "api"],
        providers=["codex"],
        risk_level="medium",
        scopes=["network"],
        enabled=True,
        config={},
        validation_status="invalid",
        last_validation_result={"summary": "Missing required field `base_url`."},
    )

    activations, blocking_errors = activate_connector_set(
        ["broken_http"],
        provider="codex",
        available_connectors=[broken_connector],
        required_connectors=["broken_http"],
    )

    assert activations[0].status == "validation_failed"
    assert blocking_errors == ["Broken HTTP: Missing required field `base_url`."]


def test_parallel_preset_normalizes_to_team_parallel_mode() -> None:
    runtime = resolve_story_runtime_plan(
        {
            "id": 3,
            "title": "Parallel backend slice",
            "description": "Implement backend slices in parallel.",
            "tags": ["backend", "api"],
        },
        launch_profile=LaunchProfile(preset="parallel", story_execution_mode="team", project_concurrency_mode="parallel", max_parallel_stories=3),
    )

    assert runtime["launch_profile"]["project_concurrency_mode"] == "parallel"
    assert runtime["launch_profile"]["max_parallel_stories"] == 3
    assert runtime["launch_profile"]["story_pipeline"] == ["research", "implement", "review"]
    assert runtime["launch_profile"]["review_phases"] == ["security", "architecture", "tests"]


def test_local_provider_defaults_runtime_profile_to_local() -> None:
    profile = normalize_launch_profile({"preset": "team", "provider": "ollama"})

    assert profile.provider == "ollama"
    assert profile.runtime_profile_id == "local"


def test_local_provider_runtime_plan_uses_selected_provider() -> None:
    runtime = resolve_story_runtime_plan(
        {
            "id": 31,
            "title": "Local backend slice",
            "description": "Implement a backend slice on a local runtime.",
            "tags": ["backend", "api"],
        },
        launch_profile={"preset": "team", "provider": "ollama", "runtime_profile_id": "local"},
    )

    assert runtime["launch_profile"]["provider"] == "ollama"
    assert runtime["launch_profile"]["runtime_profile_id"] == "local"
    assert all(member["provider"] == "ollama" for member in runtime["team_members"])
    assert runtime["activation_errors"] == []


def test_story_pipeline_override_can_skip_research_even_in_team_mode() -> None:
    runtime = resolve_story_runtime_plan(
        {
            "id": 4,
            "title": "Backend fix",
            "description": "Implement a targeted backend fix.",
            "tags": ["backend", "api"],
            "pipeline": ["implement", "review"],
        },
        launch_profile={"preset": "team"},
    )

    assert runtime["story_pipeline"] == ["implement", "review"]
    assert all(member["execution_role"] != "specialist" for member in runtime["team_members"])


def test_story_pipeline_override_can_enable_research_from_fast_profile() -> None:
    runtime = resolve_story_runtime_plan(
        {
            "id": 5,
            "title": "Landing page refactor",
            "description": "Improve the frontend shell with prior research.",
            "tags": ["frontend", "ui"],
            "pipeline": ["research", "implement", "review"],
        },
        launch_profile={"preset": "fast"},
    )

    assert runtime["story_pipeline"] == ["research", "implement", "review"]
    assert any(member["execution_role"] == "specialist" for member in runtime["team_members"])


def test_fast_preset_defaults_to_single_broad_review() -> None:
    profile = normalize_launch_profile({"preset": "fast"})

    assert profile.review_phases == []


def test_review_phase_normalization_deduplicates_aliases() -> None:
    assert normalize_review_phases(["sec", "architecture", "qa", "tests"]) == [
        "security",
        "architecture",
        "tests",
    ]
