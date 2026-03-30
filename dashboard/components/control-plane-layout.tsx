"use client";

import { AppSidebar } from "@/components/app-sidebar";
import { ControlPlaneHeaderSections } from "@/components/control-plane-header-sections";
import { ControlPlaneMainSections } from "@/components/control-plane-main-sections";
import type { AccountHealth, ProjectSummary } from "@/lib/types";
import type { ComponentProps } from "react";

type ControlPlaneLayoutProps = {
  health: AccountHealth | null;
  visibleProjects: ProjectSummary[];
  headerSectionProps: ComponentProps<typeof ControlPlaneHeaderSections>;
  mainSectionsProps: ComponentProps<typeof ControlPlaneMainSections>;
};

export function ControlPlaneLayout({
  health,
  visibleProjects,
  headerSectionProps,
  mainSectionsProps,
}: ControlPlaneLayoutProps) {
  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={health} projects={visibleProjects} />
      <main className="flex-1 pl-[260px]">
        <ControlPlaneHeaderSections {...headerSectionProps} />
        <ControlPlaneMainSections {...mainSectionsProps} />
      </main>
    </div>
  );
}
