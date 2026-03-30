"use client";

import { BreakdownChips, SessionMetric } from "@/components/control-plane-display";
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
import type {
  ExecutionPlaneCountMap,
  OrchestratorControlPassRecord,
} from "@/lib/types";

type SelectedControlPassCardProps = {
  selectedPass: OrchestratorControlPassRecord | null;
  toStringValue: (value: unknown, fallback?: string) => string;
  toNumber: (value: unknown, fallback?: number) => number;
  onOpenSession: (sessionId: string) => void;
};

export function SelectedControlPassCard({
  selectedPass,
  toStringValue,
  toNumber,
  onOpenSession,
}: SelectedControlPassCardProps) {
  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
          Selected Control Pass
        </CardTitle>
        <CardDescription className="text-[13px] text-[#787774]">
          Inspect the pass currently selected from recent history or session-linked passes.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedPass ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Select a control pass to inspect applied steps and final state.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                    {selectedPass.id}
                  </p>
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedPass.status)}`}
                  >
                    {selectedPass.status}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                  >
                    {selectedPass.profile}
                  </Badge>
                </div>
                <p className="mt-2 text-[13px] text-[#6b6b6b]">
                  Session {selectedPass.orchestrator_session_id} ·{" "}
                  {selectedPass.actor || "unknown actor"}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                onClick={() => {
                  onOpenSession(selectedPass.orchestrator_session_id);
                }}
              >
                Open session
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <SessionMetric
                label="Final State"
                value={toStringValue(selectedPass.summary.final_state, "unknown")}
                detail={toStringValue(selectedPass.summary.stopped_reason, "No stop reason")}
              />
              <SessionMetric
                label="Applied"
                value={String(toNumber(selectedPass.summary.applied, selectedPass.applied.length))}
                detail={`${toNumber(selectedPass.summary.errors, selectedPass.errors.length)} error step(s)`}
              />
              <SessionMetric
                label="Control Transition"
                value={`${toStringValue(selectedPass.control_before.state, "unknown")} -> ${toStringValue(selectedPass.control_after.state, "unknown")}`}
                detail={`${selectedPass.session_status_before || "unknown"} -> ${selectedPass.session_status_after || "unknown"} session status`}
              />
              <SessionMetric
                label="Coverage"
                value={`${selectedPass.project_ids.length} project${selectedPass.project_ids.length === 1 ? "" : "s"}`}
                detail={selectedPass.initiative_id || "No initiative mapping"}
              />
            </div>

            <BreakdownChips
              label="Recommendation Kinds"
              values={selectedPass.recommendation_kinds.reduce<ExecutionPlaneCountMap>((acc, kind) => {
                acc[kind] = (acc[kind] || 0) + 1;
                return acc;
              }, {})}
              emptyText="No recommendation kinds recorded."
            />

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Applied Steps
              </p>
              {selectedPass.applied.length === 0 ? (
                <p className="mt-3 text-[13px] text-[#9b9a97]">No applied steps recorded.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  {selectedPass.applied.map((step, index) => (
                    <div
                      key={`${selectedPass.id}-applied-${index}`}
                      className="rounded-xl border border-[#ecebe8] bg-white p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[13px] font-semibold text-[#37352f]">
                          {toStringValue(step.title, toStringValue(step.recommendation_kind, "step"))}
                        </p>
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(step.status, "ok"))}`}
                        >
                          {toStringValue(step.status, "ok")}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[12px] text-[#787774]">
                        {toStringValue(step.operation_type, "operation")}
                        {toStringValue(step.operation_mode)
                          ? ` · ${toStringValue(step.operation_mode)}`
                          : ""}
                      </p>
                      <p className="mt-2 text-[12px] text-[#9b9a97]">
                        {toStringValue(step.control_state_before, "unknown")}
                        {" -> "}
                        {toStringValue(step.control_state_after, "unknown")}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Errors
              </p>
              {selectedPass.errors.length === 0 ? (
                <p className="mt-3 text-[13px] text-[#9b9a97]">No errors recorded for this pass.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  {selectedPass.errors.map((error, index) => (
                    <div
                      key={`${selectedPass.id}-error-${index}`}
                      className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] p-3"
                    >
                      <p className="text-[13px] font-semibold text-[#93370d]">
                        {toStringValue(
                          error.title,
                          toStringValue(error.recommendation_kind, "error")
                        )}
                      </p>
                      <p className="mt-2 text-[12px] text-[#93370d]">
                        {toStringValue(error.error, "Unknown control-pass error")}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
