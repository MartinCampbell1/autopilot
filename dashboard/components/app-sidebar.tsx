"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { ShadowAuditReviewSheet } from "@/components/shadow-audit-review-sheet";
import { Button } from "@/components/ui/button";
import { resolveExecutionPlaneShadowAudit } from "@/lib/api";
import {
  summarizeProjectRuntimeHandoffSignals,
  type ProjectRuntimeHandoffSummary,
} from "@/lib/story-runtime-handoffs";
import { compareShadowAuditsByRecency } from "@/lib/shadow-audit-queue";
import { cn } from "@/lib/utils";
import type { AccountHealth, ProjectSummary } from "@/lib/types";

const NAV_ITEMS = [
  {
    label: "Projects",
    href: "/",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    label: "New Project",
    href: "/intake",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5v14M5 12h14" />
      </svg>
    ),
  },
  {
    label: "Accounts",
    href: "/accounts",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    label: "Control Plane",
    href: "/control-plane",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 12h16" />
        <path d="M12 4v16" />
        <circle cx="12" cy="12" r="8" />
      </svg>
    ),
  },
  {
    label: "Settings",
    href: "/settings",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 .6 1.65 1.65 0 0 0-.33 1.82v.08a2 2 0 0 1-1.64 1.1 2 2 0 0 1-1.64-1.1v-.08a1.65 1.65 0 0 0-.33-1.82 1.65 1.65 0 0 0-1-.6 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-.6-1 1.65 1.65 0 0 0-1.82-.33h-.08a2 2 0 0 1-1.1-1.64 2 2 0 0 1 1.1-1.64h.08a1.65 1.65 0 0 0 1.82-.33 1.65 1.65 0 0 0 .6-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-.6 1.65 1.65 0 0 0 .33-1.82V2.1a2 2 0 0 1 1.64-1.1 2 2 0 0 1 1.64 1.1v.08a1.65 1.65 0 0 0 .33 1.82 1.65 1.65 0 0 0 1 .6 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.24.27.48.59.6 1 .15.51.15 1.1 0 1.6-.12.41-.36.73-.6 1Z" />
      </svg>
    ),
  },
];

const STATUS_DOT: Record<ProjectSummary["status"], string> = {
  idle: "bg-[#9b9a97]",
  running: "bg-[#2a6690]",
  paused: "bg-[#d9730d]",
  completed: "bg-[#2b6e3f]",
  failed: "bg-[#93370d]",
};

interface AppSidebarProps {
  health: AccountHealth | null;
  projects?: ProjectSummary[];
  activeProjectId?: string | null;
  projectRuntimeHandoffSignals?: Record<string, ProjectRuntimeHandoffSummary>;
  onRefreshProjectRuntimeHandoffSignals?: () => void;
}

export function AppSidebar({
  health,
  projects = [],
  activeProjectId,
  projectRuntimeHandoffSignals = {},
  onRefreshProjectRuntimeHandoffSignals,
}: AppSidebarProps) {
  const pathname = usePathname() ?? "";
  const [busyActionKey, setBusyActionKey] = useState("");
  const [resolveError, setResolveError] = useState("");
  const [queueOpen, setQueueOpen] = useState(false);
  const [activeQueueAuditId, setActiveQueueAuditId] = useState("");
  const quarantineSummary = useMemo(
    () => summarizeProjectRuntimeHandoffSignals(projectRuntimeHandoffSignals),
    [projectRuntimeHandoffSignals]
  );
  const quarantinedProjects = useMemo(
    () =>
      projects
        .map((project) => ({
          project,
          runtimeSignal: projectRuntimeHandoffSignals[project.id],
        }))
        .filter(
          (entry): entry is {
            project: ProjectSummary;
            runtimeSignal: ProjectRuntimeHandoffSummary;
          } => Boolean(entry.runtimeSignal?.openShadowAuditCount)
        )
        .sort((left, right) => {
          const auditDelta =
            right.runtimeSignal.openShadowAuditCount - left.runtimeSignal.openShadowAuditCount;
          if (auditDelta !== 0) return auditDelta;
          const blockedDelta =
            right.runtimeSignal.blockedStoryCount - left.runtimeSignal.blockedStoryCount;
          if (blockedDelta !== 0) return blockedDelta;
          return Date.parse(right.project.last_activity_at || "") - Date.parse(left.project.last_activity_at || "");
        }),
    [projectRuntimeHandoffSignals, projects]
  );
  const visibleQuarantineProjects = quarantinedProjects.slice(0, 4);
  const hiddenQuarantineCount = Math.max(0, quarantinedProjects.length - visibleQuarantineProjects.length);
  const queueAudits = useMemo(
    () =>
      quarantinedProjects.flatMap(({ runtimeSignal }) =>
        runtimeSignal.openShadowAudits.map((audit) => ({
          audit,
          runtimeSignal,
        }))
      )
      .sort((left, right) => compareShadowAuditsByRecency(left.audit, right.audit)),
    [quarantinedProjects]
  );
  const activeQueueAudit = useMemo(
    () =>
      queueAudits.find((entry) => entry.audit.id === activeQueueAuditId)?.audit
      || queueAudits[0]?.audit
      || null,
    [activeQueueAuditId, queueAudits]
  );
  const activeQueueAuditIndex = useMemo(
    () =>
      activeQueueAudit
        ? queueAudits.findIndex((entry) => entry.audit.id === activeQueueAudit.id)
        : -1,
    [activeQueueAudit, queueAudits]
  );
  const formatTimestamp = useCallback((value?: string | null) => {
    if (!value) return "No timestamp";
    return new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  }, []);
  const handleResolveQueuedShadowAudit = useCallback(
    (audit: ProjectRuntimeHandoffSummary["primaryShadowAudit"]) => {
      if (!audit) return;
      const actionKey = `shadow-audit-resolve:${audit.id}`;
      const currentIndex = queueAudits.findIndex((entry) => entry.audit.id === audit.id);
      const nextAuditId = queueAudits[currentIndex + 1]?.audit.id || "";
      setBusyActionKey(actionKey);
      setResolveError("");
      void resolveExecutionPlaneShadowAudit(audit.id, {
        actor: "dashboard-sidebar-queue",
      })
        .then(() => {
          onRefreshProjectRuntimeHandoffSignals?.();
          if (nextAuditId) {
            setActiveQueueAuditId(nextAuditId);
            setQueueOpen(true);
          } else {
            setActiveQueueAuditId("");
            setQueueOpen(false);
          }
        })
        .catch((error) => {
          setResolveError(
            error instanceof Error
              ? error.message
              : "Failed to resolve shadow-audit quarantine."
          );
        })
        .finally(() => {
          setBusyActionKey("");
        });
    },
    [onRefreshProjectRuntimeHandoffSignals, queueAudits]
  );
  const handleSelectNextQueueAudit = useCallback(() => {
    if (activeQueueAuditIndex < 0) return;
    const nextAuditId = queueAudits[activeQueueAuditIndex + 1]?.audit.id;
    if (!nextAuditId) return;
    setResolveError("");
    setActiveQueueAuditId(nextAuditId);
  }, [activeQueueAuditIndex, queueAudits]);
  const handleSelectPreviousQueueAudit = useCallback(() => {
    if (activeQueueAuditIndex <= 0) return;
    const previousAuditId = queueAudits[activeQueueAuditIndex - 1]?.audit.id;
    if (!previousAuditId) return;
    setResolveError("");
    setActiveQueueAuditId(previousAuditId);
  }, [activeQueueAuditIndex, queueAudits]);

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-[260px] flex-col border-r border-[#e3e2e0] bg-[#f7f7f5]">
      <div className="flex h-[52px] items-center gap-2.5 border-b border-[#ecebe8] px-4">
        <div className="flex h-[28px] w-[28px] items-center justify-center rounded-md bg-[#37352f]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <span className="text-[14px] font-semibold tracking-[-0.01em] text-[#37352f]">Autopilot</span>
        {quarantineSummary.openShadowAuditCount > 0 ? (
          <span className="ml-auto rounded-full bg-[#fff1cc] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-[#9a6700]">
            {quarantineSummary.openShadowAuditCount} audit
            {quarantineSummary.openShadowAuditCount === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>

      <nav className="border-b border-[#ecebe8] px-2 py-2">
        <div className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors",
                  isActive
                    ? "bg-[#ebebea] font-medium text-[#37352f]"
                    : "text-[#787774] hover:bg-[#ebebea]/70 hover:text-[#37352f]"
                )}
              >
                <span className={cn(isActive ? "text-[#37352f]" : "text-[#9b9a97]")}>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="min-h-0 flex-1 px-2 py-3">
        {visibleQuarantineProjects.length > 0 ? (
          <div className="mb-4 rounded-lg border border-[#f4e0c4] bg-[#fff9ef] p-2.5">
            <div className="flex items-center justify-between gap-2 px-0.5">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9a6700]">
                  Quarantine Inbox
                </p>
                <p className="mt-1 text-[11px] text-[#b27700]">
                  {quarantineSummary.blockedProjectCount} blocked project
                  {quarantineSummary.blockedProjectCount === 1 ? "" : "s"} across{" "}
                  {quarantineSummary.blockedStoryCount} stor
                  {quarantineSummary.blockedStoryCount === 1 ? "y" : "ies"}
                </p>
              </div>
              <span className="rounded-full border border-[#f4e0c4] bg-white px-2 py-0.5 text-[11px] font-semibold text-[#9a6700]">
                {quarantineSummary.openShadowAuditCount}
              </span>
            </div>
            {activeQueueAudit ? (
              <div className="mt-2 flex items-center justify-between gap-2 rounded-md border border-[#f7e4cb] bg-white/80 px-2.5 py-2">
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-[#9a6700]">Next blocked audit</p>
                  <p className="mt-0.5 line-clamp-2 text-[11px] text-[#b27700]">
                    {activeQueueAudit.summary || "Quarantined handoff requires explicit review."}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 rounded-md border-[#f4e0c4] bg-[#fff6e8] px-2 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                  onClick={() => {
                    setQueueOpen(true);
                  }}
                >
                  Review next
                </Button>
              </div>
            ) : null}
            {resolveError ? (
              <div className="mt-2 rounded-md border border-[#f4d1c8] bg-[#fff6f4] px-2.5 py-2 text-[11px] text-[#93370d]">
                {resolveError}
              </div>
            ) : null}
            {activeQueueAudit ? (
              <ShadowAuditReviewSheet
                audit={activeQueueAudit}
                open={queueOpen}
                onOpenChange={setQueueOpen}
                hideTrigger
                busyActionKey={busyActionKey}
                formatTimestamp={formatTimestamp}
                onResolveShadowAudit={handleResolveQueuedShadowAudit}
                queueState={{
                  currentIndex: Math.max(activeQueueAuditIndex, 0),
                  totalCount: queueAudits.length,
                  onSelectNext: handleSelectNextQueueAudit,
                  onSelectPrevious: handleSelectPreviousQueueAudit,
                }}
              />
            ) : null}
            <div className="mt-2 space-y-1.5">
              {visibleQuarantineProjects.map(({ project, runtimeSignal }) => {
                const quarantineHref = runtimeSignal.primaryStoryId
                  ? `/projects/${project.id}?storyId=${runtimeSignal.primaryStoryId}`
                  : `/projects/${project.id}`;
                const isActiveQuarantineTarget =
                  activeProjectId === project.id || pathname === `/projects/${project.id}`;
                return (
                  <div
                    key={`quarantine-${project.id}`}
                    className={cn(
                      "block rounded-md border px-2.5 py-2 transition-colors",
                      isActiveQuarantineTarget
                        ? "border-[#f4e0c4] bg-white"
                        : "border-[#f7e4cb] bg-white/80 hover:bg-white"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <Link href={quarantineHref} className="min-w-0 flex-1">
                        <p className="line-clamp-2 text-[12px] font-medium leading-[1.35] text-[#37352f]">
                          {project.name}
                        </p>
                      </Link>
                      <div className="flex items-center gap-1.5">
                        <span className="rounded-full bg-[#fff6e8] px-1.5 py-0.5 text-[10px] font-semibold text-[#9a6700]">
                          {runtimeSignal.openShadowAuditCount}
                        </span>
                        {runtimeSignal.primaryShadowAudit ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 rounded-md border-[#f4e0c4] bg-[#fff6e8] px-2 text-[10px] text-[#9a6700] hover:bg-[#fff0d9]"
                            onClick={() => {
                              setResolveError("");
                              setActiveQueueAuditId(runtimeSignal.primaryShadowAudit?.id || "");
                              setQueueOpen(true);
                            }}
                          >
                            Review
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    <p className="mt-1 text-[11px] text-[#9a6700]">
                      {runtimeSignal.blockedHandoffCount} blocked handoff
                      {runtimeSignal.blockedHandoffCount === 1 ? "" : "s"} ·{" "}
                      {runtimeSignal.blockedStoryCount} stor
                      {runtimeSignal.blockedStoryCount === 1 ? "y" : "ies"}
                    </p>
                  </div>
                );
              })}
              {hiddenQuarantineCount > 0 ? (
                <Link
                  href="/"
                  className="block rounded-md px-2.5 py-1.5 text-[11px] font-medium text-[#9a6700] transition-colors hover:bg-white/70"
                >
                  See {hiddenQuarantineCount} more blocked project
                  {hiddenQuarantineCount === 1 ? "" : "s"}
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
        <div className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
          Workspace
        </div>
        <div className="space-y-1 overflow-y-auto pr-1">
          {projects.length === 0 ? (
            <div className="rounded-md px-2 py-3 text-[12px] text-[#9b9a97]">
              No active projects.
            </div>
          ) : (
            projects.map((project) => {
              const isProjectActive =
                activeProjectId === project.id || pathname === `/projects/${project.id}`;
              const runtimeSignal = projectRuntimeHandoffSignals[project.id];
              const hasQuarantinedHandoff = Boolean(runtimeSignal?.openShadowAuditCount);
              const projectHref = runtimeSignal?.primaryStoryId
                ? `/projects/${project.id}?storyId=${runtimeSignal.primaryStoryId}`
                : `/projects/${project.id}`;
              return (
                <Link
                  key={project.id}
                  href={projectHref}
                  className={cn(
                    "block rounded-md border px-2.5 py-2 transition-colors",
                    isProjectActive
                      ? hasQuarantinedHandoff
                        ? "border-[#f4e0c4] bg-white shadow-[0_1px_2px_rgba(154,103,0,0.08)]"
                        : "border-[#d8d7d3] bg-white shadow-[0_1px_2px_rgba(15,15,15,0.04)]"
                      : hasQuarantinedHandoff
                        ? "border-[#f4e0c4] bg-[#fffdf8] hover:bg-[#fff7e8]"
                        : "border-transparent hover:bg-[#ebebea]/60"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="line-clamp-2 text-[12px] font-medium leading-[1.35] text-[#37352f]">
                      {project.name}
                    </p>
                    <span
                      className={cn(
                        "mt-1 inline-block h-2 w-2 shrink-0 rounded-full",
                        hasQuarantinedHandoff ? "bg-[#d9730d]" : STATUS_DOT[project.status]
                      )}
                    />
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px] text-[#9b9a97]">
                    <span>{project.stories_done}/{project.stories_total}</span>
                    <span className="capitalize">{project.status}</span>
                  </div>
                  {hasQuarantinedHandoff ? (
                    <div className="mt-1 flex items-center gap-1.5 text-[11px] text-[#9a6700]">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#d9730d]" />
                      <span>
                        {runtimeSignal.blockedStoryCount} blocked · {runtimeSignal.openShadowAuditCount} audit
                        {runtimeSignal.openShadowAuditCount === 1 ? "" : "s"}
                      </span>
                    </div>
                  ) : null}
                </Link>
              );
            })
          )}
        </div>
      </div>

      {health && (
        <div className="border-t border-[#e3e2e0] px-4 py-3">
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-[#9b9a97]">Agents</span>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-[#2ecc71]" />
              <span className="font-medium tabular-nums text-[#37352f]">
                {health.available}/{health.total}
              </span>
            </div>
          </div>
          {health.on_cooldown > 0 && (
            <div className="mt-1.5 flex items-center gap-2 text-[12px] text-[#9b9a97]">
              <span className="inline-block h-2 w-2 rounded-full bg-[#f5a623]" />
              {health.on_cooldown} on cooldown
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
