"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { requestProjectRuntimeControl } from "@/lib/api";
import type {
  ControlRequestMessage,
  ControlResponseMessage,
  ProjectRuntimeControlExchangeRecord,
  ProjectRuntimeControlRequestResult,
  ProjectSummary,
} from "@/lib/types";

const DEFAULT_HISTORY_LIMIT = 6;
const PENDING_PHASES = new Set(["queued", "acknowledged"]);

type ControlRequestInput = ControlRequestMessage["request"];

type UseProjectRuntimeControlClientArgs = {
  projects: ProjectSummary[];
  historyLimit?: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function nowIso(): string {
  return new Date().toISOString();
}

function buildRequestId(projectId: string): string {
  const random =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}_${Math.random().toString(16).slice(2)}`;
  return `runtime_${projectId}_${random.replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

function requestSubtype(request: unknown): string {
  if (!isRecord(request)) return "unknown";
  return stringValue(request.subtype) || "unknown";
}

function parseControlRequestMessage(value: unknown): ControlRequestMessage | null {
  if (!isRecord(value) || value.type !== "control_request") return null;
  if (!isRecord(value.request)) return null;
  const requestId = stringValue(value.request_id);
  if (!requestId) return null;
  const subtype = requestSubtype(value.request);
  return {
    type: "control_request",
    request_id: requestId,
    request: {
      ...value.request,
      subtype,
    },
    session_id: stringValue(value.session_id) || null,
  };
}

function parseControlResponseMessage(value: unknown): ControlResponseMessage | null {
  if (!isRecord(value) || value.type !== "control_response" || !isRecord(value.response)) {
    return null;
  }
  const subtype = stringValue(value.response.subtype);
  const requestId = stringValue(value.response.request_id);
  if (!requestId || (subtype !== "success" && subtype !== "error")) {
    return null;
  }
  if (subtype === "error") {
    return {
      type: "control_response",
      response: {
        subtype: "error",
        request_id: requestId,
        error: stringValue(value.response.error) || "Runtime control request failed.",
      },
      session_id: stringValue(value.session_id) || null,
    };
  }
  return {
    type: "control_response",
    response: {
      subtype: "success",
      request_id: requestId,
      response: isRecord(value.response.response) ? value.response.response : {},
    },
    session_id: stringValue(value.session_id) || null,
  };
}

function pruneRecords(
  records: Record<string, ProjectRuntimeControlExchangeRecord>,
  historyLimit: number
): Record<string, ProjectRuntimeControlExchangeRecord> {
  const grouped = new Map<string, ProjectRuntimeControlExchangeRecord[]>();
  for (const record of Object.values(records)) {
    const group = grouped.get(record.projectId) ?? [];
    group.push(record);
    grouped.set(record.projectId, group);
  }

  const next: Record<string, ProjectRuntimeControlExchangeRecord> = {};
  for (const group of grouped.values()) {
    group.sort((left, right) => {
      const updatedDelta = Date.parse(right.updatedAt) - Date.parse(left.updatedAt);
      if (updatedDelta !== 0) return updatedDelta;
      return right.requestId.localeCompare(left.requestId);
    });
    let resolvedCount = 0;
    for (const record of group) {
      const isPending = PENDING_PHASES.has(record.phase);
      if (isPending || resolvedCount < historyLimit) {
        next[record.requestId] = record;
        if (!isPending) {
          resolvedCount += 1;
        }
      }
    }
  }
  return next;
}

export function useProjectRuntimeControlClient({
  projects,
  historyLimit = DEFAULT_HISTORY_LIMIT,
}: UseProjectRuntimeControlClientArgs) {
  const [recordsById, setRecordsById] = useState<Record<string, ProjectRuntimeControlExchangeRecord>>({});

  const projectMap = useMemo(() => {
    const map = new Map<string, ProjectSummary>();
    for (const project of projects) {
      map.set(project.id, project);
    }
    return map;
  }, [projects]);

  const sessionProjectMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const project of projects) {
      const runtimeSessionId = stringValue(project.runtime_session_id);
      if (runtimeSessionId) {
        map.set(runtimeSessionId, project.id);
      }
    }
    return map;
  }, [projects]);

  const mutateRecords = useCallback(
    (
      updater: (
        current: Record<string, ProjectRuntimeControlExchangeRecord>
      ) => Record<string, ProjectRuntimeControlExchangeRecord>
    ) => {
      setRecordsById((current) => {
        const updated = updater(current);
        return pruneRecords(updated, historyLimit);
      });
    },
    [historyLimit]
  );

  useEffect(() => {
    mutateRecords((current) => {
      let changed = false;
      const next = { ...current };
      const timestamp = nowIso();
      for (const [requestId, record] of Object.entries(current)) {
        if (!PENDING_PHASES.has(record.phase)) continue;
        const project = projectMap.get(record.projectId);
        const activeSessionId = stringValue(project?.runtime_session_id);
        const controlAvailable = Boolean(project?.runtime_control_available);
        if (activeSessionId && activeSessionId === record.runtimeSessionId && controlAvailable) {
          continue;
        }
        next[requestId] = {
          ...record,
          phase: "stale",
          updatedAt: timestamp,
          errorMessage: record.errorMessage || "Runtime session changed before a response arrived.",
        };
        changed = true;
      }
      return changed ? next : current;
    });
  }, [mutateRecords, projectMap]);

  const handleSSEEvent = useCallback(
    (event: string, data: unknown) => {
      if (event !== "control_request" && event !== "control_response") {
        return;
      }

      if (event === "control_request") {
        const message = parseControlRequestMessage(data);
        if (!message) return;
        mutateRecords((current) => {
          const existing = current[message.request_id];
          const runtimeSessionId = stringValue(message.session_id);
          const projectId = existing?.projectId || sessionProjectMap.get(runtimeSessionId);
          if (!projectId) return current;
          const timestamp = nowIso();
          return {
            ...current,
            [message.request_id]: {
              requestId: message.request_id,
              projectId,
              runtimeSessionId: runtimeSessionId || existing?.runtimeSessionId || "",
              subtype: requestSubtype(message.request),
              phase:
                existing?.phase === "success" || existing?.phase === "error"
                  ? existing.phase
                  : "acknowledged",
              source: existing?.source ?? "external",
              queuedAt: existing?.queuedAt ?? timestamp,
              updatedAt: timestamp,
              request: message,
              response: existing?.response ?? null,
              errorMessage: existing?.errorMessage ?? null,
            },
          };
        });
        return;
      }

      const message = parseControlResponseMessage(data);
      if (!message) return;
      mutateRecords((current) => {
        const requestId = message.response.request_id;
        const existing = current[requestId];
        const runtimeSessionId = stringValue(message.session_id) || existing?.runtimeSessionId || "";
        const projectId = existing?.projectId || sessionProjectMap.get(runtimeSessionId);
        if (!projectId) return current;
        const timestamp = nowIso();
        return {
          ...current,
          [requestId]: {
            requestId,
            projectId,
            runtimeSessionId,
            subtype: existing?.subtype || "unknown",
            phase: message.response.subtype === "error" ? "error" : "success",
            source: existing?.source ?? "external",
            queuedAt: existing?.queuedAt ?? timestamp,
            updatedAt: timestamp,
            request: existing?.request ?? null,
            response: message.response,
            errorMessage:
              message.response.subtype === "error"
                ? message.response.error
                : null,
          },
        };
      });
    },
    [mutateRecords, sessionProjectMap]
  );

  const requestControl = useCallback(
    async (
      projectId: string,
      request: ControlRequestInput,
      options?: { requestId?: string }
    ): Promise<ProjectRuntimeControlRequestResult> => {
      const project = projectMap.get(projectId);
      if (!project) {
        throw new Error(`Project ${projectId} is not currently loaded in the dashboard.`);
      }
      if (!project.runtime_control_available || !stringValue(project.runtime_session_id)) {
        throw new Error(`Project ${project.name} does not currently expose runtime control.`);
      }

      const requestId = stringValue(options?.requestId) || buildRequestId(projectId);
      const timestamp = nowIso();
      const optimisticRequest: ControlRequestMessage = {
        type: "control_request",
        request_id: requestId,
        request: {
          ...request,
          subtype: requestSubtype(request),
        },
        session_id: stringValue(project.runtime_session_id) || null,
      };

      mutateRecords((current) => ({
        ...current,
        [requestId]: {
          requestId,
          projectId,
          runtimeSessionId: stringValue(project.runtime_session_id),
          subtype: optimisticRequest.request.subtype,
          phase: "queued",
          source: "local",
          queuedAt: timestamp,
          updatedAt: timestamp,
          request: optimisticRequest,
          response: null,
          errorMessage: null,
        },
      }));

      try {
        const result = await requestProjectRuntimeControl(projectId, {
          requestId,
          request: optimisticRequest.request,
        });
        mutateRecords((current) => {
          const existing = current[requestId];
          if (!existing) return current;
          return {
            ...current,
            [requestId]: {
              ...existing,
              runtimeSessionId: result.runtime_session_id || existing.runtimeSessionId,
              request: result.request,
              updatedAt: nowIso(),
            },
          };
        });
        return result;
      } catch (error) {
        mutateRecords((current) => {
          const existing = current[requestId];
          if (!existing) return current;
          return {
            ...current,
            [requestId]: {
              ...existing,
              phase: "error",
              updatedAt: nowIso(),
              errorMessage:
                error instanceof Error ? error.message : "Failed to queue runtime control request.",
            },
          };
        });
        throw error;
      }
    },
    [mutateRecords, projectMap]
  );

  const requestInitialize = useCallback(
    (projectId: string, payload?: Omit<ControlRequestInput, "subtype">) =>
      requestControl(projectId, { ...(payload || {}), subtype: "initialize" }),
    [requestControl]
  );

  const requestContextUsage = useCallback(
    (projectId: string) => requestControl(projectId, { subtype: "get_context_usage" }),
    [requestControl]
  );

  const requestInterrupt = useCallback(
    (projectId: string) => requestControl(projectId, { subtype: "interrupt" }),
    [requestControl]
  );

  const requestMcpStatus = useCallback(
    (projectId: string) => requestControl(projectId, { subtype: "mcp_status" }),
    [requestControl]
  );

  const requestReloadPlugins = useCallback(
    (projectId: string) => requestControl(projectId, { subtype: "reload_plugins" }),
    [requestControl]
  );

  const requestSetModel = useCallback(
    (projectId: string, model: string | null) =>
      requestControl(projectId, { subtype: "set_model", model: model ?? null }),
    [requestControl]
  );

  const requestSetPermissionMode = useCallback(
    (projectId: string, mode: string, ultraplan?: boolean) =>
      requestControl(projectId, {
        subtype: "set_permission_mode",
        mode,
        ...(typeof ultraplan === "boolean" ? { ultraplan } : {}),
      }),
    [requestControl]
  );

  const records = useMemo(
    () =>
      Object.values(recordsById).sort((left, right) => {
        const updatedDelta = Date.parse(right.updatedAt) - Date.parse(left.updatedAt);
        if (updatedDelta !== 0) return updatedDelta;
        return right.requestId.localeCompare(left.requestId);
      }),
    [recordsById]
  );

  const recordsByProject = useMemo(() => {
    const grouped: Record<string, ProjectRuntimeControlExchangeRecord[]> = {};
    for (const record of records) {
      if (!grouped[record.projectId]) {
        grouped[record.projectId] = [];
      }
      grouped[record.projectId].push(record);
    }
    return grouped;
  }, [records]);

  const getLatestRequest = useCallback(
    (projectId: string, subtype?: string): ProjectRuntimeControlExchangeRecord | null => {
      const projectRecords = recordsByProject[projectId] || [];
      if (!subtype) {
        return projectRecords[0] ?? null;
      }
      return projectRecords.find((record) => record.subtype === subtype) ?? null;
    },
    [recordsByProject]
  );

  const isPending = useCallback(
    (projectId: string, subtype?: string): boolean => {
      const latest = getLatestRequest(projectId, subtype);
      return latest ? PENDING_PHASES.has(latest.phase) : false;
    },
    [getLatestRequest]
  );

  const getLatestResponse = useCallback(
    (projectId: string, subtype?: string) => getLatestRequest(projectId, subtype)?.response ?? null,
    [getLatestRequest]
  );

  return useMemo(
    () => ({
      records,
      recordsByProject,
      handleSSEEvent,
      requestControl,
      requestInitialize,
      requestContextUsage,
      requestInterrupt,
      requestMcpStatus,
      requestReloadPlugins,
      requestSetModel,
      requestSetPermissionMode,
      getLatestRequest,
      getLatestResponse,
      isPending,
    }),
    [
      getLatestRequest,
      getLatestResponse,
      handleSSEEvent,
      isPending,
      records,
      recordsByProject,
      requestContextUsage,
      requestControl,
      requestInitialize,
      requestInterrupt,
      requestMcpStatus,
      requestReloadPlugins,
      requestSetModel,
      requestSetPermissionMode,
    ]
  );
}
