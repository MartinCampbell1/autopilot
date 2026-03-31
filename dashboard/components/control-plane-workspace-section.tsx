"use client";

import type { ComponentProps } from "react";
import { ControlPlaneOverviewSections } from "@/components/control-plane-overview-sections";
import { RuntimeAgentSection } from "@/components/runtime-agent-section";
import { SelectedActionRunCard } from "@/components/selected-action-run-card";
import { SessionLineageSection } from "@/components/session-lineage-section";
import { SessionMetric } from "@/components/control-plane-display";
import { TriageInboxSection } from "@/components/triage-inbox-section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { passStatusClass } from "@/lib/control-plane-ui";
import type { OrchestratorControlPassRecord } from "@/lib/types";

type ControlPlaneWorkspaceSectionProps = {
  recentControlPasses: OrchestratorControlPassRecord[];
  totalControlPassCount: number;
  selectedPassId: string;
  formatTimestamp: (value?: string | null) => string;
  toStringValue: (value: unknown, fallback?: string) => string;
  toNumber: (value: unknown, fallback?: number) => number;
  onInspectControlPass: (controlPass: OrchestratorControlPassRecord) => void;
  selectedActionRunCardProps: ComponentProps<typeof SelectedActionRunCard>;
  sessionLineageSectionProps: ComponentProps<typeof SessionLineageSection>;
  triageInboxSectionProps: ComponentProps<typeof TriageInboxSection>;
  runtimeAgentSectionProps: ComponentProps<typeof RuntimeAgentSection>;
  controlPlaneOverviewSectionsProps: ComponentProps<typeof ControlPlaneOverviewSections>;
};

export function ControlPlaneWorkspaceSection({
  recentControlPasses,
  totalControlPassCount,
  selectedPassId,
  formatTimestamp,
  toStringValue,
  toNumber,
  onInspectControlPass,
  selectedActionRunCardProps,
  sessionLineageSectionProps,
  triageInboxSectionProps,
  runtimeAgentSectionProps,
  controlPlaneOverviewSectionsProps,
}: ControlPlaneWorkspaceSectionProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.9fr)]">
      <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <CardHeader>
          <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Recent Control Passes
          </CardTitle>
          <CardDescription className="text-[13px] text-[#787774]">
            Latest session-level FounderOS control passes, now selectable for drill-down.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentControlPasses.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
              {totalControlPassCount
                ? "No orchestrator control passes match the current history search."
                : "No orchestrator control passes recorded yet."}
            </div>
          ) : (
            <div className="space-y-3">
              {recentControlPasses.map((controlPass) => {
                const finalState = toStringValue(controlPass.summary.final_state, "unknown");
                const stoppedReason = toStringValue(controlPass.summary.stopped_reason);
                const appliedSteps = toNumber(
                  controlPass.summary.applied,
                  controlPass.applied.length
                );
                const errorSteps = toNumber(controlPass.summary.errors, controlPass.errors.length);
                const selected = selectedPassId === controlPass.id;

                return (
                  <div
                    key={controlPass.id}
                    className={`rounded-2xl border p-4 ${
                      selected
                        ? "border-[#d3e5ef] bg-[#f7fbfd] shadow-[0_1px_2px_rgba(42,102,144,0.08)]"
                        : "border-[#ecebe8] bg-[#fbfbf9]"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                            {controlPass.id}
                          </p>
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(controlPass.status)}`}
                          >
                            {controlPass.status}
                          </Badge>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {controlPass.profile}
                          </Badge>
                        </div>
                        <p className="mt-2 text-[13px] text-[#6b6b6b]">
                          Session{" "}
                          <span className="font-mono text-[#37352f]">
                            {controlPass.orchestrator_session_id}
                          </span>
                          {" · "}
                          {controlPass.actor || "unknown actor"}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-[12px] text-[#9b9a97]">
                          {formatTimestamp(controlPass.created_at)}
                        </p>
                        <Button
                          size="sm"
                          variant={selected ? "default" : "outline"}
                          className={`mt-2 h-8 rounded-lg text-[12px] ${
                            selected
                              ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                              : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                          }`}
                          onClick={() => {
                            onInspectControlPass(controlPass);
                          }}
                        >
                          {selected ? "Selected" : "Inspect"}
                        </Button>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <SessionMetric
                        label="Outcome"
                        value={finalState}
                        detail={`${appliedSteps} applied · ${errorSteps} errors`}
                      />
                      <SessionMetric
                        label="Coverage"
                        value={`${controlPass.project_ids.length} project${controlPass.project_ids.length === 1 ? "" : "s"}`}
                        detail={controlPass.initiative_id || "No initiative mapping"}
                      />
                      <SessionMetric
                        label="Reason"
                        value={stoppedReason || controlPass.reason || "No stop reason"}
                        detail={`${controlPass.recommendation_kinds.length} recommendation kind(s)`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="space-y-6">
        <SelectedActionRunCard {...selectedActionRunCardProps} />
        <SessionLineageSection {...sessionLineageSectionProps} />
        <TriageInboxSection {...triageInboxSectionProps} />
        <RuntimeAgentSection {...runtimeAgentSectionProps} />
        <ControlPlaneOverviewSections {...controlPlaneOverviewSectionsProps} />
      </div>
    </section>
  );
}
