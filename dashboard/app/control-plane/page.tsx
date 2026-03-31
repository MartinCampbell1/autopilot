"use client";

import { Suspense, useEffect, useMemo } from "react";
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

function ControlPlanePageInner({
  initialSelection,
  pathname,
  searchParamsString,
}: ControlPlanePageInnerProps) {
  const router = useRouter();
  const {
    loading,
    health,
    visibleProjects,
    selectedSessionId,
    selectedAgentId,
    selectedRunId,
    selectedPassId,
    headerSectionProps,
    mainSectionsProps,
  } = useControlPlanePageController(initialSelection);

  useEffect(() => {
    const current = searchParamsString;
    const next = new URLSearchParams(current);

    if (selectedSessionId) next.set("session", selectedSessionId);
    else next.delete("session");

    if (selectedAgentId) next.set("agent", selectedAgentId);
    else next.delete("agent");

    if (selectedRunId) next.set("run", selectedRunId);
    else next.delete("run");

    if (selectedPassId) next.set("pass", selectedPassId);
    else next.delete("pass");

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
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsString = searchParams.toString();
  const initialSelection = useMemo<ControlPlaneViewSelection>(
    () => ({
      sessionId: searchParams.get("session"),
      agentId: searchParams.get("agent"),
      runId: searchParams.get("run"),
      passId: searchParams.get("pass"),
    }),
    [searchParams]
  );
  const selectionKey = useMemo(
    () =>
      [
        initialSelection.sessionId || "",
        initialSelection.agentId || "",
        initialSelection.runId || "",
        initialSelection.passId || "",
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
