"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { SettingsCapabilitiesManager } from "@/components/settings-capabilities";
import { fetchAccountsHealth, fetchProjects } from "@/lib/api";
import { useProjectRuntimeHandoffSignals } from "@/lib/use-project-runtime-handoff-signals";
import type { AccountHealth, ProjectSummary } from "@/lib/types";

export default function SettingsPage() {
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const {
    signals: projectRuntimeHandoffSignals,
    refresh: refreshProjectRuntimeHandoffSignals,
  } = useProjectRuntimeHandoffSignals(projects);

  useEffect(() => {
    void Promise.all([fetchAccountsHealth(), fetchProjects(false)])
      .then(([healthData, projectData]) => {
        setHealth(healthData);
        setProjects((projectData.projects || []) as ProjectSummary[]);
      })
      .catch(() => {
        setHealth(null);
        setProjects([]);
      });
  }, []);

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar
        health={health}
        projects={projects}
        projectRuntimeHandoffSignals={projectRuntimeHandoffSignals}
        onRefreshProjectRuntimeHandoffSignals={refreshProjectRuntimeHandoffSignals}
      />

      <main className="flex-1 pl-[260px]">
        <header className="sticky top-0 z-30 flex h-[52px] items-center justify-between border-b border-[#e5e5e3] bg-white px-6">
          <div>
            <h1 className="text-[15px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">Settings</h1>
            <p className="mt-0.5 text-[12px] text-[#9b9a97]">
              Configure MCP connectors, API adapters, skill packs, and routing policy.
            </p>
          </div>
        </header>

        <div className="px-6 py-6">
          <div className="mb-6 grid gap-4 xl:grid-cols-3">
            <section className="rounded-[14px] border border-[#e5e5e3] bg-white px-5 py-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">Launch Checklist</p>
              <h2 className="mt-2 text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                Connect accounts, then connect tools
              </h2>
              <p className="mt-2 text-[14px] leading-relaxed text-[#6b6b6b]">
                Accounts and external tools are configured separately on purpose. First import provider
                sessions in Accounts, then define the MCP/API connectors, skill packs, and per-role routing
                policy available to the planner and workers here.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  href="/accounts"
                  className="inline-flex h-9 items-center justify-center rounded-[8px] bg-[#37352f] px-3.5 text-[13px] font-medium text-white transition-colors hover:bg-[#4a4a45]"
                >
                  Open Accounts
                </Link>
                <Link
                  href="/intake"
                  className="inline-flex h-9 items-center justify-center rounded-[8px] border border-[#e5e5e3] bg-white px-3.5 text-[13px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                >
                  New Project
                </Link>
              </div>
            </section>

            <section className="rounded-[14px] border border-[#e5e5e3] bg-white px-5 py-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">How Autopilot Uses This</p>
              <h2 className="mt-2 text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                Planner and runtime both use this catalog
              </h2>
              <p className="mt-2 text-[14px] leading-relaxed text-[#6b6b6b]">
                During intake, the planner sees your connector, skill-pack, and routing catalog. During launch,
                runtime resolves that same catalog into actual team assignments and connector activation states for
                each story.
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-[12px] text-[#787774]">
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">1. Accounts</span>
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">2. Connectors</span>
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">3. Skill Packs</span>
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">4. Routing Policy</span>
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">5. Intake & Launch</span>
              </div>
            </section>

            <section className="rounded-[14px] border border-[#e5e5e3] bg-white px-5 py-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">Local-First Runtime</p>
              <h2 className="mt-2 text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                Local endpoint and command runtimes are supported
              </h2>
              <p className="mt-2 text-[14px] leading-relaxed text-[#6b6b6b]">
                Autopilot can now execute against configured local providers such as an OpenAI-compatible
                endpoint or a wrapper command, then route the same launch contract through local, cloud, or
                hybrid runtime profiles.
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-[12px] text-[#787774]">
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">1. Edit config.yaml</span>
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">2. Run doctor --refresh</span>
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">3. Choose provider in Intake</span>
                <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1">4. Launch with runtime profile</span>
              </div>
              <p className="mt-4 text-[12px] leading-relaxed text-[#787774]">
                Canonical examples live in `README.md` and `docs/local-first-runtime.md` inside the repo.
              </p>
            </section>
          </div>

          <SettingsCapabilitiesManager />
        </div>
      </main>
    </div>
  );
}
