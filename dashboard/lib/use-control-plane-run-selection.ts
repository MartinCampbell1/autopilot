"use client";

import { useEffect, type Dispatch, type SetStateAction } from "react";
import type { ExecutionAgentActionRunRecord } from "@/lib/types";

type UseControlPlaneRunSelectionArgs = {
  filteredRuns: ExecutionAgentActionRunRecord[];
  linkedRuns: ExecutionAgentActionRunRecord[];
  selectedRunId: string;
  selectedRunResultIndex: number;
  preserveEmptyRunSelection: boolean;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSelectedRunResultIndex: Dispatch<SetStateAction<number>>;
};

export function useControlPlaneRunSelection({
  filteredRuns,
  linkedRuns,
  selectedRunId,
  selectedRunResultIndex,
  preserveEmptyRunSelection,
  setSelectedRunId,
  setSelectedRunResultIndex,
}: UseControlPlaneRunSelectionArgs) {
  useEffect(() => {
    if (!filteredRuns.length) {
      return;
    }
    if (!selectedRunId && preserveEmptyRunSelection) {
      return;
    }
    if (!selectedRunId || !filteredRuns.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(filteredRuns[0].id);
    }
  }, [filteredRuns, preserveEmptyRunSelection, selectedRunId, setSelectedRunId]);

  useEffect(() => {
    const currentRun = linkedRuns.find((run) => run.id === selectedRunId) ?? null;
    if (!currentRun) {
      setSelectedRunResultIndex(0);
      return;
    }
    if (selectedRunResultIndex >= currentRun.results.length) {
      setSelectedRunResultIndex(0);
    }
  }, [linkedRuns, selectedRunId, selectedRunResultIndex, setSelectedRunResultIndex]);
}
