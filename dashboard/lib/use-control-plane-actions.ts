import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import {
  applyExecutionPlanePreviewRun,
  applyExecutionPlaneApproval,
  applyExecutionPlaneOrchestratorSessionControlPlan,
  applyExecutionPlaneOrchestratorSessionRecommendation,
  allowExecutionPlaneToolPermissionRuntime,
  approveExecutionPlaneApproval,
  denyExecutionPlaneToolPermissionRuntime,
  executeExecutionPlaneAgentAction,
  rejectExecutionPlaneApproval,
  resolveExecutionPlaneIssue,
} from "@/lib/api";
import { extractLatestRunIdFromAppliedSteps, extractRunId } from "@/lib/control-plane-data";
import type {
  AgentTimelineEntry,
  SessionLineageEntry,
  TriageInboxFeedback,
} from "@/lib/control-plane-models";
import { agentTimelineEntryKey } from "@/lib/control-plane-linking";
import {
  agentTimelinePriority,
  matchesSessionLineageFilter,
} from "@/lib/control-plane-triage";
import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
  ExecutionRuntimeAgentDetail,
  OrchestratorSessionControlProfile,
  OrchestratorSessionControlRecommendation,
  ToolPermissionRuntimeRecord,
} from "@/lib/types";

const DEFAULT_CONTROL_ACTOR = "dashboard-control-plane";

export type PendingLineageAutoAdvance = {
  filter: "attention" | "decisions";
  previousKey: string;
  previousEntry: SessionLineageEntry | null;
  previousFilter: string;
};

export type PendingAgentPriorityAutoAdvance = {
  priority: "critical" | "high";
  previousKey: string;
  previousEntry: AgentTimelineEntry | null;
};

type UseControlPlaneActionsArgs = {
  selectedSessionId: string;
  selectedAgentId: string;
  selectedAgent: ExecutionRuntimeAgentDetail | null;
  setRefreshing: Dispatch<SetStateAction<boolean>>;
  setBusyActionKey: Dispatch<SetStateAction<string>>;
  setNotice: Dispatch<SetStateAction<string>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSelectedRunResultIndex: Dispatch<SetStateAction<number>>;
  setSelectedPassId: Dispatch<SetStateAction<string>>;
  setSelectedAgent: Dispatch<SetStateAction<ExecutionRuntimeAgentDetail | null>>;
  setEntitySearch: Dispatch<SetStateAction<string>>;
  setPendingLineageAutoAdvance: Dispatch<SetStateAction<PendingLineageAutoAdvance | null>>;
  setPendingAgentPriorityAutoAdvance: Dispatch<
    SetStateAction<PendingAgentPriorityAutoAdvance | null>
  >;
  setTriageInboxFeedbackHistory: Dispatch<SetStateAction<TriageInboxFeedback[]>>;
  selectedSessionLineageEntryRef: MutableRefObject<SessionLineageEntry | null>;
  selectedAgentTimelineEntryRef: MutableRefObject<AgentTimelineEntry | null>;
  selectedTriageInboxKeyRef: MutableRefObject<string>;
  sessionLineageFilterRef: MutableRefObject<string>;
  loadOverview: () => Promise<void>;
  loadSessionDetail: (sessionId: string) => Promise<unknown>;
  loadAgentDetail: (runtimeAgentId: string) => Promise<ExecutionRuntimeAgentDetail>;
  toStringValue: (value: unknown, fallback?: string) => string;
  triageInboxFeedbackLimit?: number;
};

export function useControlPlaneActions({
  selectedSessionId,
  selectedAgentId,
  selectedAgent,
  setRefreshing,
  setBusyActionKey,
  setNotice,
  setErrorMessage,
  setSelectedRunId,
  setSelectedRunResultIndex,
  setSelectedPassId,
  setSelectedAgent,
  setEntitySearch,
  setPendingLineageAutoAdvance,
  setPendingAgentPriorityAutoAdvance,
  setTriageInboxFeedbackHistory,
  selectedSessionLineageEntryRef,
  selectedAgentTimelineEntryRef,
  selectedTriageInboxKeyRef,
  sessionLineageFilterRef,
  loadOverview,
  loadSessionDetail,
  loadAgentDetail,
  toStringValue,
  triageInboxFeedbackLimit = 5,
}: UseControlPlaneActionsArgs) {
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadOverview();
      if (selectedSessionId) {
        await loadSessionDetail(selectedSessionId);
      }
    } finally {
      setRefreshing(false);
    }
  }, [loadOverview, loadSessionDetail, selectedSessionId, setRefreshing]);

  const refreshAfterMutation = useCallback(
    async (sessionId: string) => {
      await loadOverview();
      await loadSessionDetail(sessionId);
    },
    [loadOverview, loadSessionDetail]
  );

  const refreshAfterAgentMutation = useCallback(
    async (runtimeAgentId: string) => {
      await loadOverview();
      if (selectedSessionId) {
        await loadSessionDetail(selectedSessionId);
      }
      await loadAgentDetail(runtimeAgentId).then((detail) => {
        setSelectedAgent(detail);
      });
    },
    [loadAgentDetail, loadOverview, loadSessionDetail, selectedSessionId, setSelectedAgent]
  );

  const recordTriageInboxFeedback = useCallback(
    (
      itemKey: string,
      itemLabel: string,
      message: string,
      tone: "info" | "success" = "success"
    ) => {
      if (!itemKey || !itemLabel || !message) return;
      const feedback: TriageInboxFeedback = {
        itemKey,
        itemLabel,
        message,
        tone,
        timestamp: new Date().toISOString(),
      };
      setTriageInboxFeedbackHistory((current) => {
        const deduped = current.filter(
          (entry) =>
            !(
              entry.itemKey === feedback.itemKey &&
              entry.itemLabel === feedback.itemLabel &&
              entry.message === feedback.message &&
              entry.tone === feedback.tone
            )
        );
        return [feedback, ...deduped].slice(0, triageInboxFeedbackLimit);
      });
    },
    [setTriageInboxFeedbackHistory, triageInboxFeedbackLimit]
  );

  const runDecisionAction = useCallback(
    async (
      actionKey: string,
      task: () => Promise<string>,
      options?: { autoAdvanceQueue?: boolean }
    ) => {
      if (!selectedSessionId) return;
      setBusyActionKey(actionKey);
      setNotice("");
      setErrorMessage("");
      const currentTriageInboxKey = selectedTriageInboxKeyRef.current;
      const currentLineageEntry = selectedSessionLineageEntryRef.current;
      const currentLineageFilter = sessionLineageFilterRef.current;
      const currentAgentEntry = selectedAgentTimelineEntryRef.current;
      let autoAdvanceFilter: "attention" | "decisions" | "" = "";
      let autoAdvanceAgentPriority: "critical" | "high" | "" = "";
      if (options?.autoAdvanceQueue && currentLineageEntry) {
        if (currentLineageFilter === "attention" || currentLineageFilter === "decisions") {
          autoAdvanceFilter = currentLineageFilter;
        } else if (matchesSessionLineageFilter(currentLineageEntry, "attention")) {
          autoAdvanceFilter = "attention";
        } else if (matchesSessionLineageFilter(currentLineageEntry, "decisions")) {
          autoAdvanceFilter = "decisions";
        }
      }
      if (options?.autoAdvanceQueue && currentAgentEntry) {
        const priority = agentTimelinePriority(currentAgentEntry);
        if (priority === "critical" || priority === "high") {
          autoAdvanceAgentPriority = priority;
        }
      }
      try {
        const message = await task();
        setNotice(message);
        if (currentTriageInboxKey) {
          const itemLabel =
            currentTriageInboxKey === "session-attention"
              ? "Session Attention"
              : currentTriageInboxKey === "session-decisions"
                ? "Session Decision"
                : currentTriageInboxKey === "agent-critical"
                  ? "Agent Critical"
                  : currentTriageInboxKey === "agent-high"
                    ? "Agent High"
                    : "";
          recordTriageInboxFeedback(currentTriageInboxKey, itemLabel, message, "success");
        }
        if (autoAdvanceFilter && currentLineageEntry) {
          setPendingLineageAutoAdvance({
            filter: autoAdvanceFilter,
            previousKey: currentLineageEntry.key,
            previousEntry: currentLineageEntry,
            previousFilter: currentLineageFilter || autoAdvanceFilter,
          });
        }
        if (autoAdvanceAgentPriority && currentAgentEntry) {
          setPendingAgentPriorityAutoAdvance({
            priority: autoAdvanceAgentPriority,
            previousKey: agentTimelineEntryKey(currentAgentEntry),
            previousEntry: currentAgentEntry,
          });
        }
        await refreshAfterMutation(selectedSessionId);
        if (selectedAgentId) {
          const detail = await loadAgentDetail(selectedAgentId);
          setSelectedAgent(detail);
        }
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to apply linked decision action."
        );
      } finally {
        setBusyActionKey("");
      }
    },
    [
      loadAgentDetail,
      recordTriageInboxFeedback,
      refreshAfterMutation,
      selectedAgentId,
      selectedSessionId,
      selectedAgentTimelineEntryRef,
      selectedSessionLineageEntryRef,
      selectedTriageInboxKeyRef,
      sessionLineageFilterRef,
      setBusyActionKey,
      setErrorMessage,
      setNotice,
      setPendingAgentPriorityAutoAdvance,
      setPendingLineageAutoAdvance,
      setSelectedAgent,
    ]
  );

  const applyPreviewRun = useCallback(
    async (run: ExecutionAgentActionRunRecord) => {
      if (!run.dry_run) return;
      const previewId = toStringValue(run.preview_id, run.id);
      if (!previewId) return;
      const busyKey = `preview-apply:${previewId}`;
      setBusyActionKey(busyKey);
      setNotice("");
      setErrorMessage("");

      try {
        const payload = await applyExecutionPlanePreviewRun(run, {
          actor: DEFAULT_CONTROL_ACTOR,
          reason: run.approval_required
            ? `Dashboard requested approval from preview ${previewId}`
            : `Dashboard applied preview ${previewId}`,
        });
        const appliedRunId = toStringValue(payload.run?.id);
        if (appliedRunId) {
          setSelectedRunId(appliedRunId);
          setSelectedRunResultIndex(0);
        }

        const firstApprovalId = payload.results
          .map((result) => {
            const approval =
              result && typeof result === "object" && !Array.isArray(result)
                ? (result as Record<string, unknown>).approval
                : null;
            return approval && typeof approval === "object" && !Array.isArray(approval)
              ? toStringValue((approval as Record<string, unknown>).id)
              : "";
          })
          .find(Boolean);
        if (firstApprovalId) {
          setEntitySearch(firstApprovalId);
        }

        setNotice(
          firstApprovalId
            ? `Preview ${previewId} escalated to approval ${firstApprovalId}.`
            : `Preview ${previewId} applied as run ${appliedRunId || payload.run.id}.`
        );

        if (run.orchestrator_session_id) {
          await refreshAfterMutation(run.orchestrator_session_id);
        } else {
          await loadOverview();
        }
        if (selectedAgentId && run.runtime_agent_ids.includes(selectedAgentId)) {
          const detail = await loadAgentDetail(selectedAgentId);
          setSelectedAgent(detail);
        }
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to apply selected preview.");
      } finally {
        setBusyActionKey("");
      }
    },
    [
      loadAgentDetail,
      loadOverview,
      refreshAfterMutation,
      selectedAgentId,
      setBusyActionKey,
      setEntitySearch,
      setErrorMessage,
      setNotice,
      setSelectedAgent,
      setSelectedRunId,
      setSelectedRunResultIndex,
      toStringValue,
    ]
  );

  const applyRecommendation = useCallback(
    async (recommendation: OrchestratorSessionControlRecommendation) => {
      if (!selectedSessionId) return;
      const actionKey = `recommendation:${recommendation.kind}`;
      setBusyActionKey(actionKey);
      setNotice("");
      setErrorMessage("");

      try {
        const payload = await applyExecutionPlaneOrchestratorSessionRecommendation(selectedSessionId, {
          recommendationKind: recommendation.kind,
          actor: DEFAULT_CONTROL_ACTOR,
          reason: `Dashboard applied session recommendation ${recommendation.kind}`,
        });
        const runId = extractRunId(payload.result);
        if (runId) setSelectedRunId(runId);
        setNotice(
          `${payload.recommendation.title || recommendation.kind} finished with status ${payload.status}.`
        );
        await refreshAfterMutation(selectedSessionId);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to apply session recommendation."
        );
      } finally {
        setBusyActionKey("");
      }
    },
    [
      refreshAfterMutation,
      selectedSessionId,
      setBusyActionKey,
      setErrorMessage,
      setNotice,
      setSelectedRunId,
    ]
  );

  const approveApproval = useCallback(
    async (approval: ExecutionApprovalRecord) => {
      await runDecisionAction(
        `approval-approve:${approval.id}`,
        async () => {
          const payload = await approveExecutionPlaneApproval(approval.id, {
            actor: DEFAULT_CONTROL_ACTOR,
            note: `Dashboard approved ${approval.action} for session ${selectedSessionId}`,
          });
          return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
        },
        { autoAdvanceQueue: true }
      );
    },
    [runDecisionAction, selectedSessionId]
  );

  const rejectApproval = useCallback(
    async (approval: ExecutionApprovalRecord) => {
      await runDecisionAction(
        `approval-reject:${approval.id}`,
        async () => {
          const payload = await rejectExecutionPlaneApproval(approval.id, {
            actor: DEFAULT_CONTROL_ACTOR,
            note: `Dashboard rejected ${approval.action} for session ${selectedSessionId}`,
          });
          return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
        },
        { autoAdvanceQueue: true }
      );
    },
    [runDecisionAction, selectedSessionId]
  );

  const applyApproval = useCallback(
    async (approval: ExecutionApprovalRecord) => {
      await runDecisionAction(
        `approval-apply:${approval.id}`,
        async () => {
          const payload = await applyExecutionPlaneApproval(approval.id, {
            actor: DEFAULT_CONTROL_ACTOR,
            note: `Dashboard applied ${approval.action} for session ${selectedSessionId}`,
          });
          return toStringValue(
            payload.command_result.message,
            `Approval ${payload.approval.id} applied successfully.`
          );
        },
        { autoAdvanceQueue: true }
      );
    },
    [runDecisionAction, selectedSessionId, toStringValue]
  );

  const resolveIssue = useCallback(
    async (issue: ExecutionIssueRecord) => {
      await runDecisionAction(
        `issue-resolve:${issue.id}`,
        async () => {
          const payload = await resolveExecutionPlaneIssue(issue.id, {
            actor: DEFAULT_CONTROL_ACTOR,
            note: `Dashboard resolved issue ${issue.id} for session ${selectedSessionId}`,
          });
          return `Issue ${payload.issue.id} marked ${payload.issue.status}.`;
        },
        { autoAdvanceQueue: true }
      );
    },
    [runDecisionAction, selectedSessionId]
  );

  const resolveToolPermissionRuntime = useCallback(
    async (runtime: ToolPermissionRuntimeRecord, outcome: "allow" | "deny") => {
      const actionLabel = outcome === "allow" ? "allow" : "deny";
      const runtimeAgentLabel =
        runtime.runtime_agent_ids[0] || selectedAgent?.runtime_agent_id || selectedSessionId || "session";
      await runDecisionAction(
        `tool-permission-${actionLabel}:${runtime.id}`,
        async () => {
          const payload =
            outcome === "allow"
              ? await allowExecutionPlaneToolPermissionRuntime(runtime.id, {
                  actor: DEFAULT_CONTROL_ACTOR,
                  note: `Dashboard allowed ${runtime.tool_name || runtime.id} for ${runtimeAgentLabel}`,
                  source: "user",
                })
              : await denyExecutionPlaneToolPermissionRuntime(runtime.id, {
                  actor: DEFAULT_CONTROL_ACTOR,
                  note: `Dashboard denied ${runtime.tool_name || runtime.id} for ${runtimeAgentLabel}`,
                  source: "user",
                });
          return `Tool permission ${payload.runtime.id} marked ${payload.runtime.status}.`;
        },
        { autoAdvanceQueue: true }
      );
    },
    [runDecisionAction, selectedAgent?.runtime_agent_id, selectedSessionId]
  );

  const runAgentSuggestedCommand = useCallback(
    async (command: Record<string, unknown>, mode: "execute_now" | "request_approval") => {
      if (!selectedAgent) return;
      const commandName = toStringValue(command.command);
      if (!commandName) return;
      const actionKey = `${selectedAgent.runtime_agent_id}:command:${commandName}`;
      const busyKey = `agent-command:${selectedAgent.runtime_agent_id}:${commandName}:${mode}`;
      setBusyActionKey(busyKey);
      setNotice("");
      setErrorMessage("");

      try {
        const payload = await executeExecutionPlaneAgentAction({
          actionKey,
          orchestratorSessionId: selectedSessionId,
          actor: DEFAULT_CONTROL_ACTOR,
          mode,
          reason: `Dashboard ${
            mode === "execute_now" ? "executed" : "requested approval for"
          } agent command ${commandName}`,
        });
        const runId = extractRunId(payload);
        if (runId) setSelectedRunId(runId);
        if (payload.approval?.id) {
          setEntitySearch(payload.approval.id);
        }
        setNotice(
          payload.message ||
            toStringValue(payload.command_result?.message) ||
            `Agent command ${commandName} finished with status ${payload.status}.`
        );
        await refreshAfterAgentMutation(selectedAgent.runtime_agent_id);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to execute runtime agent command."
        );
      } finally {
        setBusyActionKey("");
      }
    },
    [
      refreshAfterAgentMutation,
      selectedAgent,
      selectedSessionId,
      setBusyActionKey,
      setEntitySearch,
      setErrorMessage,
      setNotice,
      setSelectedRunId,
      toStringValue,
    ]
  );

  const applyControlPlan = useCallback(
    async (profile: OrchestratorSessionControlProfile) => {
      if (!selectedSessionId) return;
      const actionKey = `profile:${profile.name}`;
      setBusyActionKey(actionKey);
      setNotice("");
      setErrorMessage("");

      try {
        const payload = await applyExecutionPlaneOrchestratorSessionControlPlan(selectedSessionId, {
          profile: profile.name,
          actor: DEFAULT_CONTROL_ACTOR,
          reason: `Dashboard executed ${profile.name} control pass`,
        });
        const runId = extractLatestRunIdFromAppliedSteps(payload.applied);
        if (runId) setSelectedRunId(runId);
        setNotice(
          `Control profile ${payload.profile.name} recorded pass ${payload.control_pass.id} with status ${payload.status}.`
        );
        setSelectedPassId(payload.control_pass.id);
        await refreshAfterMutation(selectedSessionId);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to apply session control profile."
        );
      } finally {
        setBusyActionKey("");
      }
    },
    [
      refreshAfterMutation,
      selectedSessionId,
      setBusyActionKey,
      setErrorMessage,
      setNotice,
      setSelectedPassId,
      setSelectedRunId,
    ]
  );

  return {
    refresh,
    recordTriageInboxFeedback,
    applyRecommendation,
    approveApproval,
    rejectApproval,
    applyApproval,
    resolveIssue,
    resolveToolPermissionRuntime,
    applyPreviewRun,
    runAgentSuggestedCommand,
    applyControlPlan,
  };
}
