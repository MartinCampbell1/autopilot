"use client";

import type { ComponentProps } from "react";
import { ControlPlaneWorkspaceSection } from "@/components/control-plane-workspace-section";
import { SessionDrilldownSection } from "@/components/session-drilldown-section";

type ControlPlaneMainSectionsProps = {
  notice: string;
  errorMessage: string;
  workspaceSectionProps: ComponentProps<typeof ControlPlaneWorkspaceSection>;
  sessionDrilldownSectionProps: ComponentProps<typeof SessionDrilldownSection>;
};

export function ControlPlaneMainSections({
  notice,
  errorMessage,
  workspaceSectionProps,
  sessionDrilldownSectionProps,
}: ControlPlaneMainSectionsProps) {
  return (
    <div className="space-y-6 px-6 py-6">
      {notice && (
        <div className="rounded-xl border border-[#d6e9dc] bg-[#eef8f1] px-4 py-3 text-[13px] text-[#2b6e3f]">
          {notice}
        </div>
      )}
      {errorMessage && (
        <div className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] px-4 py-3 text-[13px] text-[#93370d]">
          {errorMessage}
        </div>
      )}

      <ControlPlaneWorkspaceSection {...workspaceSectionProps} />
      <SessionDrilldownSection {...sessionDrilldownSectionProps} />
    </div>
  );
}
