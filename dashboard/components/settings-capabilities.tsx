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
  fetchCapabilitiesCatalog,
  updateConnector,
  updateSkillPack,
} from "@/lib/api";
import type { CapabilitiesCatalog, MCPConnector, RoleTemplate, SkillPack } from "@/lib/types";
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

const CONNECTOR_TYPES = ["mcp_server", "http_api", "builtin", "custom"];
const TRANSPORTS = ["stdio", "http", "builtin"];
const RISK_LEVELS = ["low", "medium", "high"];

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

export function SettingsCapabilitiesManager() {
  const [catalog, setCatalog] = useState<CapabilitiesCatalog>({ connectors: [], skill_packs: [], roles: [] });
  const [activeTab, setActiveTab] = useState<"connectors" | "skill-packs">("connectors");
  const [selectedConnectorId, setSelectedConnectorId] = useState<string>("");
  const [selectedSkillPackId, setSelectedSkillPackId] = useState<string>("");
  const [connectorDraft, setConnectorDraft] = useState<ConnectorDraft>(EMPTY_CONNECTOR);
  const [skillPackDraft, setSkillPackDraft] = useState<SkillPackDraft>(EMPTY_SKILL_PACK);
  const [connectorFilter, setConnectorFilter] = useState("");
  const [skillPackFilter, setSkillPackFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

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
    } else if (!selectedConnectorId) {
      setConnectorDraft(EMPTY_CONNECTOR);
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

  const selectConnector = (connector: MCPConnector) => {
    setActiveTab("connectors");
    setSelectedConnectorId(connector.id);
    setConnectorDraft(formatConnectorDraft(connector));
    setMessage("");
  };

  const selectSkillPack = (skillPack: SkillPack) => {
    setActiveTab("skill-packs");
    setSelectedSkillPackId(skillPack.id);
    setSkillPackDraft(formatSkillPackDraft(skillPack));
    setMessage("");
  };

  const startNewConnector = () => {
    setActiveTab("connectors");
    setSelectedConnectorId("");
    setConnectorDraft(EMPTY_CONNECTOR);
    setMessage("");
  };

  const startNewSkillPack = () => {
    setActiveTab("skill-packs");
    setSelectedSkillPackId("");
    setSkillPackDraft(EMPTY_SKILL_PACK);
    setMessage("");
  };

  const saveConnector = async () => {
    const id = connectorDraft.id.trim();
    if (!id) {
      setMessage("Connector id is required.");
      return;
    }

    let config: Record<string, unknown> = {};
    try {
      config = connectorDraft.config.trim() ? JSON.parse(connectorDraft.config) : {};
    } catch {
      setMessage("Connector config must be valid JSON.");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        id,
        name: connectorDraft.name.trim() || id,
        connector_type: connectorDraft.connector_type.trim() || "mcp_server",
        description: connectorDraft.description.trim(),
        transport: connectorDraft.transport.trim() || "stdio",
        tags: splitList(connectorDraft.tags),
        providers: splitList(connectorDraft.providers),
        risk_level: connectorDraft.risk_level.trim() || "medium",
        scopes: splitList(connectorDraft.scopes),
        enabled: connectorDraft.enabled,
        config,
      };

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
      await loadCatalog();
      setSelectedConnectorId(id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save connector.");
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
        onValueChange={(value) => setActiveTab((value as "connectors" | "skill-packs") || "connectors")}
        className="gap-4"
        orientation="horizontal"
      >
        <TabsList className="w-full justify-start bg-[#f1f1ef]">
          <TabsTrigger value="connectors">Connectors</TabsTrigger>
          <TabsTrigger value="skill-packs">Skill Packs</TabsTrigger>
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
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, connector_type: event.target.value }))}
                    className="h-10 w-full rounded-lg border border-[#e3e2e0] bg-white px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f]"
                  >
                    {CONNECTOR_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
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
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, transport: event.target.value }))}
                    className="h-10 w-full rounded-lg border border-[#e3e2e0] bg-white px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f]"
                  >
                    {TRANSPORTS.map((transport) => (
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
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, providers: event.target.value }))}
                    placeholder="codex, claude, gemini"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Risk Level
                  </span>
                  <select
                    value={connectorDraft.risk_level}
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, risk_level: event.target.value }))}
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
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, tags: event.target.value }))}
                    placeholder="backend, graph, docs"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Scopes
                  </span>
                  <Input
                    value={connectorDraft.scopes}
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, scopes: event.target.value }))}
                    placeholder="network, database, browser"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Description
                  </span>
                  <Textarea
                    value={connectorDraft.description}
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, description: event.target.value }))}
                    placeholder="What this connector exposes to agents."
                    className="min-h-24"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Config JSON
                  </span>
                  <Textarea
                    value={connectorDraft.config}
                    onChange={(event) => setConnectorDraft((current) => ({ ...current, config: event.target.value }))}
                    className="min-h-40 font-mono text-[12px]"
                    placeholder='{\n  "base_url": "https://..."\n}'
                  />
                </label>
              </div>

              <label className="mt-4 flex items-center gap-2 text-[13px] text-[#37352f]">
                <input
                  type="checkbox"
                  checked={connectorDraft.enabled}
                  onChange={(event) => setConnectorDraft((current) => ({ ...current, enabled: event.target.checked }))}
                  className="h-4 w-4 rounded border-[#d0cfcc]"
                />
                Enabled for planning and assignment
              </label>

              <div className="mt-5 flex items-center justify-end gap-2">
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
      </Tabs>
    </div>
  );
}
