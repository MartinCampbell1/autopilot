"""Typed plugin manifest and discovery models."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field, model_validator

PluginConfigValue = str | int | float | bool | list[str]


class PluginAuthor(BaseModel):
    """Basic plugin author metadata."""

    name: str = ""
    email: str = ""
    url: str = ""


class PluginInterface(BaseModel):
    """User-facing plugin interface metadata."""

    displayName: str = ""
    shortDescription: str = ""
    longDescription: str = ""
    developerName: str = ""
    category: str = ""
    capabilities: list[str] = Field(default_factory=list)
    websiteURL: str = ""
    privacyPolicyURL: str = ""
    termsOfServiceURL: str = ""
    defaultPrompt: str | list[str] = Field(default_factory=list)
    composerIcon: str = ""
    logo: str = ""
    screenshots: list[str] = Field(default_factory=list)
    brandColor: str = ""

    def normalized_default_prompts(self) -> list[str]:
        if isinstance(self.defaultPrompt, str):
            prompt = self.defaultPrompt.strip()
            return [prompt] if prompt else []
        return [str(item).strip() for item in self.defaultPrompt if str(item).strip()]


class PluginUserConfigOption(BaseModel):
    """Declarative plugin option schema for user-provided configuration."""

    type: str = "string"
    title: str = ""
    description: str = ""
    required: bool = False
    sensitive: bool = False
    default: PluginConfigValue | None = None
    enum: list[str] = Field(default_factory=list)
    placeholder: str = ""
    pattern: str = ""
    items: str = "string"

    @model_validator(mode="after")
    def normalize_types(self) -> "PluginUserConfigOption":
        normalized = str(self.type or "string").strip().lower()
        if normalized in {"int", "integer", "float"}:
            normalized = "number"
        elif normalized in {"bool"}:
            normalized = "boolean"
        elif normalized in {"list"}:
            normalized = "array"
        if normalized not in {"string", "number", "boolean", "array"}:
            raise ValueError(f"Unsupported plugin option type: {self.type}")
        self.type = normalized
        if self.type != "array":
            self.items = "string"
        else:
            item_type = str(self.items or "string").strip().lower()
            self.items = item_type if item_type in {"string", "number", "boolean"} else "string"
        self.enum = [str(item).strip() for item in self.enum if str(item).strip()]
        return self


class PluginManifest(BaseModel):
    """Filesystem plugin manifest rooted at `.codex-plugin/plugin.json`."""

    name: str
    version: str
    description: str = ""
    author: PluginAuthor | None = None
    homepage: str = ""
    repository: str = ""
    license: str = ""
    keywords: list[str] = Field(default_factory=list)
    commands: str | list[str] = Field(default_factory=list)
    mcpServers: str | dict[str, object] | list[object] | None = Field(
        default=None,
        validation_alias=AliasChoices("mcpServers", "mcp_servers"),
    )
    skills: str = ""
    apps: str = ""
    userConfig: dict[str, PluginUserConfigOption] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("userConfig", "user_config"),
    )
    interface: PluginInterface = Field(default_factory=PluginInterface)


class PluginIdentifier(BaseModel):
    """Parsed plugin identifier such as `github` or `github@0.1.0`."""

    name: str
    version: str = ""


class LoadedPlugin(BaseModel):
    """Resolved on-disk plugin with manifest and lifecycle metadata."""

    plugin_id: str
    name: str
    version: str = ""
    display_name: str = ""
    description: str = ""
    enabled: bool = True
    source: str = "filesystem"
    root_path: str
    manifest_path: str
    data_dir: str
    homepage: str = ""
    repository: str = ""
    license: str = ""
    keywords: list[str] = Field(default_factory=list)
    author: PluginAuthor | None = None
    commands_path: str = ""
    commands_paths: list[str] = Field(default_factory=list)
    mcp_server_spec: str | dict[str, object] | list[object] | None = None
    mcp_paths: list[str] = Field(default_factory=list)
    skills_path: str = ""
    skills_present: bool = False
    apps_path: str = ""
    apps_present: bool = False
    user_config: dict[str, PluginUserConfigOption] = Field(default_factory=dict)
    interface: PluginInterface = Field(default_factory=PluginInterface)
    validation_status: str = "valid"
    validation_errors: list[str] = Field(default_factory=list)


class PluginSkillDescriptor(BaseModel):
    """Discovered plugin skill descriptor from one `SKILL.md` bundle."""

    plugin_id: str
    skill_id: str
    name: str
    description: str = ""
    path: str
    relative_path: str = ""
    license_path: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class PluginCommandDescriptor(BaseModel):
    """Discovered plugin command or prompt bundle from markdown content."""

    plugin_id: str
    command_id: str
    name: str
    display_name: str = ""
    description: str = ""
    path: str
    relative_path: str = ""
    source_kind: str = "command"
    user_invocable: bool = True
    argument_hint: str = ""
    arguments: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    when_to_use: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class PluginOptionValidationResult(BaseModel):
    """Validation outcome for one plugin option payload."""

    valid: bool = True
    values: dict[str, object] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)


class PluginOptionState(BaseModel):
    """Resolved option state for one loaded plugin."""

    plugin_id: str
    option_schema: dict[str, PluginUserConfigOption] = Field(default_factory=dict)
    configured_values: dict[str, object] = Field(default_factory=dict)
    configured_keys: list[str] = Field(default_factory=list)
    sensitive_keys: list[str] = Field(default_factory=list)
    unconfigured_keys: list[str] = Field(default_factory=list)
    validation_errors: dict[str, str] = Field(default_factory=dict)


class PluginMcpServerDescriptor(BaseModel):
    """Resolved plugin-declared MCP server with redacted preview config."""

    plugin_id: str
    server_name: str
    connector_id: str
    display_name: str
    transport: str
    source_kind: str = "inline"
    source_path: str = ""
    config: dict[str, object] = Field(default_factory=dict)
    validation_status: str = "valid"
    validation_errors: list[str] = Field(default_factory=list)
    missing_env_vars: list[str] = Field(default_factory=list)
    missing_option_keys: list[str] = Field(default_factory=list)
    sensitive_option_keys: list[str] = Field(default_factory=list)
    policy_action: str = "allow"
    policy_status: str = "ok"
    policy_summary: str = ""
    policy_flags: list[str] = Field(default_factory=list)
    wrapper_mode: str = ""
    recommended_runtime_profile: str = ""
    runtime_active: bool = True
