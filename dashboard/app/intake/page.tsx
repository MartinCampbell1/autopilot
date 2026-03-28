"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppSidebar } from "@/components/app-sidebar";
import { IntakeChat } from "@/components/intake-chat";
import { SpecImportPanel } from "@/components/spec-import-panel";
import { Button } from "@/components/ui/button";
import {
  createProjectFromPrd,
  fetchAccountsHealth,
  fetchCapabilitiesCatalog,
  fetchProjects,
  launchProject as launchProjectRun,
} from "@/lib/api";
import type { LaunchPreset, PRD, ProjectSummary } from "@/lib/types";

const FALLBACK_PRESETS: LaunchPreset[] = [
  {
    id: "fast",
    label: "Fast",
    description: "One primary worker per story, sequential execution.",
    launch_profile: { preset: "fast", story_execution_mode: "solo", project_concurrency_mode: "sequential", max_parallel_stories: 1 },
  },
  {
    id: "team",
    label: "Team",
    description: "Primary worker, critic, and optional specialist.",
    launch_profile: { preset: "team", story_execution_mode: "team", project_concurrency_mode: "sequential", max_parallel_stories: 1 },
  },
  {
    id: "parallel",
    label: "Parallel",
    description: "Story teams with parallel worktrees.",
    launch_profile: { preset: "parallel", story_execution_mode: "team", project_concurrency_mode: "parallel", max_parallel_stories: 3 },
  },
];

function inferSpecialist(tags: string[] = []) {
  const set = new Set(tags);
  if (["frontend", "ui", "design"].some((tag) => set.has(tag))) return "UI Specialist";
  if (["graph", "database", "data", "analytics"].some((tag) => set.has(tag))) return "Data Specialist";
  if (["backend", "api", "docs", "research"].some((tag) => set.has(tag))) return "API Specialist";
  return null;
}

export default function IntakePage() {
  const router = useRouter();
  const [prd, setPRD] = useState<PRD | null>(null);
  const [mode, setMode] = useState<"chat" | "spec">("chat");
  const [projectName, setProjectName] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [launching, setLaunching] = useState(false);
  const [message, setMessage] = useState("");
  const [editingPrd, setEditingPrd] = useState(false);
  const [prdDraft, setPrdDraft] = useState("");
  const [health, setHealth] = useState<{ total: number; available: number; on_cooldown: number } | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [launchPresetId, setLaunchPresetId] = useState<"fast" | "team" | "parallel">("fast");
  const [launchPresets, setLaunchPresets] = useState<LaunchPreset[]>(FALLBACK_PRESETS);

  useEffect(() => {
    void Promise.all([fetchAccountsHealth(), fetchProjects(false), fetchCapabilitiesCatalog()])
      .then(([healthData, projectsData, catalog]) => {
        setHealth(healthData);
        setProjects((projectsData.projects || []) as ProjectSummary[]);
        const presets = (catalog.launch_presets || []) as LaunchPreset[];
        setLaunchPresets(presets.length ? presets : FALLBACK_PRESETS);
      })
      .catch(() => {
        setHealth(null);
        setProjects([]);
        setLaunchPresets(FALLBACK_PRESETS);
      });
  }, []);

  useEffect(() => {
    if (!prd) return;
    setProjectName(prd.title || "");
    setPrdDraft(JSON.stringify(prd, null, 2));
  }, [prd]);

  const handlePRDReady = (nextPrd: PRD) => {
    setPRD(nextPrd);
    setMessage("");
    setEditingPrd(false);
  };

  const saveEditedPrd = () => {
    try {
      const parsed = JSON.parse(prdDraft) as PRD;
      setPRD(parsed);
      setProjectName(parsed.title || projectName);
      setEditingPrd(false);
      setMessage("PRD updated.");
    } catch {
      setMessage("PRD JSON is invalid. Fix it before saving.");
    }
  };

  const launchProject = async () => {
    if (!prd || launching || editingPrd) return;

    setLaunching(true);
    setMessage("");

    try {
      const data = await createProjectFromPrd(
        prd,
        projectName.trim() || prd.title,
        projectPath.trim() || undefined
      );
      const activePreset =
        launchPresets.find((preset) => preset.id === launchPresetId) ||
        FALLBACK_PRESETS.find((preset) => preset.id === launchPresetId) ||
        FALLBACK_PRESETS[0];
      const launch = await launchProjectRun(data.project_id, activePreset.launch_profile);
      setMessage(launch.message);
      router.push(`/projects/${data.project_id}`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to launch project.");
    } finally {
      setLaunching(false);
    }
  };

  const activeLaunchPreset =
    launchPresets.find((preset) => preset.id === launchPresetId) ||
    FALLBACK_PRESETS.find((preset) => preset.id === launchPresetId) ||
    FALLBACK_PRESETS[0];
  const launchPreviewStory = prd?.stories?.[0];
  const launchPreviewSpecialist =
    activeLaunchPreset.launch_profile.story_execution_mode === "team"
      ? inferSpecialist(launchPreviewStory?.tags || [])
      : null;

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={health} projects={projects} />

      <main className="flex-1 pl-[260px]">
        <header className="sticky top-0 z-30 flex h-[52px] items-center justify-between border-b border-[#e5e5e3] bg-white px-6">
          <h1 className="text-[15px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">New Project</h1>
          <div className="flex items-center gap-2 rounded-[8px] bg-[#f1f1ef] p-1">
            <button
              type="button"
              onClick={() => setMode("chat")}
              className={mode === "chat" ? "rounded-[6px] bg-white px-3 py-1.5 text-[13px] font-medium text-[#37352f] shadow-sm" : "rounded-[6px] px-3 py-1.5 text-[13px] text-[#787774]"}
            >
              Chat
            </button>
            <button
              type="button"
              onClick={() => setMode("spec")}
              className={mode === "spec" ? "rounded-[6px] bg-white px-3 py-1.5 text-[13px] font-medium text-[#37352f] shadow-sm" : "rounded-[6px] px-3 py-1.5 text-[13px] text-[#787774]"}
            >
              Import Spec
            </button>
          </div>
        </header>

        <div className="mx-auto max-w-2xl px-6 py-8">
          {mode === "chat" ? (
            <IntakeChat onPRDReady={handlePRDReady} />
          ) : (
            <SpecImportPanel onPRDReady={handlePRDReady} />
          )}

          {prd && (
            <div className="mt-8 rounded-xl border border-[#e5e5e3] bg-white overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
              <div className="px-5 py-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-[17px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">
                    {prd.title}
                  </h3>
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-[12px] font-semibold text-emerald-700">
                    Ready
                  </span>
                </div>
                <p className="mt-2.5 text-[14px] text-[#6b6b6b] leading-relaxed">
                  {prd.description}
                </p>
              </div>

              <div className="border-t border-[#e5e5e3] px-5 py-5">
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="block">
                    <span className="mb-1.5 block text-[12px] font-semibold uppercase tracking-wider text-[#9ca3af]">
                      Project Name
                    </span>
                    <input
                      value={projectName}
                      onChange={(event) => setProjectName(event.target.value)}
                      className="h-10 w-full rounded-[8px] border border-[#e3e2e0] bg-[#fbfbf9] px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f] focus:bg-white"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-[12px] font-semibold uppercase tracking-wider text-[#9ca3af]">
                      Project Path
                    </span>
                    <input
                      value={projectPath}
                      onChange={(event) => setProjectPath(event.target.value)}
                      placeholder="Optional custom path"
                      className="h-10 w-full rounded-[8px] border border-[#e3e2e0] bg-[#fbfbf9] px-3 text-[14px] text-[#37352f] outline-none focus:border-[#37352f] focus:bg-white"
                    />
                  </label>
                </div>
              </div>

              <div className="border-t border-[#e5e5e3] px-5 py-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 className="text-[12px] font-semibold uppercase tracking-wider text-[#9ca3af]">
                      Launch Mode
                    </h4>
                    <p className="mt-1 text-[13px] text-[#787774]">
                      Choose how Autopilot assigns teams and runs stories.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 rounded-[8px] bg-[#f1f1ef] p-1">
                    {launchPresets.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => setLaunchPresetId(preset.id as "fast" | "team" | "parallel")}
                        className={
                          launchPresetId === preset.id
                            ? "rounded-[6px] bg-white px-3 py-1.5 text-[13px] font-medium text-[#37352f] shadow-sm"
                            : "rounded-[6px] px-3 py-1.5 text-[13px] text-[#787774]"
                        }
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-4 rounded-[12px] border border-[#e5e5e3] bg-[#fbfbf9] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[14px] font-semibold text-[#37352f]">{activeLaunchPreset.label}</p>
                      <p className="mt-1 text-[13px] text-[#787774]">{activeLaunchPreset.description}</p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold text-[#6b6b6b]">
                      {activeLaunchPreset.launch_profile.story_execution_mode}/{activeLaunchPreset.launch_profile.project_concurrency_mode}
                    </span>
                  </div>

                  {launchPreviewStory && (
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <div className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                        <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Primary role</p>
                        <p className="mt-1 text-[13px] font-medium text-[#37352f]">
                          {launchPreviewStory.role || "backend_worker"}
                        </p>
                        <p className="mt-2 text-[12px] text-[#787774]">
                          Skills: {(launchPreviewStory.skill_packs || []).join(", ") || "none"}
                        </p>
                        <p className="mt-1 text-[12px] text-[#787774]">
                          Connectors: {(launchPreviewStory.connectors || []).join(", ") || "none"}
                        </p>
                      </div>
                      <div className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                        <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Launch preview</p>
                        <p className="mt-1 text-[13px] font-medium text-[#37352f]">
                          {activeLaunchPreset.launch_profile.max_parallel_stories} active story slot
                          {activeLaunchPreset.launch_profile.max_parallel_stories > 1 ? "s" : ""}
                        </p>
                        <p className="mt-2 text-[12px] text-[#787774]">
                          Critic: always attached for review.
                        </p>
                        <p className="mt-1 text-[12px] text-[#787774]">
                          Specialist: {launchPreviewSpecialist || "Not required for the first story."}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {editingPrd && (
                <div className="border-t border-[#e5e5e3] px-5 py-5">
                  <h4 className="mb-3 text-[12px] font-semibold uppercase tracking-wider text-[#9ca3af]">
                    Edit PRD JSON
                  </h4>
                  <textarea
                    value={prdDraft}
                    onChange={(event) => setPrdDraft(event.target.value)}
                    className="h-[280px] w-full resize-none rounded-[8px] border border-[#e3e2e0] bg-[#fbfbf9] px-4 py-3 font-mono text-[12px] leading-[1.55] text-[#37352f] outline-none focus:border-[#37352f] focus:bg-white"
                  />
                </div>
              )}

              <div className="border-t border-[#e5e5e3] px-5 py-5">
                <h4 className="text-[12px] font-semibold uppercase tracking-wider text-[#9ca3af] mb-3">
                  Stories ({prd.stories?.length || 0})
                </h4>
                <div className="space-y-2">
                  {prd.stories?.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-start gap-3 rounded-lg border border-[#e5e5e3] px-4 py-3"
                    >
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[#f0f0ee] text-[11px] font-bold tabular-nums text-[#6b6b6b]">
                        {s.id}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[14px] font-medium text-[#1a1a1a]">{s.title}</p>
                        {s.description && (
                          <p className="mt-0.5 text-[13px] text-[#9ca3af] truncate">
                            {s.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border-t border-[#e5e5e3] px-5 py-3.5">
                <p className="mb-3 min-h-[20px] text-[13px] text-[#787774]">{message}</p>
                <div className="flex justify-end gap-2">
                  {editingPrd ? (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-9 rounded-lg text-[13px] border-[#e5e5e3]"
                        onClick={() => {
                          setEditingPrd(false);
                          setPrdDraft(JSON.stringify(prd, null, 2));
                          setMessage("");
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        className="h-9 rounded-lg text-[13px] bg-[#37352f] hover:bg-[#4a4a45]"
                        onClick={saveEditedPrd}
                      >
                        Save PRD
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-9 rounded-lg text-[13px] border-[#e5e5e3]"
                      onClick={() => setEditingPrd(true)}
                    >
                      Edit PRD
                    </Button>
                  )}
                  <Button
                    size="sm"
                    className="h-9 rounded-lg text-[13px] bg-[#1a1a1a] hover:bg-[#333]"
                    onClick={() => void launchProject()}
                    disabled={launching || editingPrd}
                  >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                    {launching ? "Launching..." : "Launch Project"}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
