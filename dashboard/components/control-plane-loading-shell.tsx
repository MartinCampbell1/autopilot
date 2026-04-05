"use client";

import { AppSidebar } from "@/components/app-sidebar";
import { useProjectRuntimeHandoffSignals } from "@/lib/use-project-runtime-handoff-signals";
import type { AccountHealth, ProjectSummary } from "@/lib/types";

type ControlPlaneLoadingShellProps = {
  health: AccountHealth | null;
  visibleProjects: ProjectSummary[];
};

export function ControlPlaneLoadingShell({
  health,
  visibleProjects,
}: ControlPlaneLoadingShellProps) {
  const {
    signals: projectRuntimeHandoffSignals,
    refresh: refreshProjectRuntimeHandoffSignals,
  } = useProjectRuntimeHandoffSignals(visibleProjects);

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar
        health={health}
        projects={visibleProjects}
        projectRuntimeHandoffSignals={projectRuntimeHandoffSignals}
        onRefreshProjectRuntimeHandoffSignals={refreshProjectRuntimeHandoffSignals}
      />
      <main className="flex flex-1 items-center justify-center pl-[260px] text-[14px] text-[#787774]">
        Loading control plane...
      </main>
    </div>
  );
}
