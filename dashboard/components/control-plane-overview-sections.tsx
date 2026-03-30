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
import { sessionStatusClass } from "@/lib/control-plane-ui";
import type {
  OrchestratorControlPassSummary,
  OrchestratorSessionRecord,
  OrchestratorSessionSummary,
} from "@/lib/types";

type ControlPlaneOverviewSectionsProps = {
  controlSummary: OrchestratorControlPassSummary;
  recentSessions: OrchestratorSessionRecord[];
  totalSessionCount: number;
  selectedSessionId: string;
  onSelectSession: (sessionId: string) => void;
  sessionSummary: OrchestratorSessionSummary;
};

export function ControlPlaneOverviewSections({
  controlSummary,
  recentSessions,
  totalSessionCount,
  selectedSessionId,
  onSelectSession,
  sessionSummary,
}: ControlPlaneOverviewSectionsProps) {
  return (
    <>
      <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <CardHeader>
          <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Control Mix
          </CardTitle>
          <CardDescription className="text-[13px] text-[#787774]">
            Top profile, final-state, and ownership slices from persisted orchestration passes.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <BreakdownChips
            label="Profiles"
            values={controlSummary.by_profile}
            emptyText="No profiles recorded."
          />
          <BreakdownChips
            label="Final States"
            values={controlSummary.by_final_state}
            emptyText="No final states recorded."
          />
          <BreakdownChips
            label="Orchestrators"
            values={controlSummary.by_orchestrator}
            emptyText="No orchestrator labels recorded."
          />
        </CardContent>
      </Card>

      <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <CardHeader>
          <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Recent Sessions
          </CardTitle>
          <CardDescription className="text-[13px] text-[#787774]">
            External FounderOS orchestration sessions, now selectable for direct control.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentSessions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-6 text-[13px] text-[#9b9a97]">
              {totalSessionCount
                ? "No orchestrator sessions match the current history search."
                : "No orchestrator sessions recorded yet."}
            </div>
          ) : (
            <div className="space-y-3">
              {recentSessions.map((session) => {
                const selected = selectedSessionId === session.id;

                return (
                  <div
                    key={session.id}
                    className={`rounded-2xl border p-4 ${
                      selected
                        ? "border-[#d3e5ef] bg-[#f7fbfd] shadow-[0_1px_2px_rgba(42,102,144,0.08)]"
                        : "border-[#ecebe8] bg-[#fbfbf9]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-[14px] font-semibold text-[#37352f]">
                            {session.title || session.id}
                          </p>
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${sessionStatusClass(session.status)}`}
                          >
                            {session.status}
                          </Badge>
                        </div>
                        <p className="mt-2 text-[12px] text-[#787774]">
                          {session.orchestrator || "unknown orchestrator"}
                          {" · "}
                          {session.actor || "unknown actor"}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-mono text-[11px] text-[#9b9a97]">{session.id}</p>
                        <Button
                          size="sm"
                          variant={selected ? "default" : "outline"}
                          className={`mt-2 h-8 rounded-lg text-[12px] ${
                            selected
                              ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                              : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                          }`}
                          onClick={() => {
                            onSelectSession(session.id);
                          }}
                        >
                          {selected ? "Selected" : "Open control"}
                        </Button>
                      </div>
                    </div>

                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <SessionMetric
                        label="Scope"
                        value={`${session.project_ids.length} project${session.project_ids.length === 1 ? "" : "s"}`}
                        detail={session.initiative_id || "No initiative mapping"}
                      />
                      <SessionMetric
                        label="Linked Objects"
                        value={`${session.linked_control_pass_ids.length} passes`}
                        detail={`${session.linked_run_ids.length} runs · ${session.linked_issue_ids.length} issues`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <CardHeader>
          <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Session Overview
          </CardTitle>
          <CardDescription className="text-[13px] text-[#787774]">
            Aggregate session lifecycle and actor coverage for the external orchestrator layer.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <BreakdownChips
            label="Session Status"
            values={sessionSummary.by_status}
            emptyText="No session statuses recorded."
          />
          <BreakdownChips
            label="Actors"
            values={sessionSummary.by_actor}
            emptyText="No actors recorded."
          />
          <BreakdownChips
            label="Orchestrators"
            values={sessionSummary.by_orchestrator}
            emptyText="No orchestrators recorded."
          />
        </CardContent>
      </Card>
    </>
  );
}
