"use client";

import { Suspense, useCallback, useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ControlPlaneLayout } from "@/components/control-plane-layout";
import { ControlPlaneLoadingShell } from "@/components/control-plane-loading-shell";
import { useControlPlanePageController } from "@/lib/use-control-plane-page-controller";
import type { ControlPlaneViewSelection } from "@/lib/use-control-plane-view-state";

type ControlPlanePageInnerProps = {
  initialSelection: ControlPlaneViewSelection;
  pathname: string;
  searchParamsString: string;
};

function parseResultIndex(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function parseSessionContextKind(
  value: string | null
): ControlPlaneViewSelection["sessionContextKind"] {
  if (
    value === "approval" ||
    value === "issue" ||
    value === "event" ||
    value === "tool_permission_runtime"
  ) {
    return value;
  }
  return null;
}

function ControlPlanePageInner({
  initialSelection,
  pathname,
  searchParamsString,
}: ControlPlanePageInnerProps) {
  const router = useRouter();
  const buildControlPlaneUrl = useCallback(
    (selection: ControlPlaneViewSelection) => {
      const next = new URLSearchParams(searchParamsString);

      if (selection.sessionId) next.set("session", selection.sessionId);
      else next.delete("session");

      if (selection.agentId) next.set("agent", selection.agentId);
      else next.delete("agent");

      if (selection.runId) next.set("run", selection.runId);
      else next.delete("run");

      if (selection.runId && typeof selection.resultIndex === "number" && selection.resultIndex >= 0) {
        next.set("result", String(selection.resultIndex));
      } else {
        next.delete("result");
      }

      if (selection.passId) next.set("pass", selection.passId);
      else next.delete("pass");

      if (selection.sessionContextKind) next.set("context", selection.sessionContextKind);
      else next.delete("context");

      if (selection.approvalId) next.set("approval", selection.approvalId);
      else next.delete("approval");

      if (selection.issueId) next.set("issue", selection.issueId);
      else next.delete("issue");

      if (selection.toolPermissionRuntimeId) {
        next.set("tool_permission_runtime", selection.toolPermissionRuntimeId);
      } else {
        next.delete("tool_permission_runtime");
      }

      if (selection.eventKey) next.set("event", selection.eventKey);
      else next.delete("event");

      const nextQuery = next.toString();
      const relativeUrl = nextQuery ? `${pathname}?${nextQuery}` : pathname;
      if (typeof window === "undefined") return relativeUrl;
      return new URL(relativeUrl, window.location.origin).toString();
    },
    [pathname, searchParamsString]
  );
  const {
    loading,
    health,
    visibleProjects,
    selectedSessionId,
    selectedAgentId,
    selectedRunId,
    selectedRunResultIndex,
    selectedPassId,
    selectedSessionApprovalId,
    selectedSessionIssueId,
    selectedSessionToolPermissionRuntimeId,
    selectedSessionEventKey,
    selectedSessionContextKind,
    headerSectionProps,
    mainSectionsProps,
  } = useControlPlanePageController(initialSelection, buildControlPlaneUrl);

  useEffect(() => {
    const current = searchParamsString;
    const next = new URLSearchParams(current);

    if (selectedSessionId) next.set("session", selectedSessionId);
    else next.delete("session");

    if (selectedAgentId) next.set("agent", selectedAgentId);
    else next.delete("agent");

    if (selectedRunId) next.set("run", selectedRunId);
    else next.delete("run");

    if (selectedRunId && typeof selectedRunResultIndex === "number" && selectedRunResultIndex >= 0) {
      next.set("result", String(selectedRunResultIndex));
    } else {
      next.delete("result");
    }

    if (selectedPassId) next.set("pass", selectedPassId);
    else next.delete("pass");

    if (selectedSessionContextKind) next.set("context", selectedSessionContextKind);
    else next.delete("context");

    if (selectedSessionApprovalId) next.set("approval", selectedSessionApprovalId);
    else next.delete("approval");

    if (selectedSessionIssueId) next.set("issue", selectedSessionIssueId);
    else next.delete("issue");

    if (selectedSessionToolPermissionRuntimeId) {
      next.set("tool_permission_runtime", selectedSessionToolPermissionRuntimeId);
    } else {
      next.delete("tool_permission_runtime");
    }

    if (selectedSessionEventKey) next.set("event", selectedSessionEventKey);
    else next.delete("event");

    const nextQuery = next.toString();
    if (nextQuery === current) return;
    router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
  }, [
    pathname,
    router,
    searchParamsString,
    selectedAgentId,
    selectedPassId,
    selectedRunId,
    selectedRunResultIndex,
    selectedSessionApprovalId,
    selectedSessionContextKind,
    selectedSessionEventKey,
    selectedSessionIssueId,
    selectedSessionToolPermissionRuntimeId,
    selectedSessionId,
  ]);

  if (loading || !headerSectionProps || !mainSectionsProps) {
    return <ControlPlaneLoadingShell health={health} visibleProjects={visibleProjects} />;
  }

  return (
    <ControlPlaneLayout
      health={health}
      visibleProjects={visibleProjects}
      headerSectionProps={headerSectionProps}
      mainSectionsProps={mainSectionsProps}
    />
  );
}

function ControlPlanePageContent() {
  const pathname = usePathname() ?? "";
  const searchParams = useSearchParams();
  const resolvedSearchParams = useMemo(
    () => searchParams ?? new URLSearchParams(),
    [searchParams]
  );
  const searchParamsString = resolvedSearchParams.toString();
  const initialSelection = useMemo<ControlPlaneViewSelection>(
    () => ({
      sessionId: resolvedSearchParams.get("session") ?? null,
      agentId: resolvedSearchParams.get("agent") ?? null,
      runId: resolvedSearchParams.get("run") ?? null,
      resultIndex: parseResultIndex(resolvedSearchParams.get("result") ?? null),
      passId: resolvedSearchParams.get("pass") ?? null,
      sessionContextKind: parseSessionContextKind(resolvedSearchParams.get("context") ?? null),
      approvalId: resolvedSearchParams.get("approval") ?? null,
      issueId: resolvedSearchParams.get("issue") ?? null,
      toolPermissionRuntimeId: resolvedSearchParams.get("tool_permission_runtime") ?? null,
      eventKey: resolvedSearchParams.get("event") ?? null,
    }),
    [resolvedSearchParams]
  );
  const selectionKey = useMemo(
    () =>
      [
        initialSelection.sessionId || "",
        initialSelection.agentId || "",
        initialSelection.runId || "",
        typeof initialSelection.resultIndex === "number" ? String(initialSelection.resultIndex) : "",
        initialSelection.passId || "",
        initialSelection.sessionContextKind || "",
        initialSelection.approvalId || "",
        initialSelection.issueId || "",
        initialSelection.toolPermissionRuntimeId || "",
        initialSelection.eventKey || "",
      ].join("|"),
    [initialSelection]
  );

  return (
    <ControlPlanePageInner
      key={selectionKey}
      initialSelection={initialSelection}
      pathname={pathname}
      searchParamsString={searchParamsString}
    />
  );
}

export default function ControlPlanePage() {
  return (
    <Suspense fallback={<ControlPlaneLoadingShell health={null} visibleProjects={[]} />}>
      <ControlPlanePageContent />
    </Suspense>
  );
}
