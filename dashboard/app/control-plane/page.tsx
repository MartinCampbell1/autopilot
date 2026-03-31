"use client";

import { ControlPlaneLayout } from "@/components/control-plane-layout";
import { ControlPlaneLoadingShell } from "@/components/control-plane-loading-shell";
import { useControlPlanePageController } from "@/lib/use-control-plane-page-controller";

export default function ControlPlanePage() {
  const {
    loading,
    health,
    visibleProjects,
    headerSectionProps,
    mainSectionsProps,
  } = useControlPlanePageController();

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
