"""Persistent registries for MCP connectors, skill packs, and role routing."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig


class MCPConnector(BaseModel):
    """A tool or MCP-backed capability that can be attached to an agent."""

    id: str
    name: str
    connector_type: str
    description: str = ""
    transport: str = "builtin"
    tags: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=lambda: ["codex", "claude", "gemini"])
    risk_level: str = "medium"
    scopes: list[str] = Field(default_factory=list)
    enabled: bool = True
    built_in: bool = False
    config: dict = Field(default_factory=dict)
    validation_status: str = "unknown"
    last_validation_result: dict = Field(default_factory=dict)


class SkillPack(BaseModel):
    """Reusable prompt pack that specializes an agent for a task family."""

    id: str
    name: str
    description: str
    prompt: str
    tags: list[str] = Field(default_factory=list)
    default_roles: list[str] = Field(default_factory=list)
    preferred_connectors: list[str] = Field(default_factory=list)
    enabled: bool = True
    built_in: bool = False


class RoleTemplate(BaseModel):
    """Routing template for a runtime role."""

    id: str
    name: str
    description: str
    default_skill_packs: list[str] = Field(default_factory=list)
    optional_skill_tags: list[str] = Field(default_factory=list)
    default_connectors: list[str] = Field(default_factory=list)
    optional_connector_tags: list[str] = Field(default_factory=list)


class ConnectorFieldSchema(BaseModel):
    """Declarative UI schema for one connector config field."""

    key: str
    label: str
    field_type: str = "text"
    required: bool = False
    placeholder: str = ""
    help_text: str = ""
    options: list[str] = Field(default_factory=list)
    sensitive: bool = False


class ConnectorTypeSchema(BaseModel):
    """Typed schema for one configurable connector family."""

    id: str
    name: str
    description: str
    transport_options: list[str] = Field(default_factory=list)
    default_transport: str = "stdio"
    suggested_tags: list[str] = Field(default_factory=list)
    suggested_scopes: list[str] = Field(default_factory=list)
    config_fields: list[ConnectorFieldSchema] = Field(default_factory=list)


class ConnectorValidationResult(BaseModel):
    """Result of validating a connector configuration."""

    ok: bool
    status: str
    summary: str
    log: str = ""
    checked_fields: list[str] = Field(default_factory=list)


class RoutingPolicy(BaseModel):
    """Per-role override policy for skill packs and connector routing."""

    role_id: str
    preferred_skill_packs: list[str] = Field(default_factory=list)
    required_connectors: list[str] = Field(default_factory=list)
    preferred_connectors: list[str] = Field(default_factory=list)
    forbidden_connectors: list[str] = Field(default_factory=list)


class LaunchProfile(BaseModel):
    """Runtime launch profile chosen by the user for a project run."""

    preset: str = "fast"
    story_execution_mode: str = "solo"
    project_concurrency_mode: str = "sequential"
    max_parallel_stories: int = 1


class LaunchPreset(BaseModel):
    """Human-facing launch mode preset."""

    id: str
    label: str
    description: str
    launch_profile: LaunchProfile


class ConnectorActivation(BaseModel):
    """Resolved runtime activation state for one connector."""

    id: str
    name: str
    connector_type: str
    provider: str
    required: bool = False
    status: str = "disabled"
    reason: str = ""
    config: dict = Field(default_factory=dict)


class TeamMemberAssignment(BaseModel):
    """Resolved runtime assignment for one member of a story team."""

    member_id: str
    label: str
    execution_role: str
    role_id: str
    provider: str
    skill_packs: list[str] = Field(default_factory=list)
    planned_connectors: list[str] = Field(default_factory=list)
    active_connectors: list[ConnectorActivation] = Field(default_factory=list)
    specialist: bool = False


DEFAULT_CONNECTOR_TYPES: list[ConnectorTypeSchema] = [
    ConnectorTypeSchema(
        id="builtin",
        name="Built-in Runtime",
        description="Autopilot-provided local runtime tool with no external setup.",
        transport_options=["builtin"],
        default_transport="builtin",
        suggested_tags=["execution", "local"],
        suggested_scopes=["workspace"],
    ),
    ConnectorTypeSchema(
        id="mcp_server",
        name="External MCP Server",
        description="Attach an MCP-compatible server over stdio or HTTP.",
        transport_options=["stdio", "http"],
        default_transport="stdio",
        suggested_tags=["mcp", "integration"],
        suggested_scopes=["network"],
        config_fields=[
            ConnectorFieldSchema(
                key="command",
                label="Command",
                required=False,
                placeholder="npx your-mcp-server",
                help_text="Required for stdio transport.",
            ),
            ConnectorFieldSchema(
                key="args",
                label="Args JSON",
                field_type="textarea",
                placeholder='["--stdio"]',
                help_text="Optional argument list for the stdio command.",
            ),
            ConnectorFieldSchema(
                key="url",
                label="HTTP URL",
                field_type="url",
                placeholder="https://mcp.example.com",
                help_text="Required for HTTP transport.",
            ),
            ConnectorFieldSchema(
                key="headers",
                label="Headers JSON",
                field_type="textarea",
                placeholder='{"Authorization":"Bearer ..."}',
                help_text="Optional HTTP headers.",
            ),
        ],
    ),
    ConnectorTypeSchema(
        id="http_api",
        name="HTTP API",
        description="REST/JSON endpoint exposed as a connector to workers.",
        transport_options=["http"],
        default_transport="http",
        suggested_tags=["api", "integration", "backend"],
        suggested_scopes=["network"],
        config_fields=[
            ConnectorFieldSchema(
                key="base_url",
                label="Base URL",
                field_type="url",
                required=True,
                placeholder="https://api.example.com",
            ),
            ConnectorFieldSchema(
                key="auth_strategy",
                label="Auth Strategy",
                field_type="select",
                options=["none", "bearer", "basic", "header"],
                placeholder="bearer",
            ),
            ConnectorFieldSchema(
                key="headers",
                label="Headers JSON",
                field_type="textarea",
                placeholder='{"X-API-Key":"..."}',
                help_text="Optional static headers.",
            ),
        ],
    ),
    ConnectorTypeSchema(
        id="neo4j",
        name="Neo4j Graph",
        description="Graph database connection for topology, relationships, and graph RAG work.",
        transport_options=["stdio"],
        default_transport="stdio",
        suggested_tags=["graph", "database", "research"],
        suggested_scopes=["database"],
        config_fields=[
            ConnectorFieldSchema(
                key="uri",
                label="Neo4j URI",
                required=True,
                placeholder="bolt://localhost:7687",
            ),
            ConnectorFieldSchema(
                key="database",
                label="Database",
                placeholder="neo4j",
            ),
            ConnectorFieldSchema(
                key="username",
                label="Username",
                placeholder="neo4j",
            ),
            ConnectorFieldSchema(
                key="password",
                label="Password",
                field_type="password",
                sensitive=True,
            ),
        ],
    ),
    ConnectorTypeSchema(
        id="postgres",
        name="Postgres",
        description="Relational database connection for backend and data verification.",
        transport_options=["stdio"],
        default_transport="stdio",
        suggested_tags=["database", "backend", "data"],
        suggested_scopes=["database"],
        config_fields=[
            ConnectorFieldSchema(
                key="dsn",
                label="Postgres DSN",
                required=True,
                placeholder="postgresql://user:pass@localhost:5432/app",
            ),
        ],
    ),
    ConnectorTypeSchema(
        id="custom",
        name="Custom Connector",
        description="Freeform connector profile for specialized integrations.",
        transport_options=["stdio", "http", "builtin"],
        default_transport="stdio",
        suggested_tags=["custom", "integration"],
        suggested_scopes=["workspace"],
        config_fields=[
            ConnectorFieldSchema(
                key="notes",
                label="Notes",
                field_type="textarea",
                placeholder="What this connector does and how agents should use it.",
            ),
        ],
    ),
]


DEFAULT_CONNECTORS: list[MCPConnector] = [
    MCPConnector(
        id="shell_exec",
        name="Shell",
        connector_type="builtin",
        description="Run shell commands inside the project workspace.",
        tags=["execution", "backend", "infra", "debug"],
        risk_level="high",
        scopes=["workspace"],
        built_in=True,
    ),
    MCPConnector(
        id="python_exec",
        name="Python",
        connector_type="builtin",
        description="Run Python snippets and short scripts for verification or data shaping.",
        tags=["execution", "python", "backend", "data", "debug"],
        risk_level="high",
        scopes=["workspace"],
        built_in=True,
    ),
    MCPConnector(
        id="browser_devtools",
        name="Browser DevTools",
        connector_type="builtin",
        description="Inspect the running UI, verify flows, and capture screenshots.",
        tags=["frontend", "ui", "browser", "qa"],
        risk_level="medium",
        scopes=["localhost", "screenshots"],
        built_in=True,
    ),
    MCPConnector(
        id="web_docs",
        name="Web / Docs Search",
        connector_type="mcp_server",
        description="Search official docs, current specs, and external references.",
        transport="stdio",
        tags=["research", "docs", "api", "frontend", "backend"],
        risk_level="medium",
        scopes=["internet"],
        built_in=True,
    ),
    MCPConnector(
        id="http_api",
        name="HTTP API",
        connector_type="mcp_server",
        description="Call configured HTTP APIs and inspect responses.",
        transport="http",
        tags=["api", "integration", "backend", "qa"],
        risk_level="medium",
        scopes=["network"],
        built_in=True,
    ),
    MCPConnector(
        id="github",
        name="GitHub",
        connector_type="mcp_server",
        description="Inspect repositories, PRs, issues, and code review metadata.",
        transport="stdio",
        tags=["code", "review", "debug", "research"],
        risk_level="medium",
        scopes=["github"],
        built_in=True,
    ),
    MCPConnector(
        id="postgres",
        name="Postgres",
        connector_type="mcp_server",
        description="Query relational data sources for debugging and feature work.",
        transport="stdio",
        tags=["database", "backend", "data"],
        risk_level="high",
        scopes=["database"],
        built_in=True,
    ),
    MCPConnector(
        id="neo4j",
        name="Neo4j Graph",
        connector_type="mcp_server",
        description="Inspect graph data and relationship patterns.",
        transport="stdio",
        tags=["graph", "database", "data", "research"],
        risk_level="high",
        scopes=["database"],
        built_in=True,
    ),
    MCPConnector(
        id="twenty_first_dev",
        name="21st.dev",
        connector_type="mcp_server",
        description="Find UI components and design patterns for frontend work.",
        transport="http",
        tags=["frontend", "ui", "design"],
        risk_level="low",
        scopes=["internet", "design-system"],
        built_in=True,
    ),
]

DEFAULT_SKILL_PACKS: list[SkillPack] = [
    SkillPack(
        id="prd-intake",
        name="PRD Intake",
        description="Turn broad product intent into phased, implementation-ready project plans.",
        prompt=(
            "Break product intent into phases, then stories small enough for a single focused worker "
            "iteration. Prefer explicit deliverables, acceptance criteria, and dependencies."
        ),
        tags=["planning", "intake", "product"],
        default_roles=["planner", "product_analyst"],
        preferred_connectors=["web_docs", "github"],
        built_in=True,
    ),
    SkillPack(
        id="fastapi-backend",
        name="FastAPI Backend",
        description="Design and implement Python/FastAPI backend stories with concrete verification.",
        prompt=(
            "Prefer small vertical slices, explicit API contracts, typed models, and reproducible "
            "backend verification. Call out missing migrations, env vars, and integration edges."
        ),
        tags=["backend", "python", "fastapi", "api"],
        default_roles=["backend_worker", "fullstack_worker"],
        preferred_connectors=["shell_exec", "python_exec", "web_docs", "http_api"],
        built_in=True,
    ),
    SkillPack(
        id="nextjs-frontend",
        name="Next.js Frontend",
        description="Implement UI stories with strong browser verification and component discipline.",
        prompt=(
            "Break UI work into concrete screens/components, verify in the browser, and keep "
            "design-system integration explicit. Prefer exact states, error paths, and loading paths."
        ),
        tags=["frontend", "nextjs", "react", "ui"],
        default_roles=["frontend_worker", "fullstack_worker"],
        preferred_connectors=["browser_devtools", "twenty_first_dev", "web_docs"],
        built_in=True,
    ),
    SkillPack(
        id="qa-review",
        name="QA Review",
        description="Review diffs and behavior with a focus on actionable failures and verification gaps.",
        prompt=(
            "Reject only for concrete, code-backed issues. Prefer explicit failing scenarios, "
            "missing verification, and reproducible regressions over vague feedback."
        ),
        tags=["qa", "review", "critic", "testing"],
        default_roles=["critic", "qa_reviewer"],
        preferred_connectors=["browser_devtools", "github"],
        built_in=True,
    ),
    SkillPack(
        id="debug-investigation",
        name="Debug Investigation",
        description="Investigate runtime failures, logs, and environment mismatches quickly.",
        prompt=(
            "Triage runtime failures from logs first, reproduce with the smallest path, and isolate "
            "root cause before patching. Prefer deterministic fixes and post-fix verification."
        ),
        tags=["debug", "runtime", "ops"],
        default_roles=["runtime_investigator", "backend_worker"],
        preferred_connectors=["shell_exec", "python_exec", "browser_devtools", "http_api"],
        built_in=True,
    ),
    SkillPack(
        id="graph-data",
        name="Graph / Data",
        description="Plan and implement stories that rely on graph queries, analytics, or data pipelines.",
        prompt=(
            "Make schemas, source systems, and validation queries explicit. Prefer small measurable "
            "data tasks instead of broad analytics umbrellas."
        ),
        tags=["graph", "database", "analytics", "data"],
        default_roles=["data_worker", "backend_worker"],
        preferred_connectors=["neo4j", "postgres", "python_exec"],
        built_in=True,
    ),
]

DEFAULT_ROLE_TEMPLATES: list[RoleTemplate] = [
    RoleTemplate(
        id="planner",
        name="Planner",
        description="Break project intent into detailed phases, stories, dependencies, and assignments.",
        default_skill_packs=["prd-intake"],
        optional_skill_tags=["product", "research"],
        default_connectors=["web_docs", "github"],
        optional_connector_tags=["research", "docs"],
    ),
    RoleTemplate(
        id="backend_worker",
        name="Backend Worker",
        description="Implement API, backend, integration, and data stories.",
        default_skill_packs=["fastapi-backend"],
        optional_skill_tags=["backend", "api", "data", "debug"],
        default_connectors=["shell_exec", "python_exec"],
        optional_connector_tags=["backend", "api", "database", "graph", "debug", "docs"],
    ),
    RoleTemplate(
        id="frontend_worker",
        name="Frontend Worker",
        description="Implement UI and browser-facing stories.",
        default_skill_packs=["nextjs-frontend"],
        optional_skill_tags=["frontend", "ui", "design", "debug"],
        default_connectors=["browser_devtools"],
        optional_connector_tags=["frontend", "ui", "design", "docs"],
    ),
    RoleTemplate(
        id="fullstack_worker",
        name="Fullstack Worker",
        description="Handle vertical slices that span frontend and backend.",
        default_skill_packs=["fastapi-backend", "nextjs-frontend"],
        optional_skill_tags=["frontend", "backend", "api", "ui"],
        default_connectors=["shell_exec", "python_exec", "browser_devtools"],
        optional_connector_tags=["frontend", "backend", "api", "docs"],
    ),
    RoleTemplate(
        id="qa_reviewer",
        name="QA Reviewer",
        description="Review deliverables for correctness, verification, and regressions.",
        default_skill_packs=["qa-review"],
        optional_skill_tags=["qa", "testing", "review"],
        default_connectors=["github", "browser_devtools"],
        optional_connector_tags=["qa", "review", "browser"],
    ),
    RoleTemplate(
        id="runtime_investigator",
        name="Runtime Investigator",
        description="Investigate live failures and operational issues.",
        default_skill_packs=["debug-investigation"],
        optional_skill_tags=["debug", "ops", "backend"],
        default_connectors=["shell_exec", "python_exec", "http_api", "browser_devtools"],
        optional_connector_tags=["debug", "runtime", "database", "graph"],
    ),
    RoleTemplate(
        id="data_worker",
        name="Data Worker",
        description="Implement graph, analytics, and data-heavy stories.",
        default_skill_packs=["graph-data"],
        optional_skill_tags=["graph", "database", "analytics", "data"],
        default_connectors=["python_exec", "postgres", "neo4j"],
        optional_connector_tags=["graph", "database", "data", "research"],
    ),
    RoleTemplate(
        id="api_researcher",
        name="API Researcher",
        description="Support backend stories with docs, API discovery, and integration context.",
        default_skill_packs=["debug-investigation"],
        optional_skill_tags=["backend", "api", "docs", "research"],
        default_connectors=["web_docs", "http_api", "github"],
        optional_connector_tags=["docs", "api", "research"],
    ),
]

DEFAULT_ROUTING_POLICIES: list[RoutingPolicy] = [
    RoutingPolicy(role_id="planner", preferred_skill_packs=["prd-intake"], preferred_connectors=["web_docs", "github"]),
    RoutingPolicy(
        role_id="backend_worker",
        preferred_skill_packs=["fastapi-backend"],
        preferred_connectors=["shell_exec", "python_exec", "web_docs", "http_api"],
    ),
    RoutingPolicy(
        role_id="frontend_worker",
        preferred_skill_packs=["nextjs-frontend"],
        preferred_connectors=["browser_devtools", "twenty_first_dev", "web_docs"],
    ),
    RoutingPolicy(
        role_id="fullstack_worker",
        preferred_skill_packs=["fastapi-backend", "nextjs-frontend"],
        preferred_connectors=["shell_exec", "python_exec", "browser_devtools", "web_docs"],
    ),
    RoutingPolicy(
        role_id="qa_reviewer",
        preferred_skill_packs=["qa-review"],
        preferred_connectors=["github", "browser_devtools"],
    ),
    RoutingPolicy(
        role_id="runtime_investigator",
        preferred_skill_packs=["debug-investigation"],
        preferred_connectors=["shell_exec", "python_exec", "http_api", "browser_devtools"],
    ),
    RoutingPolicy(
        role_id="data_worker",
        preferred_skill_packs=["graph-data"],
        preferred_connectors=["neo4j", "postgres", "python_exec"],
    ),
    RoutingPolicy(
        role_id="api_researcher",
        preferred_connectors=["web_docs", "http_api", "github"],
    ),
]

DEFAULT_LAUNCH_PRESETS: list[LaunchPreset] = [
    LaunchPreset(
        id="fast",
        label="Fast",
        description="One primary worker per story, sequential project execution.",
        launch_profile=LaunchProfile(
            preset="fast",
            story_execution_mode="solo",
            project_concurrency_mode="sequential",
            max_parallel_stories=1,
        ),
    ),
    LaunchPreset(
        id="team",
        label="Team",
        description="Primary worker plus critic and optional specialist, sequential stories.",
        launch_profile=LaunchProfile(
            preset="team",
            story_execution_mode="team",
            project_concurrency_mode="sequential",
            max_parallel_stories=1,
        ),
    ),
    LaunchPreset(
        id="parallel",
        label="Parallel",
        description="Story teams with multiple stories active in parallel worktrees.",
        launch_profile=LaunchProfile(
            preset="parallel",
            story_execution_mode="team",
            project_concurrency_mode="parallel",
            max_parallel_stories=3,
        ),
    ),
]


def _atomic_write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    tmp_path.replace(path)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def _registry_item_key(item: BaseModel) -> str:
    if hasattr(item, "id"):
        return getattr(item, "id")
    if hasattr(item, "role_id"):
        return getattr(item, "role_id")
    raise AttributeError(f"Unsupported registry item key for {type(item).__name__}")


def _merge_registry(raw_items: list[dict], defaults: list[BaseModel], model_type):
    merged = {_registry_item_key(item): item for item in defaults}
    for raw in raw_items:
        item = model_type.model_validate(raw)
        key = _registry_item_key(item)
        default = merged.get(key)
        if default and getattr(default, "built_in", False):
            data = default.model_dump()
            data.update(item.model_dump(exclude_unset=False))
            data["built_in"] = True
            merged[key] = model_type.model_validate(data)
        else:
            merged[key] = item
    return list(merged.values())


def load_connectors_registry(config: AutopilotConfig) -> list[MCPConnector]:
    if not config.connectors_json_path.exists():
        return list(DEFAULT_CONNECTORS)
    raw = json.loads(config.connectors_json_path.read_text())
    items = raw.get("connectors", []) if isinstance(raw, dict) else raw
    return _merge_registry(items, DEFAULT_CONNECTORS, MCPConnector)


def save_connectors_registry(config: AutopilotConfig, connectors: list[MCPConnector]) -> None:
    _atomic_write_json(
        config.connectors_json_path,
        {"connectors": [connector.model_dump() for connector in connectors]},
    )


def upsert_connector(config: AutopilotConfig, connector: MCPConnector) -> MCPConnector:
    validation = validate_connector_config(connector)
    connector = connector.model_copy(
        update={
            "validation_status": validation.status,
            "last_validation_result": validation.model_dump(),
        }
    )
    connectors = {item.id: item for item in load_connectors_registry(config)}
    connectors[connector.id] = connector
    save_connectors_registry(config, list(connectors.values()))
    return connector


def delete_connector(config: AutopilotConfig, connector_id: str) -> bool:
    connectors = load_connectors_registry(config)
    kept: list[MCPConnector] = []
    removed = False
    for connector in connectors:
        if connector.id == connector_id and not connector.built_in:
            removed = True
            continue
        kept.append(connector)
    if removed:
        save_connectors_registry(config, kept)
    return removed


def load_skill_packs_registry(config: AutopilotConfig) -> list[SkillPack]:
    if not config.skill_packs_json_path.exists():
        return list(DEFAULT_SKILL_PACKS)
    raw = json.loads(config.skill_packs_json_path.read_text())
    items = raw.get("skill_packs", []) if isinstance(raw, dict) else raw
    return _merge_registry(items, DEFAULT_SKILL_PACKS, SkillPack)


def save_skill_packs_registry(config: AutopilotConfig, skill_packs: list[SkillPack]) -> None:
    _atomic_write_json(
        config.skill_packs_json_path,
        {"skill_packs": [skill_pack.model_dump() for skill_pack in skill_packs]},
    )


def upsert_skill_pack(config: AutopilotConfig, skill_pack: SkillPack) -> SkillPack:
    skill_packs = {item.id: item for item in load_skill_packs_registry(config)}
    skill_packs[skill_pack.id] = skill_pack
    save_skill_packs_registry(config, list(skill_packs.values()))
    return skill_pack


def delete_skill_pack(config: AutopilotConfig, skill_pack_id: str) -> bool:
    skill_packs = load_skill_packs_registry(config)
    kept: list[SkillPack] = []
    removed = False
    for skill_pack in skill_packs:
        if skill_pack.id == skill_pack_id and not skill_pack.built_in:
            removed = True
            continue
        kept.append(skill_pack)
    if removed:
        save_skill_packs_registry(config, kept)
    return removed


def load_routing_policies_registry(config: AutopilotConfig) -> list[RoutingPolicy]:
    if not config.routing_policies_json_path.exists():
        return list(DEFAULT_ROUTING_POLICIES)
    raw = json.loads(config.routing_policies_json_path.read_text())
    items = raw.get("routing_policies", []) if isinstance(raw, dict) else raw
    return _merge_registry(items, DEFAULT_ROUTING_POLICIES, RoutingPolicy)


def save_routing_policies_registry(config: AutopilotConfig, policies: list[RoutingPolicy]) -> None:
    _atomic_write_json(
        config.routing_policies_json_path,
        {"routing_policies": [policy.model_dump() for policy in policies]},
    )


def upsert_routing_policy(config: AutopilotConfig, policy: RoutingPolicy) -> RoutingPolicy:
    policies = {item.role_id: item for item in load_routing_policies_registry(config)}
    policies[policy.role_id] = policy
    save_routing_policies_registry(config, list(policies.values()))
    return policy


def load_launch_presets() -> list[LaunchPreset]:
    return list(DEFAULT_LAUNCH_PRESETS)


def load_role_templates() -> list[RoleTemplate]:
    return list(DEFAULT_ROLE_TEMPLATES)


def load_connector_type_catalog() -> list[ConnectorTypeSchema]:
    return list(DEFAULT_CONNECTOR_TYPES)


def get_connector_type_schema(connector_type: str) -> ConnectorTypeSchema | None:
    return next((schema for schema in DEFAULT_CONNECTOR_TYPES if schema.id == connector_type), None)


def normalize_launch_profile(profile: dict | LaunchProfile | None = None) -> LaunchProfile:
    if isinstance(profile, LaunchProfile):
        raw = profile.model_dump()
    else:
        raw = dict(profile or {})

    preset = str(raw.get("preset") or "fast").strip().lower() or "fast"
    preset_match = next((item for item in DEFAULT_LAUNCH_PRESETS if item.id == preset), DEFAULT_LAUNCH_PRESETS[0])
    resolved = preset_match.launch_profile.model_copy(deep=True)

    if "story_execution_mode" in raw and raw["story_execution_mode"]:
        resolved.story_execution_mode = str(raw["story_execution_mode"]).strip().lower()
    if "project_concurrency_mode" in raw and raw["project_concurrency_mode"]:
        resolved.project_concurrency_mode = str(raw["project_concurrency_mode"]).strip().lower()
    if "max_parallel_stories" in raw and raw["max_parallel_stories"] is not None:
        try:
            resolved.max_parallel_stories = max(1, int(raw["max_parallel_stories"]))
        except (TypeError, ValueError):
            resolved.max_parallel_stories = preset_match.launch_profile.max_parallel_stories

    resolved.preset = preset_match.id
    if resolved.project_concurrency_mode != "parallel":
        resolved.max_parallel_stories = 1
    return resolved


def validate_connector_config(connector: MCPConnector) -> ConnectorValidationResult:
    schema = get_connector_type_schema(connector.connector_type)
    if schema is None:
        return ConnectorValidationResult(
            ok=False,
            status="invalid",
            summary=f"Unknown connector type: {connector.connector_type}",
            log=f"Connector type `{connector.connector_type}` is not in the type catalog.",
        )

    issues: list[str] = []
    checked_fields = [field.key for field in schema.config_fields]
    config = connector.config or {}

    if connector.transport not in schema.transport_options:
        issues.append(
            f"Transport `{connector.transport}` is not allowed for `{connector.connector_type}`. "
            f"Allowed: {', '.join(schema.transport_options)}."
        )

    for field in schema.config_fields:
        raw_value = config.get(field.key, "")
        value = str(raw_value).strip() if raw_value is not None else ""
        if field.required and not value:
            issues.append(f"Missing required field `{field.key}`.")
            continue
        if not value:
            continue
        if field.field_type == "url" and not re.match(r"^(https?|bolt|neo4j|postgres(?:ql)?)://", value):
            issues.append(f"Field `{field.key}` must be a valid URL/DSN.")

    if connector.connector_type == "mcp_server":
        command = str(config.get("command", "")).strip()
        url = str(config.get("url", "")).strip()
        if connector.transport == "stdio" and not command:
            issues.append("`command` is required for stdio MCP connectors.")
        if connector.transport == "http" and not url:
            issues.append("`url` is required for HTTP MCP connectors.")

    if connector.connector_type == "http_api" and not str(config.get("base_url", "")).strip():
        issues.append("`base_url` is required for HTTP API connectors.")

    if connector.connector_type == "neo4j" and not str(config.get("uri", "")).strip():
        issues.append("`uri` is required for Neo4j connectors.")

    if connector.connector_type == "postgres" and not str(config.get("dsn", "")).strip():
        issues.append("`dsn` is required for Postgres connectors.")

    if issues:
        return ConnectorValidationResult(
            ok=False,
            status="invalid",
            summary=f"{len(issues)} validation issue(s) found.",
            log="\n".join(f"- {issue}" for issue in issues),
            checked_fields=checked_fields,
        )

    summary = "Built-in connector is available." if connector.built_in else "Connector config looks valid."
    return ConnectorValidationResult(
        ok=True,
        status="valid",
        summary=summary,
        log="Validation completed successfully.",
        checked_fields=checked_fields,
    )


TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "frontend": ("frontend", "ui", "dashboard", "page", "component", "react", "next.js", "nextjs"),
    "backend": ("backend", "api", "service", "server", "endpoint", "fastapi"),
    "database": ("database", "sql", "schema", "migration", "postgres"),
    "graph": ("graph", "neo4j", "rag", "relationship"),
    "infra": ("deploy", "infra", "docker", "ci", "pipeline", "worker", "queue"),
    "design": ("design", "layout", "visual", "tailwind", "shadcn", "component"),
    "debug": ("debug", "fix", "incident", "failure", "bug", "runtime"),
    "testing": ("test", "qa", "verification", "smoke", "e2e"),
    "integration": ("integration", "webhook", "third-party", "oauth", "provider"),
    "trading": ("trading", "market", "wallet", "solana", "token", "exchange"),
    "research": ("research", "analyze", "investigate", "compare", "study"),
}


def _keyword_matches(haystack: str, keyword: str) -> bool:
    escaped = re.escape(keyword.lower())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", haystack) is not None


def infer_story_tags(title: str, description: str) -> list[str]:
    haystack = f"{title} {description}".lower()
    tags = {
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(_keyword_matches(haystack, keyword) for keyword in keywords)
    }
    if not tags:
        tags.add("backend")
    if "frontend" in tags and "backend" in tags:
        tags.add("fullstack")
    return sorted(tags)


def infer_story_role(tags: list[str]) -> str:
    tag_set = set(tags)
    if "testing" in tag_set and "frontend" in tag_set:
        return "qa_reviewer"
    if "debug" in tag_set:
        return "runtime_investigator"
    if "frontend" in tag_set and "backend" in tag_set:
        return "fullstack_worker"
    if "frontend" in tag_set or "design" in tag_set:
        return "frontend_worker"
    return "backend_worker"


def _collect_skill_packs(
    role_id: str,
    tags: list[str],
    skill_packs: list[SkillPack],
    *,
    routing_policies: list[RoutingPolicy] | None = None,
) -> list[str]:
    role_templates = {template.id: template for template in load_role_templates()}
    policies = {policy.role_id: policy for policy in (routing_policies or DEFAULT_ROUTING_POLICIES)}
    role = role_templates.get(role_id)
    selected: list[str] = list(role.default_skill_packs if role else [])
    tag_set = set(tags)
    for skill_pack in skill_packs:
        if not skill_pack.enabled:
            continue
        if skill_pack.id in selected:
            continue
        if tag_set.intersection(skill_pack.tags):
            selected.append(skill_pack.id)
    for skill_pack_id in policies.get(role_id, RoutingPolicy(role_id=role_id)).preferred_skill_packs:
        if skill_pack_id not in selected:
            selected.append(skill_pack_id)
    return selected


def _collect_connectors(
    role_id: str,
    tags: list[str],
    skill_pack_ids: list[str],
    connectors: list[MCPConnector],
    skill_packs: list[SkillPack],
    *,
    routing_policies: list[RoutingPolicy] | None = None,
) -> list[str]:
    role_templates = {template.id: template for template in load_role_templates()}
    policies = {policy.role_id: policy for policy in (routing_policies or DEFAULT_ROUTING_POLICIES)}
    role = role_templates.get(role_id)
    selected: list[str] = list(role.default_connectors if role else [])
    tag_set = set(tags)
    for connector in connectors:
        if not connector.enabled or connector.id in selected:
            continue
        if tag_set.intersection(connector.tags):
            selected.append(connector.id)

    skills_by_id = {skill_pack.id: skill_pack for skill_pack in skill_packs}
    for skill_pack_id in skill_pack_ids:
        skill_pack = skills_by_id.get(skill_pack_id)
        if not skill_pack:
            continue
        for connector_id in skill_pack.preferred_connectors:
            if connector_id not in selected:
                selected.append(connector_id)

    policy = policies.get(role_id)
    if policy:
        for connector_id in policy.preferred_connectors:
            if connector_id not in selected:
                selected.append(connector_id)
        for connector_id in policy.required_connectors:
            if connector_id not in selected:
                selected.append(connector_id)
        selected = [connector_id for connector_id in selected if connector_id not in set(policy.forbidden_connectors)]

    return selected


def enrich_story_plan(
    story: dict,
    *,
    skill_packs: list[SkillPack] | None = None,
    connectors: list[MCPConnector] | None = None,
    routing_policies: list[RoutingPolicy] | None = None,
) -> dict:
    """Add routing metadata to a story definition."""
    available_skills = skill_packs or list(DEFAULT_SKILL_PACKS)
    available_connectors = connectors or list(DEFAULT_CONNECTORS)

    title = str(story.get("title") or "").strip()
    description = str(story.get("description") or "").strip()
    tags = [str(tag).strip() for tag in story.get("tags", []) if str(tag).strip()] or infer_story_tags(title, description)
    role = str(story.get("role") or "").strip() or infer_story_role(tags)
    explicit_skill_packs = [
        str(skill_pack_id).strip()
        for skill_pack_id in story.get("skill_packs", [])
        if str(skill_pack_id).strip()
    ]
    story_skill_packs = [
        str(skill_pack_id).strip()
        for skill_pack_id in explicit_skill_packs
    ] or _collect_skill_packs(role, tags, available_skills, routing_policies=routing_policies)
    explicit_connectors = [
        str(connector_id).strip()
        for connector_id in story.get("connectors", [])
        if str(connector_id).strip()
    ]
    story_connectors = [
        str(connector_id).strip()
        for connector_id in explicit_connectors
    ] or _collect_connectors(
        role,
        tags,
        story_skill_packs,
        available_connectors,
        available_skills,
        routing_policies=routing_policies,
    )
    required_connectors = [
        str(connector_id).strip()
        for connector_id in story.get("required_connectors", [])
        if str(connector_id).strip()
    ]
    preferred_connectors = [
        str(connector_id).strip()
        for connector_id in story.get("preferred_connectors", [])
        if str(connector_id).strip()
    ]
    forbidden_connectors = [
        str(connector_id).strip()
        for connector_id in story.get("forbidden_connectors", [])
        if str(connector_id).strip()
    ]

    acceptance = [
        str(item).strip()
        for item in story.get("acceptance_criteria", [])
        if str(item).strip()
    ]
    if not acceptance and description:
        acceptance = [description]

    return {
        **story,
        "tags": sorted(dict.fromkeys(tags)),
        "role": role,
        "skill_packs": story_skill_packs,
        "connectors": story_connectors,
        "required_connectors": required_connectors,
        "preferred_connectors": preferred_connectors,
        "forbidden_connectors": forbidden_connectors,
        "acceptance_criteria": acceptance,
    }


def _policy_for_role(role_id: str, routing_policies: list[RoutingPolicy] | None = None) -> RoutingPolicy:
    policies = {policy.role_id: policy for policy in (routing_policies or DEFAULT_ROUTING_POLICIES)}
    return policies.get(role_id, RoutingPolicy(role_id=role_id))


def _specialist_blueprint(tags: list[str]) -> dict[str, list[str] | str] | None:
    tag_set = set(tags)
    if tag_set.intersection({"frontend", "ui", "design"}):
        return {
            "role_id": "frontend_worker",
            "label": "UI Specialist",
            "skill_packs": ["nextjs-frontend"],
            "connectors": ["browser_devtools", "twenty_first_dev", "web_docs"],
        }
    if tag_set.intersection({"graph", "database", "data", "analytics"}):
        return {
            "role_id": "data_worker",
            "label": "Data Specialist",
            "skill_packs": ["graph-data"],
            "connectors": ["neo4j", "postgres", "python_exec"],
        }
    if tag_set.intersection({"backend", "api", "docs", "research"}):
        return {
            "role_id": "api_researcher",
            "label": "API Specialist",
            "skill_packs": ["debug-investigation"],
            "connectors": ["web_docs", "http_api", "github"],
        }
    return None


def activate_connector_set(
    connector_ids: list[str],
    *,
    provider: str,
    available_connectors: list[MCPConnector] | None = None,
    required_connectors: list[str] | None = None,
) -> tuple[list[ConnectorActivation], list[str]]:
    connectors_by_id = {
        connector.id: connector for connector in (available_connectors or list(DEFAULT_CONNECTORS))
    }
    required = set(required_connectors or [])
    activations: list[ConnectorActivation] = []
    blocking_errors: list[str] = []

    for connector_id in list(dict.fromkeys(connector_ids)):
        connector = connectors_by_id.get(connector_id)
        if connector is None:
            activation = ConnectorActivation(
                id=connector_id,
                name=connector_id,
                connector_type="unknown",
                provider=provider,
                required=connector_id in required,
                status="disabled",
                reason="Connector is not present in the registry.",
            )
        elif not connector.enabled:
            activation = ConnectorActivation(
                id=connector.id,
                name=connector.name,
                connector_type=connector.connector_type,
                provider=provider,
                required=connector.id in required,
                status="disabled",
                reason="Connector is disabled in Settings.",
                config=connector.config,
            )
        elif provider not in connector.providers:
            activation = ConnectorActivation(
                id=connector.id,
                name=connector.name,
                connector_type=connector.connector_type,
                provider=provider,
                required=connector.id in required,
                status="unsupported_for_provider",
                reason=f"Connector does not support provider `{provider}`.",
                config=connector.config,
            )
        elif connector.validation_status == "invalid":
            summary = connector.last_validation_result.get("summary") if connector.last_validation_result else ""
            activation = ConnectorActivation(
                id=connector.id,
                name=connector.name,
                connector_type=connector.connector_type,
                provider=provider,
                required=connector.id in required,
                status="validation_failed",
                reason=summary or "Connector validation failed.",
                config=connector.config,
            )
        else:
            activation = ConnectorActivation(
                id=connector.id,
                name=connector.name,
                connector_type=connector.connector_type,
                provider=provider,
                required=connector.id in required,
                status="active",
                reason="Connector activated for runtime planning.",
                config=connector.config,
            )

        if activation.required and activation.status != "active":
            blocking_errors.append(f"{activation.name}: {activation.reason}")
        activations.append(activation)

    return activations, blocking_errors


def resolve_story_runtime_plan(
    story: dict,
    *,
    launch_profile: dict | LaunchProfile | None = None,
    provider: str = "codex",
    connectors: list[MCPConnector] | None = None,
    skill_packs: list[SkillPack] | None = None,
    routing_policies: list[RoutingPolicy] | None = None,
) -> dict:
    available_connectors = connectors or list(DEFAULT_CONNECTORS)
    available_skill_packs = skill_packs or list(DEFAULT_SKILL_PACKS)
    policies = routing_policies or list(DEFAULT_ROUTING_POLICIES)
    normalized_story = enrich_story_plan(
        dict(story),
        skill_packs=available_skill_packs,
        connectors=available_connectors,
        routing_policies=policies,
    )
    profile = normalize_launch_profile(launch_profile)
    role_id = str(normalized_story.get("role") or "backend_worker")
    policy = _policy_for_role(role_id, policies)
    explicit_connector_override = bool(story.get("connectors"))

    selected_skill_packs = list(dict.fromkeys(
        list(normalized_story.get("skill_packs", [])) + list(policy.preferred_skill_packs)
    ))
    planned_connectors = list(normalized_story.get("connectors", []))
    for connector_id in list(policy.preferred_connectors) + list(normalized_story.get("preferred_connectors", [])):
        if connector_id not in planned_connectors:
            planned_connectors.append(connector_id)
    required_connectors = list(
        dict.fromkeys(
            list(policy.required_connectors)
            + list(normalized_story.get("required_connectors", []))
        )
    )
    if not explicit_connector_override:
        forbidden = set(policy.forbidden_connectors + list(normalized_story.get("forbidden_connectors", [])))
        planned_connectors = [
            connector_id for connector_id in planned_connectors if connector_id not in forbidden or connector_id in required_connectors
        ]
    for connector_id in required_connectors:
        if connector_id not in planned_connectors:
            planned_connectors.append(connector_id)

    primary_activations, activation_errors = activate_connector_set(
        planned_connectors,
        provider=provider,
        available_connectors=available_connectors,
        required_connectors=required_connectors,
    )
    team_members: list[TeamMemberAssignment] = [
        TeamMemberAssignment(
            member_id="primary",
            label="Primary Worker",
            execution_role="primary_worker",
            role_id=role_id,
            provider=provider,
            skill_packs=selected_skill_packs,
            planned_connectors=planned_connectors,
            active_connectors=primary_activations,
        ),
        TeamMemberAssignment(
            member_id="critic",
            label="Critic",
            execution_role="critic",
            role_id="qa_reviewer",
            provider=provider,
            skill_packs=_collect_skill_packs("qa_reviewer", normalized_story.get("tags", []), available_skill_packs, routing_policies=policies),
            planned_connectors=_collect_connectors(
                "qa_reviewer",
                normalized_story.get("tags", []),
                ["qa-review"],
                available_connectors,
                available_skill_packs,
                routing_policies=policies,
            ),
            active_connectors=activate_connector_set(
                _collect_connectors(
                    "qa_reviewer",
                    normalized_story.get("tags", []),
                    ["qa-review"],
                    available_connectors,
                    available_skill_packs,
                    routing_policies=policies,
                ),
                provider=provider,
                available_connectors=available_connectors,
            )[0],
        ),
    ]

    specialist = _specialist_blueprint(normalized_story.get("tags", []))
    if profile.story_execution_mode == "team" and specialist:
        specialist_connectors = list(dict.fromkeys(specialist["connectors"]))  # type: ignore[index]
        team_members.append(
            TeamMemberAssignment(
                member_id="specialist",
                label=str(specialist["label"]),
                execution_role="specialist",
                role_id=str(specialist["role_id"]),
                provider=provider,
                skill_packs=list(specialist["skill_packs"]),  # type: ignore[arg-type]
                planned_connectors=specialist_connectors,
                active_connectors=activate_connector_set(
                    specialist_connectors,
                    provider=provider,
                    available_connectors=available_connectors,
                )[0],
                specialist=True,
            )
        )

    return {
        "story": normalized_story,
        "launch_profile": profile.model_dump(),
        "team_mode": profile.story_execution_mode,
        "team_members": [member.model_dump() for member in team_members],
        "planned_connectors": planned_connectors,
        "active_connectors": [activation.model_dump() for activation in primary_activations],
        "activation_errors": activation_errors,
    }


def derive_phases_from_stories(stories: list[dict]) -> list[dict]:
    phases: list[dict] = []
    seen: set[str] = set()
    for index, story in enumerate(stories, start=1):
        phase_id = str(story.get("phase_id") or "").strip() or f"phase-{max(1, min(index, 9))}"
        phase_title = str(story.get("phase_title") or "").strip() or "Implementation"
        if phase_id in seen:
            continue
        seen.add(phase_id)
        phases.append(
            {
                "id": phase_id,
                "title": phase_title,
                "goal": str(story.get("phase_goal") or "").strip(),
            }
        )
    if not phases:
        phases.append({"id": "phase-1", "title": "Implementation", "goal": ""})
    return phases


def normalize_phase_plan(prd: dict, stories: list[dict]) -> list[dict]:
    raw_phases = prd.get("phases") or []
    if not raw_phases:
        return derive_phases_from_stories(stories)

    phases: list[dict] = []
    seen: set[str] = set()
    for index, phase in enumerate(raw_phases, start=1):
        phase_id = _slugify(str(phase.get("id") or phase.get("title") or f"phase-{index}"))
        if phase_id in seen:
            phase_id = f"{phase_id}-{index}"
        seen.add(phase_id)
        phases.append(
            {
                "id": phase_id,
                "title": str(phase.get("title") or f"Phase {index}").strip(),
                "goal": str(phase.get("goal") or "").strip(),
            }
        )
    if phases:
        return phases
    return derive_phases_from_stories(stories)


def build_planning_context(
    *,
    connectors: list[MCPConnector] | None = None,
    skill_packs: list[SkillPack] | None = None,
    role_templates: list[RoleTemplate] | None = None,
    routing_policies: list[RoutingPolicy] | None = None,
) -> str:
    """Render the available routing catalog for intake/planning prompts."""
    rendered_roles = "\n".join(
        f"- {role.id}: {role.description}. Default skills: {', '.join(role.default_skill_packs) or 'none'}."
        for role in (role_templates or load_role_templates())
    )
    rendered_skills = "\n".join(
        f"- {skill.id}: {skill.description}. Tags: {', '.join(skill.tags) or 'none'}."
        for skill in (skill_packs or list(DEFAULT_SKILL_PACKS))
        if skill.enabled
    )
    rendered_connectors = "\n".join(
        f"- {connector.id}: {connector.description}. Tags: {', '.join(connector.tags) or 'none'}."
        for connector in (connectors or list(DEFAULT_CONNECTORS))
        if connector.enabled
    )
    rendered_policies = "\n".join(
        f"- {policy.role_id}: required={', '.join(policy.required_connectors) or 'none'}; "
        f"preferred={', '.join(policy.preferred_connectors) or 'none'}; "
        f"forbidden={', '.join(policy.forbidden_connectors) or 'none'}."
        for policy in (routing_policies or list(DEFAULT_ROUTING_POLICIES))
    )
    return (
        "Available roles:\n"
        f"{rendered_roles}\n\n"
        "Available skill packs:\n"
        f"{rendered_skills}\n\n"
        "Available MCP connectors / tools:\n"
        f"{rendered_connectors}\n\n"
        "Role routing policies:\n"
        f"{rendered_policies}"
    )
