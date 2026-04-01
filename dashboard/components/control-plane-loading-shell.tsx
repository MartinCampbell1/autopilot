"use client";

import { AppSidebar } from "@/components/app-sidebar";
import type { AccountHealth, ProjectSummary } from "@/lib/types";

type ControlPlaneLoadingShellProps = {
  health: AccountHealth | null;
  visibleProjects: ProjectSummary[];
};

export function ControlPlaneLoadingShell({
  health,
  visibleProjects,
}: ControlPlaneLoadingShellProps) {
  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={health} projects={visibleProjects} />
      <main className="flex flex-1 items-center justify-center pl-[260px] text-[14px] text-[#787774]">
        Loading control plane...
      </main>
    </div>
  );
}
