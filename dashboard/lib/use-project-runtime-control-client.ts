"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { requestProjectRuntimeControl } from "@/lib/api";
import type {
  ControlRequestMessage,
  ControlResponseMessage,
  ExecutionAgentActionRunRecord,
  ExecutionRuntimeAgentTaskOutputArtifact,
  ExecutionRuntimeAgentTaskRecord,
  ExecutionRuntimeAgentTaskTranscriptArtifact,
  ProjectRuntimeControlExchangeRecord,
  ProjectRuntimeControlRequestResult,
  ProjectSummary,
  ToolPermissionRuntimeListResponse,
  ToolPermissionRuntimeRecord,
} from "@/lib/types";

const DEFAULT_HISTORY_LIMIT = 6;
const PENDING_PHASES = new Set(["queued", "acknowledged"]);

type ControlRequestInput = ControlRequestMessage["request"];
type ToolPermissionRuntimeProjectState = {
  runtimeSessionId: string;
  runtimes: ToolPermissionRuntimeRecord[];
  updatedAt: string;
};
type PendingControlResponseWaiter = {
  resolve: (message: ControlResponseMessage) => void;
  reject: (error: Error) => void;
  timeoutId: ReturnType<typeof setTimeout>;
};

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

function numberValue(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
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

function toolPermissionRuntimeSort(left: ToolPermissionRuntimeRecord, right: ToolPermissionRuntimeRecord): number {
  const pendingDelta =
    Number(String(right.status || "").trim() === "pending")
    - Number(String(left.status || "").trim() === "pending");
  if (pendingDelta !== 0) return pendingDelta;
  const updatedDelta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
  if (updatedDelta !== 0) return updatedDelta;
  return right.id.localeCompare(left.id);
}

function parseToolPermissionRuntimeRecord(value: unknown): ToolPermissionRuntimeRecord | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id);
  const projectId = stringValue(value.project_id);
  if (!id || !projectId) return null;
  return {
    id,
    key: stringValue(value.key),
    project_id: projectId,
    status: stringValue(value.status),
    claim_id: stringValue(value.claim_id),
    resolution_id: stringValue(value.resolution_id),
    approval_id: stringValue(value.approval_id),
    issue_id: stringValue(value.issue_id),
    permission_sync_key: stringValue(value.permission_sync_key),
    runtime_agent_ids: Array.isArray(value.runtime_agent_ids)
      ? value.runtime_agent_ids
          .map((item) => (typeof item === "string" ? item.trim() : ""))
          .filter(Boolean)
      : [],
    winner_source: stringValue(value.winner_source),
    outcome: stringValue(value.outcome),
    message: stringValue(value.message),
    payload: isRecord(value.payload) ? value.payload : {},
    metadata: isRecord(value.metadata) ? value.metadata : {},
    settlement_attempts: Array.isArray(value.settlement_attempts)
      ? value.settlement_attempts.filter((item): item is Record<string, unknown> => isRecord(item))
      : [],
    created_at: stringValue(value.created_at),
    updated_at: stringValue(value.updated_at),
    resolved_at: stringValue(value.resolved_at) || null,
    kind: stringValue(value.kind),
    pending_stage: stringValue(value.pending_stage),
    tool_name: stringValue(value.tool_name),
    tool_use_id: stringValue(value.tool_use_id),
    resolved_behavior: stringValue(value.resolved_behavior),
    resolved_by: stringValue(value.resolved_by),
    resolved_source: stringValue(value.resolved_source),
  };
}

function parseToolPermissionRuntimeListResponse(value: unknown): ToolPermissionRuntimeListResponse | null {
  if (!isRecord(value)) return null;
  const runtimes = Array.isArray(value.runtimes)
    ? value.runtimes
        .map((item) => parseToolPermissionRuntimeRecord(item))
        .filter((item): item is ToolPermissionRuntimeRecord => item !== null)
        .sort(toolPermissionRuntimeSort)
    : [];
  const summary = isRecord(value.summary) ? value.summary : {};
  return {
    summary: {
      count: numberValue(summary.count, runtimes.length),
      pending_count: numberValue(
        summary.pending_count,
        runtimes.filter((runtime) => runtime.status === "pending").length
      ),
    },
    runtimes,
  };
}

function parseExecutionAgentActionRunRecord(value: unknown): ExecutionAgentActionRunRecord | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id);
  if (!id) return null;
  return value as unknown as ExecutionAgentActionRunRecord;
}

function parseExecutionRuntimeAgentTaskRecord(value: unknown): ExecutionRuntimeAgentTaskRecord | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id);
  const projectId = stringValue(value.project_id);
  if (!id || !projectId) return null;
  return value as unknown as ExecutionRuntimeAgentTaskRecord;
}

function parseExecutionRuntimeAgentTaskOutputArtifact(
  value: unknown
): ExecutionRuntimeAgentTaskOutputArtifact | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id);
  const taskId = stringValue(value.task_id);
  if (!id || !taskId) return null;
  return value as unknown as ExecutionRuntimeAgentTaskOutputArtifact;
}

function parseExecutionRuntimeAgentTaskTranscriptArtifact(
  value: unknown
): ExecutionRuntimeAgentTaskTranscriptArtifact | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id);
  const taskId = stringValue(value.task_id);
  if (!id || !taskId) return null;
  return value as unknown as ExecutionRuntimeAgentTaskTranscriptArtifact;
}

function extractToolPermissionRuntimeResponse(
  subtype: string,
  value: unknown
): ToolPermissionRuntimeListResponse | null {
  if (subtype === "list_tool_permission_runtimes") {
    return parseToolPermissionRuntimeListResponse(value);
  }
  if (
    subtype === "get_tool_permission_runtime"
    || subtype === "resolve_tool_permission_runtime"
  ) {
    if (!isRecord(value)) return null;
    const runtime = parseToolPermissionRuntimeRecord(value.runtime);
    if (!runtime) return null;
    return {
      summary: {
        count: 1,
        pending_count: runtime.status === "pending" ? 1 : 0,
      },
      runtimes: [runtime],
    };
  }
  return null;
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
  const [toolPermissionStateByProject, setToolPermissionStateByProject] = useState<
    Record<string, ToolPermissionRuntimeProjectState>
  >({});
  const recordsByIdRef = useRef(recordsById);
  const controlResponseWaitersRef = useRef<Map<string, PendingControlResponseWaiter>>(new Map());

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

  const applyToolPermissionResponse = useCallback(
    (
      projectId: string,
      runtimeSessionId: string,
      subtype: string,
      response: Record<string, unknown>
    ) => {
      const extracted = extractToolPermissionRuntimeResponse(subtype, response);
      if (!extracted) return;
      setToolPermissionStateByProject((current) => {
        const existing = current[projectId];
        const existingRuntimes =
          existing && existing.runtimeSessionId === runtimeSessionId ? existing.runtimes : [];
        const merged =
          subtype === "list_tool_permission_runtimes"
            ? extracted.runtimes
            : [
                ...existingRuntimes.filter(
                  (runtime) => !extracted.runtimes.some((nextRuntime) => nextRuntime.id === runtime.id)
                ),
                ...extracted.runtimes,
              ];
        return {
          ...current,
          [projectId]: {
            runtimeSessionId,
            runtimes: [...merged].sort(toolPermissionRuntimeSort),
            updatedAt: nowIso(),
          },
        };
      });
    },
    []
  );

  const settleControlResponseWaiter = useCallback((message: ControlResponseMessage) => {
    const requestId = stringValue(message.response.request_id);
    if (!requestId) return;
    const waiter = controlResponseWaitersRef.current.get(requestId);
    if (!waiter) return;
    clearTimeout(waiter.timeoutId);
    controlResponseWaitersRef.current.delete(requestId);
    waiter.resolve(message);
  }, []);

  const failControlResponseWaiter = useCallback((requestId: string, error: Error) => {
    const normalizedRequestId = stringValue(requestId);
    if (!normalizedRequestId) return;
    const waiter = controlResponseWaitersRef.current.get(normalizedRequestId);
    if (!waiter) return;
    clearTimeout(waiter.timeoutId);
    controlResponseWaitersRef.current.delete(normalizedRequestId);
    waiter.reject(error);
  }, []);

  useEffect(() => {
    recordsByIdRef.current = recordsById;
  }, [recordsById]);

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

  useEffect(() => {
    setToolPermissionStateByProject((current) => {
      let changed = false;
      const next = { ...current };
      for (const [projectId, state] of Object.entries(current)) {
        const project = projectMap.get(projectId);
        const activeSessionId = stringValue(project?.runtime_session_id);
        const controlAvailable = Boolean(project?.runtime_control_available);
        if (controlAvailable && activeSessionId && activeSessionId === state.runtimeSessionId) {
          continue;
        }
        delete next[projectId];
        changed = true;
      }
      return changed ? next : current;
    });
  }, [projectMap]);

  useEffect(
    () => () => {
      for (const [requestId, waiter] of controlResponseWaitersRef.current.entries()) {
        clearTimeout(waiter.timeoutId);
        waiter.reject(new Error("Runtime control client was disposed before a response arrived."));
        controlResponseWaitersRef.current.delete(requestId);
      }
    },
    []
  );

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
      const requestId = message.response.request_id;
      const existing = recordsByIdRef.current[requestId];
      const runtimeSessionId = stringValue(message.session_id) || existing?.runtimeSessionId || "";
      const projectId = existing?.projectId || sessionProjectMap.get(runtimeSessionId) || "";
      const subtype = existing?.subtype || "unknown";
      mutateRecords((current) => {
        const currentExisting = current[requestId];
        const currentRuntimeSessionId =
          runtimeSessionId || currentExisting?.runtimeSessionId || "";
        const currentProjectId =
          projectId || currentExisting?.projectId || sessionProjectMap.get(currentRuntimeSessionId);
        const currentSubtype = subtype || currentExisting?.subtype || "unknown";
        if (!currentProjectId) return current;
        const timestamp = nowIso();
        return {
          ...current,
          [requestId]: {
            requestId,
            projectId: currentProjectId,
            runtimeSessionId: currentRuntimeSessionId,
            subtype: currentSubtype,
            phase: message.response.subtype === "error" ? "error" : "success",
            source: currentExisting?.source ?? "external",
            queuedAt: currentExisting?.queuedAt ?? timestamp,
            updatedAt: timestamp,
            request: currentExisting?.request ?? null,
            response: message.response,
            errorMessage:
              message.response.subtype === "error"
                ? message.response.error
                : null,
          },
        };
      });
      if (projectId && message.response.subtype === "success") {
        applyToolPermissionResponse(projectId, runtimeSessionId, subtype, message.response.response);
      }
      settleControlResponseWaiter(message);
    },
    [applyToolPermissionResponse, mutateRecords, sessionProjectMap, settleControlResponseWaiter]
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
        failControlResponseWaiter(
          requestId,
          error instanceof Error ? error : new Error("Failed to queue runtime control request.")
        );
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
    [failControlResponseWaiter, mutateRecords, projectMap]
  );

  const waitForControlResponse = useCallback((requestId: string, timeoutMs = 15000) => {
    const normalizedRequestId = stringValue(requestId);
    if (!normalizedRequestId) {
      return Promise.reject(new Error("Runtime control response wait requested without a request id."));
    }
    const existing = recordsByIdRef.current[normalizedRequestId];
    if (existing?.response) {
      return Promise.resolve({
        type: "control_response" as const,
        response: existing.response,
        session_id: existing.runtimeSessionId || null,
      });
    }
    return new Promise<ControlResponseMessage>((resolve, reject) => {
      const existingWaiter = controlResponseWaitersRef.current.get(normalizedRequestId);
      if (existingWaiter) {
        clearTimeout(existingWaiter.timeoutId);
        existingWaiter.reject(new Error(`Runtime control waiter for ${normalizedRequestId} was replaced.`));
        controlResponseWaitersRef.current.delete(normalizedRequestId);
      }
      const timeoutId = setTimeout(() => {
        controlResponseWaitersRef.current.delete(normalizedRequestId);
        reject(new Error(`Runtime control request ${normalizedRequestId} timed out waiting for a response.`));
      }, timeoutMs);
      controlResponseWaitersRef.current.set(normalizedRequestId, {
        resolve,
        reject,
        timeoutId,
      });
    });
  }, []);

  const requestControlResponse = useCallback(
    async (
      projectId: string,
      request: ControlRequestInput,
      options?: { requestId?: string; timeoutMs?: number }
    ): Promise<ControlResponseMessage> => {
      const queued = await requestControl(projectId, request, options);
      return waitForControlResponse(
        queued.request.request_id,
        Math.max(options?.timeoutMs ?? 15000, 1000)
      );
    },
    [requestControl, waitForControlResponse]
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

  const requestGetRuntimeAgentActionRun = useCallback(
    async (
      projectId: string,
      runId: string,
      options?: {
        waitForAsyncSettlement?: boolean;
        runtimeAgentId?: string | null;
        waitTimeoutMs?: number;
      }
    ): Promise<ExecutionAgentActionRunRecord> => {
      const message = await requestControlResponse(
        projectId,
        {
          subtype: "get_runtime_agent_action_run",
          run_id: runId,
          wait_for_async_settlement: Boolean(options?.waitForAsyncSettlement),
          runtime_agent_id: options?.runtimeAgentId ?? null,
          wait_timeout_ms: options?.waitTimeoutMs ?? null,
        },
        { timeoutMs: options?.waitTimeoutMs }
      );
      if (message.response.subtype === "error") {
        throw new Error(message.response.error);
      }
      if (!isRecord(message.response.response)) {
        throw new Error("Runtime returned a malformed runtime-agent action run payload.");
      }
      const run = parseExecutionAgentActionRunRecord(message.response.response.run);
      if (!run) {
        throw new Error("Runtime returned a malformed runtime-agent action run payload.");
      }
      return run;
    },
    [requestControlResponse]
  );

  const requestGetRuntimeAgentTask = useCallback(
    async (
      projectId: string,
      taskId: string,
      options?: { timeoutMs?: number }
    ): Promise<ExecutionRuntimeAgentTaskRecord> => {
      const message = await requestControlResponse(
        projectId,
        {
          subtype: "get_runtime_agent_task",
          task_id: taskId,
        },
        { timeoutMs: options?.timeoutMs }
      );
      if (message.response.subtype === "error") {
        throw new Error(message.response.error);
      }
      if (!isRecord(message.response.response)) {
        throw new Error("Runtime returned a malformed runtime-agent task payload.");
      }
      const task = parseExecutionRuntimeAgentTaskRecord(message.response.response.task);
      if (!task) {
        throw new Error("Runtime returned a malformed runtime-agent task payload.");
      }
      return task;
    },
    [requestControlResponse]
  );

  const requestGetRuntimeAgentTaskOutput = useCallback(
    async (
      projectId: string,
      taskId: string,
      options?: { timeoutMs?: number }
    ): Promise<ExecutionRuntimeAgentTaskOutputArtifact> => {
      const message = await requestControlResponse(
        projectId,
        {
          subtype: "get_runtime_agent_task_output",
          task_id: taskId,
        },
        { timeoutMs: options?.timeoutMs }
      );
      if (message.response.subtype === "error") {
        throw new Error(message.response.error);
      }
      if (!isRecord(message.response.response)) {
        throw new Error("Runtime returned a malformed runtime-agent task output payload.");
      }
      const output = parseExecutionRuntimeAgentTaskOutputArtifact(message.response.response.output);
      if (!output) {
        throw new Error("Runtime returned a malformed runtime-agent task output payload.");
      }
      return output;
    },
    [requestControlResponse]
  );

  const requestGetRuntimeAgentTaskTranscript = useCallback(
    async (
      projectId: string,
      taskId: string,
      options?: { timeoutMs?: number }
    ): Promise<ExecutionRuntimeAgentTaskTranscriptArtifact> => {
      const message = await requestControlResponse(
        projectId,
        {
          subtype: "get_runtime_agent_task_transcript",
          task_id: taskId,
        },
        { timeoutMs: options?.timeoutMs }
      );
      if (message.response.subtype === "error") {
        throw new Error(message.response.error);
      }
      if (!isRecord(message.response.response)) {
        throw new Error("Runtime returned a malformed runtime-agent task transcript payload.");
      }
      const transcript = parseExecutionRuntimeAgentTaskTranscriptArtifact(
        message.response.response.transcript
      );
      if (!transcript) {
        throw new Error("Runtime returned a malformed runtime-agent task transcript payload.");
      }
      return transcript;
    },
    [requestControlResponse]
  );

  const requestListToolPermissionRuntimes = useCallback(
    async (
      projectId: string,
      filters?: {
        runtimeAgentId?: string | null;
        status?: string | null;
        pendingStage?: string | null;
        timeoutMs?: number;
      }
    ): Promise<ToolPermissionRuntimeListResponse> => {
      const message = await requestControlResponse(
        projectId,
        {
          subtype: "list_tool_permission_runtimes",
          runtime_agent_id: filters?.runtimeAgentId ?? null,
          status: filters?.status ?? null,
          pending_stage: filters?.pendingStage ?? null,
        },
        { timeoutMs: filters?.timeoutMs }
      );
      if (message.response.subtype === "error") {
        throw new Error(message.response.error);
      }
      const parsed = parseToolPermissionRuntimeListResponse(message.response.response);
      if (!parsed) {
        throw new Error("Runtime returned a malformed tool-permission runtime list.");
      }
      return parsed;
    },
    [requestControlResponse]
  );

  const requestGetToolPermissionRuntime = useCallback(
    async (
      projectId: string,
      approvalRuntimeId: string,
      options?: { timeoutMs?: number }
    ): Promise<ToolPermissionRuntimeRecord> => {
      const message = await requestControlResponse(
        projectId,
        {
          subtype: "get_tool_permission_runtime",
          approval_runtime_id: approvalRuntimeId,
        },
        { timeoutMs: options?.timeoutMs }
      );
      if (message.response.subtype === "error") {
        throw new Error(message.response.error);
      }
      const parsed = extractToolPermissionRuntimeResponse(
        "get_tool_permission_runtime",
        message.response.response
      );
      const runtime = parsed?.runtimes[0] ?? null;
      if (!runtime) {
        throw new Error("Runtime returned a malformed tool-permission runtime payload.");
      }
      return runtime;
    },
    [requestControlResponse]
  );

  const requestResolveToolPermissionRuntime = useCallback(
    async (
      projectId: string,
      approvalRuntimeId: string,
      outcome: "allow" | "deny",
      options?: {
        actor?: string | null;
        note?: string | null;
        source?: "user" | "channel";
        timeoutMs?: number;
      }
    ): Promise<ToolPermissionRuntimeRecord> => {
      const message = await requestControlResponse(
        projectId,
        {
          subtype: "resolve_tool_permission_runtime",
          approval_runtime_id: approvalRuntimeId,
          outcome,
          actor: options?.actor ?? "dashboard",
          note: options?.note ?? "",
          source: options?.source ?? "user",
        },
        { timeoutMs: options?.timeoutMs }
      );
      if (message.response.subtype === "error") {
        throw new Error(message.response.error);
      }
      const parsed = extractToolPermissionRuntimeResponse(
        "resolve_tool_permission_runtime",
        message.response.response
      );
      const runtime = parsed?.runtimes[0] ?? null;
      if (!runtime) {
        throw new Error("Runtime returned a malformed tool-permission resolution payload.");
      }
      return runtime;
    },
    [requestControlResponse]
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

  const getToolPermissionRuntimes = useCallback(
    (projectId: string, options?: { pendingOnly?: boolean }) => {
      const runtimes = toolPermissionStateByProject[projectId]?.runtimes ?? [];
      if (!options?.pendingOnly) {
        return runtimes;
      }
      return runtimes.filter((runtime) => runtime.status === "pending");
    },
    [toolPermissionStateByProject]
  );

  return useMemo(
    () => ({
      records,
      recordsByProject,
      toolPermissionRuntimesByProject: toolPermissionStateByProject,
      handleSSEEvent,
      requestControl,
      requestInitialize,
      requestContextUsage,
      requestInterrupt,
      requestMcpStatus,
      requestReloadPlugins,
      requestSetModel,
      requestSetPermissionMode,
      requestGetRuntimeAgentActionRun,
      requestGetRuntimeAgentTask,
      requestGetRuntimeAgentTaskOutput,
      requestGetRuntimeAgentTaskTranscript,
      requestListToolPermissionRuntimes,
      requestGetToolPermissionRuntime,
      requestResolveToolPermissionRuntime,
      getLatestRequest,
      getLatestResponse,
      getToolPermissionRuntimes,
      isPending,
    }),
    [
      getLatestRequest,
      getLatestResponse,
      getToolPermissionRuntimes,
      handleSSEEvent,
      isPending,
      records,
      recordsByProject,
      requestContextUsage,
      requestControl,
      requestGetRuntimeAgentActionRun,
      requestGetRuntimeAgentTask,
      requestGetRuntimeAgentTaskOutput,
      requestGetRuntimeAgentTaskTranscript,
      requestGetToolPermissionRuntime,
      requestInitialize,
      requestInterrupt,
      requestListToolPermissionRuntimes,
      requestMcpStatus,
      requestResolveToolPermissionRuntime,
      requestReloadPlugins,
      requestSetModel,
      requestSetPermissionMode,
      toolPermissionStateByProject,
    ]
  );
}
