"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchExecutionPlaneAgentActionRuns,
  fetchExecutionPlaneProject,
} from "@/lib/api";
import {
  buildProjectRuntimeHandoffSummary,
  type ProjectRuntimeHandoffSummary,
} from "@/lib/story-runtime-handoffs";
import type { ProjectSummary } from "@/lib/types";

export type ProjectRuntimeHandoffSignals = Record<string, ProjectRuntimeHandoffSummary>;
export type ProjectRuntimeHandoffSignalsResult = {
  signals: ProjectRuntimeHandoffSignals;
  refresh: () => void;
};

export function useProjectRuntimeHandoffSignals(
  projects: ProjectSummary[]
): ProjectRuntimeHandoffSignalsResult {
  const [signals, setSignals] = useState<ProjectRuntimeHandoffSignals>({});
  const [revision, setRevision] = useState(0);
  const projectSignalKey = useMemo(
    () =>
      projects
        .map(
          (project) =>
            `${project.id}:${project.status}:${project.current_story_id ?? ""}:${project.last_activity_at ?? ""}`
        )
        .join("|"),
    [projects]
  );
  const refresh = useCallback(() => {
    setRevision((current) => current + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const projectIds = projects.map((project) => project.id);
    const loadPromise = projects.length
      ? Promise.all(
          projects.map(async (project) => {
            const [projectDetail, runsPayload] = await Promise.all([
              fetchExecutionPlaneProject(project.id),
              fetchExecutionPlaneAgentActionRuns({ projectId: project.id }),
            ]);
            return [
              project.id,
              buildProjectRuntimeHandoffSummary(projectDetail, runsPayload.runs || []),
            ] as const;
          })
        )
      : Promise.resolve([] as ReadonlyArray<readonly [string, ProjectRuntimeHandoffSummary]>);

    void loadPromise
      .then((entries) => {
        if (cancelled) return;
        setSignals(Object.fromEntries(entries));
      })
      .catch(() => {
        if (cancelled) return;
        setSignals((current) => {
          const nextSignals = { ...current };
          projectIds.forEach((projectId) => {
            if (!nextSignals[projectId]) return;
            delete nextSignals[projectId];
          });
          return nextSignals;
        });
      });

    return () => {
      cancelled = true;
    };
  }, [projectSignalKey, projects, revision]);

  return { signals, refresh };
}
