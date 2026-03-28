"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  createConnector,
  createSkillPack,
  deleteConnector,
  deleteSkillPack,
  fetchCapabilitiesCatalog,
  updateRoutingPolicy,
  updateConnector,
  updateSkillPack,
  validateConnectorDraft,
} from "@/lib/api";
import type {
  CapabilitiesCatalog,
  ConnectorFieldSchema,
  ConnectorValidationResult,
  ConnectorTypeSchema,
  MCPConnector,
  RoleTemplate,
  RoutingPolicy,
  SkillPack,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type ConnectorDraft = {
  id: string;
  name: string;
  connector_type: string;
  description: string;
  transport: string;
  tags: string;
  providers: string;
  risk_level: string;
  scopes: string;
  enabled: boolean;
  config: string;
};

type SkillPackDraft = {
  id: string;
  name: string;
  description: string;
  prompt: string;
  tags: string;
  default_roles: string;
  preferred_connectors: string;
  enabled: boolean;
};

type RoutingPolicyDraft = {
  role_id: string;
  preferred_skill_packs: string;
  required_connectors: string;
  preferred_connectors: string;
  forbidden_connectors: string;
};

const EMPTY_CONNECTOR: ConnectorDraft = {
  id: "",
  name: "",
  connector_type: "mcp_server",
  description: "",
  transport: "stdio",
  tags: "",
  providers: "codex, claude, gemini",
  risk_level: "medium",
  scopes: "",
  enabled: true,
  config: "{\n  \n}",
};

const EMPTY_SKILL_PACK: SkillPackDraft = {
  id: "",
  name: "",
  description: "",
  prompt: "",
  tags: "",
  default_roles: "",
  preferred_connectors: "",
  enabled: true,
};

const EMPTY_ROUTING_POLICY: RoutingPolicyDraft = {
  role_id: "",
  preferred_skill_packs: "",
  required_connectors: "",
  preferred_connectors: "",
  forbidden_connectors: "",
};

const CONNECTOR_TYPES = ["mcp_server", "http_api", "builtin", "custom"];
const TRANSPORTS = ["stdio", "http", "builtin"];
const RISK_LEVELS = ["low", "medium", "high"];
const CONNECTOR_PRESETS: Array<{
  label: string;
  connector_type: string;
  transport: string;
  description: string;
  tags: string[];
  scopes: string[];
  config: Record<string, string>;
}> = [
  {
    label: "HTTP API",
    connector_type: "http_api",
    transport: "http",
    description: "Call an external REST or JSON API from workers.",
    tags: ["api", "integration", "backend"],
    scopes: ["network"],
    config: { base_url: "https://api.example.com", headers: "{}", auth_strategy: "bearer" },
  },
  {
    label: "External MCP",
    connector_type: "mcp_server",
    transport: "stdio",
    description: "Attach an external MCP server over stdio or HTTP transport.",
    tags: ["mcp", "tools", "integration"],
    scopes: ["network"],
    config: { command: "npx your-mcp-server", args: "[]", url: "" },
  },
  {
    label: "Neo4j Graph",
    connector_type: "neo4j",
    transport: "stdio",
    description: "Expose a graph database for retrieval, relationships, or topology work.",
    tags: ["graph", "database", "research"],
    scopes: ["database"],
    config: { uri: "bolt://localhost:7687", database: "neo4j", username: "", password: "" },
  },
  {
    label: "Postgres",
    connector_type: "postgres",
    transport: "stdio",
    description: "Expose a relational database for queries, migrations, and verification.",
    tags: ["database", "backend", "data"],
    scopes: ["database"],
    config: { dsn: "postgresql://user:pass@localhost:5432/app" },
  },
];

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(values: string[]) {
  return values.filter(Boolean).join(", ");
}

function formatConnectorDraft(connector: MCPConnector): ConnectorDraft {
  return {
    id: connector.id,
    name: connector.name,
    connector_type: connector.connector_type,
    description: connector.description || "",
    transport: connector.transport || "builtin",
    tags: joinList(connector.tags || []),
    providers: joinList(connector.providers || []),
    risk_level: connector.risk_level || "medium",
    scopes: joinList(connector.scopes || []),
    enabled: connector.enabled,
    config: JSON.stringify(connector.config || {}, null, 2),
  };
}

function formatSkillPackDraft(skillPack: SkillPack): SkillPackDraft {
  return {
    id: skillPack.id,
    name: skillPack.name,
    description: skillPack.description || "",
    prompt: skillPack.prompt || "",
    tags: joinList(skillPack.tags || []),
    default_roles: joinList(skillPack.default_roles || []),
    preferred_connectors: joinList(skillPack.preferred_connectors || []),
    enabled: skillPack.enabled,
  };
}

function formatRoutingPolicyDraft(policy: RoutingPolicy): RoutingPolicyDraft {
  return {
    role_id: policy.role_id,
    preferred_skill_packs: joinList(policy.preferred_skill_packs || []),
    required_connectors: joinList(policy.required_connectors || []),
    preferred_connectors: joinList(policy.preferred_connectors || []),
    forbidden_connectors: joinList(policy.forbidden_connectors || []),
  };
}

function connectorSummary(connector: MCPConnector) {
  return {
    status: connector.enabled ? "Enabled" : "Disabled",
    statusClass: connector.enabled ? "bg-[#dbeddb] text-[#2b6e3f]" : "bg-[#f1f1ef] text-[#787774]",
  };
}

function skillPackSummary(skillPack: SkillPack) {
  return {
    status: skillPack.enabled ? "Enabled" : "Disabled",
    statusClass: skillPack.enabled ? "bg-[#dbeddb] text-[#2b6e3f]" : "bg-[#f1f1ef] text-[#787774]",
  };
}

function roleSummary(role: RoleTemplate) {
  return `${role.default_skill_packs.join(", ") || "none"} · ${role.default_connectors.join(", ") || "none"}`;
}

function applyConnectorPreset(preset: (typeof CONNECTOR_PRESETS)[number]): ConnectorDraft {
  return {
    ...EMPTY_CONNECTOR,
    connector_type: preset.connector_type,
    transport: preset.transport,
    description: preset.description,
    tags: joinList(preset.tags),
    scopes: joinList(preset.scopes),
    config: JSON.stringify(preset.config, null, 2),
  };
}

function parseDraftConfig(configText: string): Record<string, unknown> {
  if (!configText.trim()) return {};
  return JSON.parse(configText) as Record<string, unknown>;
}

function statusTone(status: string) {
  switch (status) {
    case "valid":
      return "bg-[#dbeddb] text-[#2b6e3f]";
    case "invalid":
      return "bg-[#fbe4e4] text-[#a02323]";
    default:
      return "bg-[#f1f1ef] text-[#787774]";
  }
}

function getConnectorConfigValue(configText: string, field: ConnectorFieldSchema): string {
  try {
    const config = parseDraftConfig(configText);
    const value = config[field.key];
    if (value == null) return "";
    if (typeof value === "string") return value;
    return JSON.stringify(value, null, 2);
  } catch {
    return "";
  }
}

function normalizeConnectorConfigValue(field: ConnectorFieldSchema, value: unknown): unknown {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (field.field_type === "textarea") {
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        return JSON.parse(trimmed);
      } catch {
        return value;
      }
    }
  }
  return value;
}

function renderConnectorFieldInput(
  field: ConnectorFieldSchema,
  value: string,
  onChange: (nextValue: string) => void
) {
  if (field.field_type === "textarea") {
    return (
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-24 font-mono text-[12px]"
        placeholder={field.placeholder}
      />
    );
  }

  if (field.field_type === "select") {
    return (
      <select
        value={value || field.options[0] || ""}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-lg border border-[#e3e2e0] bg-white px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f]"
      >
        <option value="">Select…</option>
        {field.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  return (
    <Input
      type={
        field.field_type === "password"
          ? "password"
          : field.field_type === "url"
            ? "url"
            : "text"
      }
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={field.placeholder}
    />
  );
}

export function SettingsCapabilitiesManager() {
  const [catalog, setCatalog] = useState<CapabilitiesCatalog>({
    connectors: [],
    skill_packs: [],
    roles: [],
    connector_types: [],
    routing_policies: [],
    launch_presets: [],
  });
  const [activeTab, setActiveTab] = useState<"connectors" | "skill-packs" | "routing">("connectors");
  const [selectedConnectorId, setSelectedConnectorId] = useState<string>("");
  const [selectedSkillPackId, setSelectedSkillPackId] = useState<string>("");
  const [selectedRoleId, setSelectedRoleId] = useState<string>("");
  const [connectorDraft, setConnectorDraft] = useState<ConnectorDraft>(EMPTY_CONNECTOR);
  const [skillPackDraft, setSkillPackDraft] = useState<SkillPackDraft>(EMPTY_SKILL_PACK);
  const [routingPolicyDraft, setRoutingPolicyDraft] = useState<RoutingPolicyDraft>(EMPTY_ROUTING_POLICY);
  const [connectorFilter, setConnectorFilter] = useState("");
  const [skillPackFilter, setSkillPackFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [draftValidation, setDraftValidation] = useState<ConnectorValidationResult | null>(null);

  const loadCatalog = async () => {
    setLoading(true);
    try {
      const nextCatalog = await fetchCapabilitiesCatalog();
      setCatalog(nextCatalog);

      setSelectedConnectorId((current) => {
        if (current && nextCatalog.connectors.some((item) => item.id === current)) return current;
        return nextCatalog.connectors[0]?.id || "";
      });
      setSelectedSkillPackId((current) => {
        if (current && nextCatalog.skill_packs.some((item) => item.id === current)) return current;
        return nextCatalog.skill_packs[0]?.id || "";
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load capabilities.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCatalog();
  }, []);

  useEffect(() => {
    const selected = catalog.connectors.find((item) => item.id === selectedConnectorId);
    if (selected) {
      setConnectorDraft(formatConnectorDraft(selected));
      setDraftValidation(selected.last_validation_result ?? null);
    } else if (!selectedConnectorId) {
      setConnectorDraft(EMPTY_CONNECTOR);
      setDraftValidation(null);
    }
  }, [catalog.connectors, selectedConnectorId]);

  useEffect(() => {
    const selected = catalog.skill_packs.find((item) => item.id === selectedSkillPackId);
    if (selected) {
      setSkillPackDraft(formatSkillPackDraft(selected));
    } else if (!selectedSkillPackId) {
      setSkillPackDraft(EMPTY_SKILL_PACK);
    }
  }, [catalog.skill_packs, selectedSkillPackId]);

  useEffect(() => {
    setSelectedRoleId((current) => {
      if (current && catalog.roles.some((role) => role.id === current)) return current;
      return catalog.roles[0]?.id || "";
    });
  }, [catalog.roles]);

  useEffect(() => {
    if (!selectedRoleId) {
      setRoutingPolicyDraft(EMPTY_ROUTING_POLICY);
      return;
    }
    const selectedPolicy = catalog.routing_policies.find((policy) => policy.role_id === selectedRoleId);
    if (selectedPolicy) {
      setRoutingPolicyDraft(formatRoutingPolicyDraft(selectedPolicy));
      return;
    }
    setRoutingPolicyDraft({
      ...EMPTY_ROUTING_POLICY,
      role_id: selectedRoleId,
    });
  }, [catalog.routing_policies, selectedRoleId]);

  const selectConnector = (connector: MCPConnector) => {
    setActiveTab("connectors");
    setSelectedConnectorId(connector.id);
    setConnectorDraft(formatConnectorDraft(connector));
    setDraftValidation(connector.last_validation_result ?? null);
    setMessage("");
  };

  const selectSkillPack = (skillPack: SkillPack) => {
    setActiveTab("skill-packs");
    setSelectedSkillPackId(skillPack.id);
    setSkillPackDraft(formatSkillPackDraft(skillPack));
    setMessage("");
  };

  const selectRole = (role: RoleTemplate) => {
    setActiveTab("routing");
    setSelectedRoleId(role.id);
    const existingPolicy = catalog.routing_policies.find((policy) => policy.role_id === role.id);
    setRoutingPolicyDraft(
      existingPolicy
        ? formatRoutingPolicyDraft(existingPolicy)
        : {
            ...EMPTY_ROUTING_POLICY,
            role_id: role.id,
          }
    );
    setMessage("");
  };

  const startNewConnector = () => {
    setActiveTab("connectors");
    setSelectedConnectorId("");
    setConnectorDraft(EMPTY_CONNECTOR);
    setDraftValidation(null);
    setMessage("");
  };

  const startNewSkillPack = () => {
    setActiveTab("skill-packs");
    setSelectedSkillPackId("");
    setSkillPackDraft(EMPTY_SKILL_PACK);
    setMessage("");
  };

  const selectedConnectorType =
    catalog.connector_types.find((item) => item.id === connectorDraft.connector_type) ?? null;

  const buildConnectorPayload = () => {
    const id = connectorDraft.id.trim();
    if (!id) {
      throw new Error("Connector id is required.");
    }

    const config = parseDraftConfig(connectorDraft.config);
    const normalizedConfig = selectedConnectorType
      ? Object.fromEntries(
          Object.entries(config).map(([key, value]) => {
            const field = selectedConnectorType.config_fields.find((item) => item.key === key);
            return [key, field ? normalizeConnectorConfigValue(field, value) : value];
          })
        )
      : config;
    return {
      id,
      name: connectorDraft.name.trim() || id,
      connector_type: connectorDraft.connector_type.trim() || "mcp_server",
      description: connectorDraft.description.trim(),
      transport: connectorDraft.transport.trim() || selectedConnectorType?.default_transport || "stdio",
      tags: splitList(connectorDraft.tags),
      providers: splitList(connectorDraft.providers),
      risk_level: connectorDraft.risk_level.trim() || "medium",
      scopes: splitList(connectorDraft.scopes),
      enabled: connectorDraft.enabled,
      config: normalizedConfig,
    };
  };

  const updateConnectorConfigField = (field: string, value: string) => {
    setConnectorDraft((current) => {
      let config: Record<string, unknown> = {};
      try {
        config = parseDraftConfig(current.config);
      } catch {
        config = {};
      }
      config[field] = value;
      return {
        ...current,
        config: JSON.stringify(config, null, 2),
      };
    });
    setDraftValidation(null);
  };

  const saveConnector = async () => {
    try {
      const payload = buildConnectorPayload();
      const id = payload.id;

      setSaving(true);

      if (selectedConnectorId && selectedConnectorId === id) {
        await updateConnector(selectedConnectorId, payload);
      } else if (selectedConnectorId && selectedConnectorId !== id) {
        await updateConnector(selectedConnectorId, {
          ...payload,
          id: selectedConnectorId,
        });
      } else {
        await createConnector(payload);
      }

      setMessage(`Connector ${id} saved.`);
      setDraftValidation(null);
      await loadCatalog();
      setSelectedConnectorId(id);
    } catch (error) {
      setMessage(
        error instanceof Error && error.message.includes("Unexpected token")
          ? "Connector config must be valid JSON."
          : error instanceof Error
            ? error.message
            : "Failed to save connector."
      );
    } finally {
      setSaving(false);
    }
  };

  const validateCurrentConnector = async () => {
    try {
      const payload = buildConnectorPayload();
      setSaving(true);
      const result = await validateConnectorDraft(payload);
      setDraftValidation(result.result);
      setMessage(result.result.summary);
    } catch (error) {
      setMessage(
        error instanceof Error && error.message.includes("Unexpected token")
          ? "Connector config must be valid JSON."
          : error instanceof Error
            ? error.message
            : "Failed to validate connector."
      );
    } finally {
      setSaving(false);
    }
  };

  const saveSkillPack = async () => {
    const id = skillPackDraft.id.trim();
    if (!id) {
      setMessage("Skill pack id is required.");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        id,
        name: skillPackDraft.name.trim() || id,
        description: skillPackDraft.description.trim(),
        prompt: skillPackDraft.prompt.trim(),
        tags: splitList(skillPackDraft.tags),
        default_roles: splitList(skillPackDraft.default_roles),
        preferred_connectors: splitList(skillPackDraft.preferred_connectors),
        enabled: skillPackDraft.enabled,
      };

      if (selectedSkillPackId && selectedSkillPackId === id) {
        await updateSkillPack(selectedSkillPackId, payload);
      } else if (selectedSkillPackId && selectedSkillPackId !== id) {
        await updateSkillPack(selectedSkillPackId, {
          ...payload,
          id: selectedSkillPackId,
        });
      } else {
        await createSkillPack(payload);
      }

      setMessage(`Skill pack ${id} saved.`);
      await loadCatalog();
      setSelectedSkillPackId(id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save skill pack.");
    } finally {
      setSaving(false);
    }
  };

  const saveRoutingPolicy = async () => {
    if (!routingPolicyDraft.role_id.trim()) {
      setMessage("Select a role before saving routing policy.");
      return;
    }

    try {
      setSaving(true);
      await updateRoutingPolicy(routingPolicyDraft.role_id, {
        role_id: routingPolicyDraft.role_id,
        preferred_skill_packs: splitList(routingPolicyDraft.preferred_skill_packs),
        required_connectors: splitList(routingPolicyDraft.required_connectors),
        preferred_connectors: splitList(routingPolicyDraft.preferred_connectors),
        forbidden_connectors: splitList(routingPolicyDraft.forbidden_connectors),
      });
      setMessage(`Routing policy for ${routingPolicyDraft.role_id} saved.`);
      await loadCatalog();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save routing policy.");
    } finally {
      setSaving(false);
    }
  };

  const removeSelectedConnector = async () => {
    if (!selectedConnectorId) return;
    setSaving(true);
    try {
      const result = await deleteConnector(selectedConnectorId);
      setMessage(result.message);
      setSelectedConnectorId("");
      setConnectorDraft(EMPTY_CONNECTOR);
      setDraftValidation(null);
      await loadCatalog();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to delete connector.");
    } finally {
      setSaving(false);
    }
  };

  const removeSelectedSkillPack = async () => {
    if (!selectedSkillPackId) return;
    setSaving(true);
    try {
      const result = await deleteSkillPack(selectedSkillPackId);
      setMessage(result.message);
      setSelectedSkillPackId("");
      setSkillPackDraft(EMPTY_SKILL_PACK);
      await loadCatalog();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to delete skill pack.");
    } finally {
      setSaving(false);
    }
  };

  const connectorCount = catalog.connectors.length;
  const enabledConnectorCount = catalog.connectors.filter((item) => item.enabled).length;
  const skillPackCount = catalog.skill_packs.length;
  const enabledSkillPackCount = catalog.skill_packs.filter((item) => item.enabled).length;
  const filteredConnectors = catalog.connectors.filter((connector) => {
    const haystack = `${connector.id} ${connector.name} ${connector.description} ${connector.tags.join(" ")}`.toLowerCase();
    return haystack.includes(connectorFilter.trim().toLowerCase());
  });
  const filteredSkillPacks = catalog.skill_packs.filter((skillPack) => {
    const haystack = `${skillPack.id} ${skillPack.name} ${skillPack.description} ${skillPack.tags.join(" ")}`.toLowerCase();
    return haystack.includes(skillPackFilter.trim().toLowerCase());
  });
  const filteredRoles = catalog.roles.filter((role) => {
    const haystack = `${role.id} ${role.name} ${role.description} ${role.default_skill_packs.join(" ")} ${role.default_connectors.join(" ")}`.toLowerCase();
    return haystack.includes(roleFilter.trim().toLowerCase());
  });
  const selectedConnector = catalog.connectors.find((item) => item.id === selectedConnectorId) ?? null;
  const selectedSkillPack = catalog.skill_packs.find((item) => item.id === selectedSkillPackId) ?? null;
  const selectedRole = catalog.roles.find((item) => item.id === selectedRoleId) ?? null;
  const connectorTypeOptions = catalog.connector_types.length
    ? catalog.connector_types
    : CONNECTOR_TYPES.map(
        (id) =>
          ({
            id,
            name: id,
            description: "",
            transport_options: TRANSPORTS,
            default_transport: "stdio",
            suggested_tags: [],
            suggested_scopes: [],
            config_fields: [],
          }) satisfies ConnectorTypeSchema
      );
  const transportOptions = selectedConnectorType?.transport_options?.length
    ? selectedConnectorType.transport_options
    : TRANSPORTS;
  const activeValidation = draftValidation ?? selectedConnector?.last_validation_result ?? null;
  const activeValidationStatus = draftValidation?.status || selectedConnector?.validation_status || "unknown";
  const activeValidationCheckedFields = Array.isArray(activeValidation?.checked_fields)
    ? activeValidation.checked_fields
    : [];
  const activeValidationSummary =
    typeof activeValidation?.summary === "string" && activeValidation.summary.trim()
      ? activeValidation.summary
      : "No validation summary recorded yet.";
  const activeValidationLog =
    typeof activeValidation?.log === "string" && activeValidation.log.trim()
      ? activeValidation.log
      : "";

  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-[12px] border border-[#e5e5e3] bg-white px-4 py-3 shadow-[0_1px_3px_rgba(15,15,15,0.08)]">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Connectors</p>
          <p className="mt-1 text-[20px] font-semibold text-[#37352f]">{connectorCount}</p>
          <p className="mt-1 text-[12px] text-[#787774]">{enabledConnectorCount} enabled</p>
        </div>
        <div className="rounded-[12px] border border-[#e5e5e3] bg-white px-4 py-3 shadow-[0_1px_3px_rgba(15,15,15,0.08)]">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Skill packs</p>
          <p className="mt-1 text-[20px] font-semibold text-[#37352f]">{skillPackCount}</p>
          <p className="mt-1 text-[12px] text-[#787774]">{enabledSkillPackCount} enabled</p>
        </div>
        <div className="rounded-[12px] border border-[#e5e5e3] bg-white px-4 py-3 shadow-[0_1px_3px_rgba(15,15,15,0.08)]">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Roles</p>
          <p className="mt-1 text-[20px] font-semibold text-[#37352f]">{catalog.roles.length}</p>
          <p className="mt-1 text-[12px] text-[#787774]">Planner and worker routing templates</p>
        </div>
        <div className="rounded-[12px] border border-[#e5e5e3] bg-white px-4 py-3 shadow-[0_1px_3px_rgba(15,15,15,0.08)]">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Catalog</p>
          <p className="mt-1 text-[20px] font-semibold text-[#37352f]">{loading ? "Syncing" : "Ready"}</p>
          <p className="mt-1 text-[12px] text-[#787774]">Local connector registry and skill packs</p>
        </div>
      </div>

      <div className="rounded-[14px] border border-[#e5e5e3] bg-white px-5 py-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <p className="text-[14px] leading-relaxed text-[#37352f]">
          Configure the exact MCP servers, API adapters, and skill packs available to Autopilot workers.
          Connectors are persisted locally; the planner uses this catalog to tag stories and assign roles.
        </p>
        <p className="mt-2 min-h-[20px] text-[13px] text-[#787774]">{message}</p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab((value as "connectors" | "skill-packs" | "routing") || "connectors")}
        className="gap-4"
        orientation="horizontal"
      >
        <TabsList className="w-full justify-start bg-[#f1f1ef]">
          <TabsTrigger value="connectors">Connectors</TabsTrigger>
          <TabsTrigger value="skill-packs">Skill Packs</TabsTrigger>
          <TabsTrigger value="routing">Routing</TabsTrigger>
        </TabsList>

        <TabsContent value="connectors" className="mt-0">
          <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
            <section className="rounded-[14px] border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <div className="flex items-center justify-between border-b border-[#ecebe8] px-4 py-3">
                <div>
                  <h3 className="text-[14px] font-semibold text-[#37352f]">MCP / API connectors</h3>
                  <p className="text-[12px] text-[#9b9a97]">Choose a connector to edit or create a new one.</p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-[8px] border-[#e5e5e3] text-[12px]"
                  onClick={startNewConnector}
                >
                  New
                </Button>
              </div>
              <div className="border-b border-[#ecebe8] px-4 py-3">
                <Input
                  value={connectorFilter}
                  onChange={(event) => setConnectorFilter(event.target.value)}
                  placeholder="Search connectors"
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {CONNECTOR_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => {
                        startNewConnector();
                        setConnectorDraft(applyConnectorPreset(preset));
                      }}
                      className="rounded-full border border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#6b6b6b] transition-colors hover:border-[#d0cfcc] hover:bg-[#f7f7f5]"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
              <ScrollArea className="h-[620px]">
                <div className="space-y-2 px-3 py-3">
                  {filteredConnectors.length === 0 ? (
                    <div className="rounded-[10px] border border-dashed border-[#e5e5e3] px-4 py-6 text-[13px] text-[#9b9a97]">
                      {catalog.connectors.length === 0 ? "No connectors configured yet." : "No connectors match your search."}
                    </div>
                  ) : (
                    filteredConnectors.map((connector) => {
                      const selected = connector.id === selectedConnectorId;
                      const summary = connectorSummary(connector);
                      return (
                        <button
                          key={connector.id}
                          type="button"
                          onClick={() => selectConnector(connector)}
                          className={cn(
                            "w-full rounded-[12px] border px-4 py-3 text-left transition-colors",
                            selected
                              ? "border-[#d7d6d2] bg-[#fbfbf9] shadow-[0_1px_3px_rgba(15,15,15,0.06)]"
                              : "border-transparent hover:bg-[#f7f7f5]"
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-[13px] font-semibold text-[#37352f]">{connector.name}</p>
                              <p className="mt-1 text-[12px] text-[#787774]">{connector.id}</p>
                            </div>
                            <Badge className={cn("border-0 text-[11px]", summary.statusClass)} variant="outline">
                              {summary.status}
                            </Badge>
                          </div>
                          <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed text-[#6b6b6b]">
                            {connector.description || "No description provided."}
                          </p>
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {connector.tags.slice(0, 3).map((tag) => (
                              <Badge key={tag} variant="outline" className="border-[#ecebe8] bg-white text-[11px] text-[#787774]">
                                {tag}
                              </Badge>
                            ))}
                            <Badge variant="outline" className="border-[#ecebe8] bg-white text-[11px] text-[#9b9a97]">
                              {connector.transport}
                            </Badge>
                            <Badge variant="outline" className="border-[#ecebe8] bg-white text-[11px] text-[#9b9a97]">
                              {connector.validation_status || "unknown"}
                            </Badge>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </section>

            <section className="rounded-[14px] border border-[#e5e5e3] bg-white p-5 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <div className="flex items-center justify-between gap-3 border-b border-[#ecebe8] pb-4">
                <div>
                  <h3 className="text-[16px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    {selectedConnectorId ? "Edit connector" : "Create connector"}
                  </h3>
                  <p className="mt-1 text-[13px] text-[#787774]">
                    Store the connector definition the orchestrator will expose to workers.
                  </p>
                </div>
                <Badge variant="outline" className="border-[#ecebe8] bg-[#f7f7f5] text-[#787774]">
                  {connectorDraft.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>

              <div className="mt-4 rounded-[12px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[13px] font-medium text-[#37352f]">
                      {selectedConnectorType?.name || connectorDraft.connector_type}
                    </p>
                    <p className="mt-1 text-[12px] leading-relaxed text-[#787774]">
                      {selectedConnectorType?.description || "Connector type schema is not loaded yet."}
                    </p>
                  </div>
                  <Badge className={cn("border-0 text-[11px]", statusTone(activeValidationStatus))} variant="outline">
                    {activeValidationStatus}
                  </Badge>
                </div>
                {selectedConnectorType && (
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Suggested tags</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedConnectorType.suggested_tags.length === 0 ? (
                          <span className="text-[12px] text-[#9b9a97]">No type-level tag suggestions.</span>
                        ) : (
                          selectedConnectorType.suggested_tags.map((tag) => (
                            <button
                              key={tag}
                              type="button"
                              onClick={() => {
                                const nextTags = Array.from(new Set([...splitList(connectorDraft.tags), tag]));
                                setConnectorDraft((current) => ({ ...current, tags: joinList(nextTags) }));
                                setDraftValidation(null);
                              }}
                              className="rounded-full border border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] text-[#6b6b6b] transition-colors hover:bg-[#f7f7f5]"
                            >
                              + {tag}
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Suggested scopes</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedConnectorType.suggested_scopes.length === 0 ? (
                          <span className="text-[12px] text-[#9b9a97]">No type-level scope suggestions.</span>
                        ) : (
                          selectedConnectorType.suggested_scopes.map((scope) => (
                            <button
                              key={scope}
                              type="button"
                              onClick={() => {
                                const nextScopes = Array.from(new Set([...splitList(connectorDraft.scopes), scope]));
                                setConnectorDraft((current) => ({ ...current, scopes: joinList(nextScopes) }));
                                setDraftValidation(null);
                              }}
                              className="rounded-full border border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] text-[#6b6b6b] transition-colors hover:bg-[#f7f7f5]"
                            >
                              + {scope}
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Id
                  </span>
                  <Input
                    value={connectorDraft.id}
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, id: event.target.value }))}
                    placeholder="solana_rpc"
                    disabled={Boolean(selectedConnectorId)}
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Name
                  </span>
                  <Input
                    value={connectorDraft.name}
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Solana RPC"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Connector Type
                  </span>
                  <select
                    value={connectorDraft.connector_type}
                    onChange={(event) => {
                      const nextType = connectorTypeOptions.find((item) => item.id === event.target.value) ?? null;
                      setConnectorDraft((current) => ({
                        ...current,
                        connector_type: event.target.value,
                        transport:
                          nextType && !nextType.transport_options.includes(current.transport)
                            ? nextType.default_transport
                            : current.transport,
                        tags: current.tags || joinList(nextType?.suggested_tags || []),
                        scopes: current.scopes || joinList(nextType?.suggested_scopes || []),
                      }));
                      setDraftValidation(null);
                    }}
                    className="h-10 w-full rounded-lg border border-[#e3e2e0] bg-white px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f]"
                  >
                    {connectorTypeOptions.map((type) => (
                      <option key={type.id} value={type.id}>
                        {type.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Transport
                  </span>
                  <select
                    value={connectorDraft.transport}
                    onChange={(event) => {
                      setConnectorDraft((current) => ({ ...current, transport: event.target.value }));
                      setDraftValidation(null);
                    }}
                    className="h-10 w-full rounded-lg border border-[#e3e2e0] bg-white px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f]"
                  >
                    {transportOptions.map((transport) => (
                      <option key={transport} value={transport}>
                        {transport}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Providers
                  </span>
                  <Input
                    value={connectorDraft.providers}
                    onChange={(event) => {
                      setConnectorDraft((current) => ({ ...current, providers: event.target.value }));
                      setDraftValidation(null);
                    }}
                    placeholder="codex, claude, gemini"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Risk Level
                  </span>
                  <select
                    value={connectorDraft.risk_level}
                    onChange={(event) => {
                      setConnectorDraft((current) => ({ ...current, risk_level: event.target.value }));
                      setDraftValidation(null);
                    }}
                    className="h-10 w-full rounded-lg border border-[#e3e2e0] bg-white px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f]"
                  >
                    {RISK_LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Tags
                  </span>
                  <Input
                    value={connectorDraft.tags}
                    onChange={(event) => {
                      setConnectorDraft((current) => ({ ...current, tags: event.target.value }));
                      setDraftValidation(null);
                    }}
                    placeholder="backend, graph, docs"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Scopes
                  </span>
                  <Input
                    value={connectorDraft.scopes}
                    onChange={(event) => {
                      setConnectorDraft((current) => ({ ...current, scopes: event.target.value }));
                      setDraftValidation(null);
                    }}
                    placeholder="network, database, browser"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Description
                  </span>
                  <Textarea
                    value={connectorDraft.description}
                    onChange={(event) => {
                      setConnectorDraft((current) => ({ ...current, description: event.target.value }));
                      setDraftValidation(null);
                    }}
                    placeholder="What this connector exposes to agents."
                    className="min-h-24"
                  />
                </label>
                {selectedConnectorType?.config_fields?.map((field) => (
                  <label
                    key={field.key}
                    className={cn(
                      "block",
                      field.field_type === "textarea" ? "md:col-span-2" : ""
                    )}
                  >
                    <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                      {field.label}
                      {field.required ? " *" : ""}
                    </span>
                    {renderConnectorFieldInput(
                      field,
                      getConnectorConfigValue(connectorDraft.config, field),
                      (value) => updateConnectorConfigField(field.key, value)
                    )}
                    {field.help_text ? (
                      <span className="mt-1 block text-[12px] leading-relaxed text-[#9b9a97]">{field.help_text}</span>
                    ) : null}
                  </label>
                ))}
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Advanced Config JSON
                  </span>
                  <Textarea
                    value={connectorDraft.config}
                    onChange={(event) => {
                      setConnectorDraft((current) => ({ ...current, config: event.target.value }));
                      setDraftValidation(null);
                    }}
                    className="min-h-40 font-mono text-[12px]"
                    placeholder='{\n  "base_url": "https://..."\n}'
                  />
                </label>
              </div>

              <label className="mt-4 flex items-center gap-2 text-[13px] text-[#37352f]">
                <input
                  type="checkbox"
                  checked={connectorDraft.enabled}
                  onChange={(event) => {
                    setConnectorDraft((current) => ({ ...current, enabled: event.target.checked }));
                    setDraftValidation(null);
                  }}
                  className="h-4 w-4 rounded border-[#d0cfcc]"
                />
                Enabled for planning and assignment
              </label>

              {activeValidation && (
                <div className="mt-4 rounded-[12px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[13px] font-medium text-[#37352f]">Validation result</p>
                    <Badge className={cn("border-0 text-[11px]", statusTone(activeValidation.status))} variant="outline">
                      {activeValidation.status}
                    </Badge>
                  </div>
                  <p className="mt-2 text-[13px] text-[#6b6b6b]">{activeValidationSummary}</p>
                  {activeValidationCheckedFields.length > 0 && (
                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                      Checked: {activeValidationCheckedFields.join(", ")}
                    </p>
                  )}
                  {activeValidationLog ? (
                    <pre className="mt-3 overflow-x-auto rounded-[10px] bg-white p-3 text-[12px] leading-relaxed text-[#6b6b6b]">
                      {activeValidationLog}
                    </pre>
                  ) : null}
                </div>
              )}

              <div className="mt-5 flex items-center justify-end gap-2">
                {selectedConnector && !selectedConnector.built_in && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-9 rounded-[8px] border-[#f0d7d1] text-[13px] text-[#93370d] hover:bg-[#fff7f5]"
                    onClick={() => void removeSelectedConnector()}
                    disabled={saving}
                  >
                    Delete connector
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="h-9 rounded-[8px] border-[#e5e5e3] text-[13px]"
                  onClick={() => void validateCurrentConnector()}
                  disabled={saving}
                >
                  {saving ? "Working..." : "Validate"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-9 rounded-[8px] border-[#e5e5e3] text-[13px]"
                  onClick={startNewConnector}
                  disabled={saving}
                >
                  New connector
                </Button>
                <Button
                  size="sm"
                  className="h-9 rounded-[8px] bg-[#37352f] text-[13px] hover:bg-[#4a4a45]"
                  onClick={() => void saveConnector()}
                  disabled={saving}
                >
                  {saving ? "Saving..." : selectedConnectorId ? "Update connector" : "Create connector"}
                </Button>
              </div>

              <div className="mt-5 rounded-[12px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Notes</p>
                <ul className="mt-2 space-y-1.5 text-[13px] leading-relaxed text-[#6b6b6b]">
                  <li>Use preset chips to start from a typed connector template instead of raw JSON.</li>
                  <li>`transport=http` is useful for hosted APIs or remote MCP bridges.</li>
                  <li>`transport=stdio` is useful when the connector should spawn a local MCP/tool process.</li>
                  <li>Only enabled connectors are considered by the planner when it tags and routes stories.</li>
                </ul>
              </div>
            </section>
          </div>
        </TabsContent>

        <TabsContent value="skill-packs" className="mt-0">
          <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
            <section className="rounded-[14px] border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <div className="flex items-center justify-between border-b border-[#ecebe8] px-4 py-3">
                <div>
                  <h3 className="text-[14px] font-semibold text-[#37352f]">Skill packs</h3>
                  <p className="text-[12px] text-[#9b9a97]">Prompt packs used to specialize worker and critic roles.</p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-[8px] border-[#e5e5e3] text-[12px]"
                  onClick={startNewSkillPack}
                >
                  New
                </Button>
              </div>
              <div className="border-b border-[#ecebe8] px-4 py-3">
                <Input
                  value={skillPackFilter}
                  onChange={(event) => setSkillPackFilter(event.target.value)}
                  placeholder="Search skill packs"
                />
              </div>
              <ScrollArea className="h-[620px]">
                <div className="space-y-2 px-3 py-3">
                  {filteredSkillPacks.length === 0 ? (
                    <div className="rounded-[10px] border border-dashed border-[#e5e5e3] px-4 py-6 text-[13px] text-[#9b9a97]">
                      {catalog.skill_packs.length === 0 ? "No skill packs configured yet." : "No skill packs match your search."}
                    </div>
                  ) : (
                    filteredSkillPacks.map((skillPack) => {
                      const selected = skillPack.id === selectedSkillPackId;
                      const summary = skillPackSummary(skillPack);
                      return (
                        <button
                          key={skillPack.id}
                          type="button"
                          onClick={() => selectSkillPack(skillPack)}
                          className={cn(
                            "w-full rounded-[12px] border px-4 py-3 text-left transition-colors",
                            selected
                              ? "border-[#d7d6d2] bg-[#fbfbf9] shadow-[0_1px_3px_rgba(15,15,15,0.06)]"
                              : "border-transparent hover:bg-[#f7f7f5]"
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-[13px] font-semibold text-[#37352f]">{skillPack.name}</p>
                              <p className="mt-1 text-[12px] text-[#787774]">{skillPack.id}</p>
                            </div>
                            <Badge className={cn("border-0 text-[11px]", summary.statusClass)} variant="outline">
                              {summary.status}
                            </Badge>
                          </div>
                          <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed text-[#6b6b6b]">
                            {skillPack.description || "No description provided."}
                          </p>
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {skillPack.tags.slice(0, 3).map((tag) => (
                              <Badge key={tag} variant="outline" className="border-[#ecebe8] bg-white text-[11px] text-[#787774]">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </section>

            <section className="rounded-[14px] border border-[#e5e5e3] bg-white p-5 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <div className="flex items-center justify-between gap-3 border-b border-[#ecebe8] pb-4">
                <div>
                  <h3 className="text-[16px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    {selectedSkillPackId ? "Edit skill pack" : "Create skill pack"}
                  </h3>
                  <p className="mt-1 text-[13px] text-[#787774]">
                    Specialize agents with role prompts and connector preferences.
                  </p>
                </div>
                <Badge variant="outline" className="border-[#ecebe8] bg-[#f7f7f5] text-[#787774]">
                  {skillPackDraft.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Id
                  </span>
                  <Input
                    value={skillPackDraft.id}
                    onChange={(event) => setSkillPackDraft((current) => ({ ...current, id: event.target.value }))}
                    placeholder="fastapi-backend"
                    disabled={Boolean(selectedSkillPackId)}
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Name
                  </span>
                  <Input
                    value={skillPackDraft.name}
                    onChange={(event) => setSkillPackDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="FastAPI Backend"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Description
                  </span>
                  <Textarea
                    value={skillPackDraft.description}
                    onChange={(event) => setSkillPackDraft((current) => ({ ...current, description: event.target.value }))}
                    className="min-h-20"
                    placeholder="What this skill pack is for."
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Prompt
                  </span>
                  <Textarea
                    value={skillPackDraft.prompt}
                    onChange={(event) => setSkillPackDraft((current) => ({ ...current, prompt: event.target.value }))}
                    className="min-h-40"
                    placeholder="Instructions the worker should always follow."
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Tags
                  </span>
                  <Input
                    value={skillPackDraft.tags}
                    onChange={(event) => setSkillPackDraft((current) => ({ ...current, tags: event.target.value }))}
                    placeholder="backend, api, fastapi"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Default roles
                  </span>
                  <Input
                    value={skillPackDraft.default_roles}
                    onChange={(event) => setSkillPackDraft((current) => ({ ...current, default_roles: event.target.value }))}
                    placeholder="backend_worker, fullstack_worker"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Preferred connectors
                  </span>
                  <Input
                    value={skillPackDraft.preferred_connectors}
                    onChange={(event) => setSkillPackDraft((current) => ({ ...current, preferred_connectors: event.target.value }))}
                    placeholder="shell_exec, python_exec, web_docs"
                  />
                </label>
              </div>

              <label className="mt-4 flex items-center gap-2 text-[13px] text-[#37352f]">
                <input
                  type="checkbox"
                  checked={skillPackDraft.enabled}
                  onChange={(event) => setSkillPackDraft((current) => ({ ...current, enabled: event.target.checked }))}
                  className="h-4 w-4 rounded border-[#d0cfcc]"
                />
                Enabled for planning and routing
              </label>

              <div className="mt-5 flex items-center justify-end gap-2">
                {selectedSkillPack && !selectedSkillPack.built_in && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-9 rounded-[8px] border-[#f0d7d1] text-[13px] text-[#93370d] hover:bg-[#fff7f5]"
                    onClick={() => void removeSelectedSkillPack()}
                    disabled={saving}
                  >
                    Delete skill pack
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="h-9 rounded-[8px] border-[#e5e5e3] text-[13px]"
                  onClick={startNewSkillPack}
                  disabled={saving}
                >
                  New skill pack
                </Button>
                <Button
                  size="sm"
                  className="h-9 rounded-[8px] bg-[#37352f] text-[13px] hover:bg-[#4a4a45]"
                  onClick={() => void saveSkillPack()}
                  disabled={saving}
                >
                  {saving ? "Saving..." : selectedSkillPackId ? "Update skill pack" : "Create skill pack"}
                </Button>
              </div>

              <div className="mt-5 rounded-[12px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Roles routing catalog</p>
                <div className="mt-3 space-y-3">
                  {catalog.roles.length === 0 ? (
                    <p className="text-[13px] text-[#9b9a97]">No roles loaded.</p>
                  ) : (
                    catalog.roles.map((role) => (
                      <div key={role.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-2">
                        <p className="text-[13px] font-medium text-[#37352f]">{role.name}</p>
                        <p className="mt-1 text-[12px] leading-relaxed text-[#787774]">{role.description}</p>
                        <p className="mt-1 text-[11px] text-[#9b9a97]">{roleSummary(role)}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>
          </div>
        </TabsContent>

        <TabsContent value="routing" className="mt-0">
          <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
            <section className="rounded-[14px] border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <div className="flex items-center justify-between border-b border-[#ecebe8] px-4 py-3">
                <div>
                  <h3 className="text-[14px] font-semibold text-[#37352f]">Role routing</h3>
                  <p className="text-[12px] text-[#9b9a97]">Override connector policy and preferred skill packs per role.</p>
                </div>
              </div>
              <div className="border-b border-[#ecebe8] px-4 py-3">
                <Input
                  value={roleFilter}
                  onChange={(event) => setRoleFilter(event.target.value)}
                  placeholder="Search roles"
                />
              </div>
              <ScrollArea className="h-[620px]">
                <div className="space-y-2 px-3 py-3">
                  {filteredRoles.length === 0 ? (
                    <div className="rounded-[10px] border border-dashed border-[#e5e5e3] px-4 py-6 text-[13px] text-[#9b9a97]">
                      No roles match your search.
                    </div>
                  ) : (
                    filteredRoles.map((role) => {
                      const selected = role.id === selectedRoleId;
                      const policy = catalog.routing_policies.find((item) => item.role_id === role.id);
                      return (
                        <button
                          key={role.id}
                          type="button"
                          onClick={() => selectRole(role)}
                          className={cn(
                            "w-full rounded-[12px] border px-4 py-3 text-left transition-colors",
                            selected
                              ? "border-[#d7d6d2] bg-[#fbfbf9] shadow-[0_1px_3px_rgba(15,15,15,0.06)]"
                              : "border-transparent hover:bg-[#f7f7f5]"
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-[13px] font-semibold text-[#37352f]">{role.name}</p>
                              <p className="mt-1 text-[12px] text-[#787774]">{role.id}</p>
                            </div>
                            <Badge variant="outline" className="border-[#ecebe8] bg-white text-[11px] text-[#787774]">
                              {policy ? "Custom" : "Default"}
                            </Badge>
                          </div>
                          <p className="mt-2 text-[12px] leading-relaxed text-[#6b6b6b]">{role.description}</p>
                          <p className="mt-2 text-[11px] text-[#9b9a97]">{roleSummary(role)}</p>
                        </button>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </section>

            <section className="rounded-[14px] border border-[#e5e5e3] bg-white p-5 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <div className="flex items-center justify-between gap-3 border-b border-[#ecebe8] pb-4">
                <div>
                  <h3 className="text-[16px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Routing policy
                  </h3>
                  <p className="mt-1 text-[13px] text-[#787774]">
                    Manual overrides are applied on top of automatic role, tag, and skill-pack routing.
                  </p>
                </div>
                <Badge variant="outline" className="border-[#ecebe8] bg-[#f7f7f5] text-[#787774]">
                  {selectedRole?.name || "Select role"}
                </Badge>
              </div>

              {selectedRole ? (
                <>
                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <label className="block md:col-span-2">
                      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                        Preferred skill packs
                      </span>
                      <Input
                        value={routingPolicyDraft.preferred_skill_packs}
                        onChange={(event) =>
                          setRoutingPolicyDraft((current) => ({ ...current, preferred_skill_packs: event.target.value }))
                        }
                        placeholder={selectedRole.default_skill_packs.join(", ") || "fastapi-backend"}
                      />
                    </label>
                    <label className="block md:col-span-2">
                      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                        Required connectors
                      </span>
                      <Input
                        value={routingPolicyDraft.required_connectors}
                        onChange={(event) =>
                          setRoutingPolicyDraft((current) => ({ ...current, required_connectors: event.target.value }))
                        }
                        placeholder="context7, http_api"
                      />
                    </label>
                    <label className="block md:col-span-2">
                      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                        Preferred connectors
                      </span>
                      <Input
                        value={routingPolicyDraft.preferred_connectors}
                        onChange={(event) =>
                          setRoutingPolicyDraft((current) => ({ ...current, preferred_connectors: event.target.value }))
                        }
                        placeholder={selectedRole.default_connectors.join(", ") || "shell_exec, python_exec"}
                      />
                    </label>
                    <label className="block md:col-span-2">
                      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                        Forbidden connectors
                      </span>
                      <Input
                        value={routingPolicyDraft.forbidden_connectors}
                        onChange={(event) =>
                          setRoutingPolicyDraft((current) => ({ ...current, forbidden_connectors: event.target.value }))
                        }
                        placeholder="browser_devtools"
                      />
                    </label>
                  </div>

                  <div className="mt-5 flex items-center justify-end gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-9 rounded-[8px] border-[#e5e5e3] text-[13px]"
                      onClick={() =>
                        setRoutingPolicyDraft(
                          catalog.routing_policies.find((policy) => policy.role_id === selectedRole.id)
                            ? formatRoutingPolicyDraft(
                                catalog.routing_policies.find((policy) => policy.role_id === selectedRole.id)!
                              )
                            : { ...EMPTY_ROUTING_POLICY, role_id: selectedRole.id }
                        )
                      }
                      disabled={saving}
                    >
                      Reset
                    </Button>
                    <Button
                      size="sm"
                      className="h-9 rounded-[8px] bg-[#37352f] text-[13px] hover:bg-[#4a4a45]"
                      onClick={() => void saveRoutingPolicy()}
                      disabled={saving}
                    >
                      {saving ? "Saving..." : "Save routing policy"}
                    </Button>
                  </div>

                  <div className="mt-5 space-y-4 rounded-[12px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Launch presets</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                        {catalog.launch_presets.map((preset) => (
                          <div key={preset.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                            <p className="text-[13px] font-semibold text-[#37352f]">{preset.label}</p>
                            <p className="mt-1 text-[12px] leading-relaxed text-[#787774]">{preset.description}</p>
                            <p className="mt-2 text-[11px] text-[#9b9a97]">
                              {preset.launch_profile.story_execution_mode}/{preset.launch_profile.project_concurrency_mode}
                              {" · "}
                              {preset.launch_profile.max_parallel_stories} parallel
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">How overrides work</p>
                      <ul className="mt-2 space-y-1.5 text-[13px] leading-relaxed text-[#6b6b6b]">
                        <li>Automatic routing still starts from role defaults, story tags, and skill-pack connector preferences.</li>
                        <li>`required_connectors` block story start if they cannot activate successfully at runtime.</li>
                        <li>`preferred_connectors` are added after auto-selection and show up in launch preview and workspace runtime state.</li>
                        <li>`forbidden_connectors` suppress auto-selected connectors unless the story explicitly pins them.</li>
                      </ul>
                    </div>
                  </div>
                </>
              ) : (
                <div className="mt-4 rounded-[12px] border border-dashed border-[#e5e5e3] px-4 py-8 text-[13px] text-[#9b9a97]">
                  Select a role to edit its routing policy.
                </div>
              )}
            </section>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
