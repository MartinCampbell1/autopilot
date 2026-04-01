"use client";

import type { ComponentProps } from "react";
import { LinkedDecisionsCard } from "@/components/linked-decisions-card";
import { SelectedControlPassCard } from "@/components/selected-control-pass-card";
import { SelectedSessionContextCard } from "@/components/selected-session-context-card";
import { SessionDrilldownActivitySection } from "@/components/session-drilldown-activity-section";
import { SessionDrilldownControlSection } from "@/components/session-drilldown-control-section";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { OrchestratorSessionDetail } from "@/lib/types";

type SessionDrilldownSectionProps = {
  selectedSessionId: string;
  sessionLoading: boolean;
  selectedSession: OrchestratorSessionDetail | null;
  controlSectionProps: ComponentProps<typeof SessionDrilldownControlSection> | null;
  activitySectionProps: ComponentProps<typeof SessionDrilldownActivitySection> | null;
  selectedControlPassCardProps: ComponentProps<typeof SelectedControlPassCard>;
  linkedDecisionsCardProps: ComponentProps<typeof LinkedDecisionsCard>;
  selectedSessionContextCardProps: ComponentProps<typeof SelectedSessionContextCard>;
};

export function SessionDrilldownSection({
  selectedSessionId,
  sessionLoading,
  selectedSession,
  controlSectionProps,
  activitySectionProps,
  selectedControlPassCardProps,
  linkedDecisionsCardProps,
  selectedSessionContextCardProps,
}: SessionDrilldownSectionProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.95fr)]">
      <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <CardHeader>
          <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Session Drill-Down
          </CardTitle>
          <CardDescription className="text-[13px] text-[#787774]">
            Inspect the selected session, apply direct recommendations, or run a session-level
            control pass profile from this panel.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!selectedSessionId ? (
            <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
              Select a recent session or control pass to inspect live control state.
            </div>
          ) : sessionLoading || !selectedSession || !controlSectionProps || !activitySectionProps ? (
            <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
              Loading session detail...
            </div>
          ) : (
            <div className="space-y-5">
              <SessionDrilldownControlSection {...controlSectionProps} />
              <SessionDrilldownActivitySection {...activitySectionProps} />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="space-y-6">
        <SelectedControlPassCard {...selectedControlPassCardProps} />
        <LinkedDecisionsCard {...linkedDecisionsCardProps} />
        <SelectedSessionContextCard {...selectedSessionContextCardProps} />
      </div>
    </section>
  );
}
