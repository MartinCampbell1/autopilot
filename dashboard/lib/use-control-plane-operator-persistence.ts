"use client";

import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import type { QueueAdvanceFocusDelta } from "@/components/queue-advance-notice";
import {
  buildScopedStorageKey,
  emptySnoozedVisibilityRecord,
  emptyVisibilityKeysRecord,
  isPersistedAgentTimelineStateEmpty,
  isPersistedLineageQueueStateEmpty,
  persistQueueAdvanceFocusDelta,
  readPersistedQueueAdvanceFocusDelta,
  sanitizePersistedAgentTimelineState,
  sanitizePersistedLineageQueueState,
  type PersistedAgentTimelineState,
  type PersistedLineageQueueState,
} from "@/lib/control-plane-operator-state";
import {
  SESSION_LINEAGE_QUEUE_KEYS,
  type LineageQueueKind,
} from "@/lib/control-plane-models";

const LINEAGE_QUEUE_STORAGE_PREFIX = "control-plane:lineage-queue:";
const AGENT_TIMELINE_STORAGE_PREFIX = "control-plane:agent-timeline:";
const SESSION_QUEUE_FOCUS_STORAGE_PREFIX = "control-plane:session-queue-focus:";
const AGENT_QUEUE_FOCUS_STORAGE_PREFIX = "control-plane:agent-queue-focus:";

type UseControlPlaneOperatorPersistenceArgs = {
  selectedSessionId: string;
  selectedAgentId: string;
  dismissedLineageQueueKeys: Record<LineageQueueKind, string[]>;
  setDismissedLineageQueueKeys: Dispatch<
    SetStateAction<Record<LineageQueueKind, string[]>>
  >;
  snoozedLineageQueueUntil: Record<LineageQueueKind, Record<string, number>>;
  setSnoozedLineageQueueUntil: Dispatch<
    SetStateAction<Record<LineageQueueKind, Record<string, number>>>
  >;
  lineageQueueNow: number;
  setLineageQueueNow: Dispatch<SetStateAction<number>>;
  sessionQueueFocusDelta: QueueAdvanceFocusDelta | null;
  setSessionQueueFocusDelta: Dispatch<SetStateAction<QueueAdvanceFocusDelta | null>>;
  dismissedAgentTimelineKeys: string[];
  setDismissedAgentTimelineKeys: Dispatch<SetStateAction<string[]>>;
  snoozedAgentTimelineUntil: Record<string, number>;
  setSnoozedAgentTimelineUntil: Dispatch<SetStateAction<Record<string, number>>>;
  agentQueueFocusDelta: QueueAdvanceFocusDelta | null;
  setAgentQueueFocusDelta: Dispatch<SetStateAction<QueueAdvanceFocusDelta | null>>;
};

export function useControlPlaneOperatorPersistence({
  selectedSessionId,
  selectedAgentId,
  dismissedLineageQueueKeys,
  setDismissedLineageQueueKeys,
  snoozedLineageQueueUntil,
  setSnoozedLineageQueueUntil,
  lineageQueueNow,
  setLineageQueueNow,
  sessionQueueFocusDelta,
  setSessionQueueFocusDelta,
  dismissedAgentTimelineKeys,
  setDismissedAgentTimelineKeys,
  snoozedAgentTimelineUntil,
  setSnoozedAgentTimelineUntil,
  agentQueueFocusDelta,
  setAgentQueueFocusDelta,
}: UseControlPlaneOperatorPersistenceArgs) {
  const hydratedAgentTimelineStorageKeyRef = useRef("");
  const hydratedLineageQueueSessionIdRef = useRef("");
  const hydratedSessionQueueFocusStorageKeyRef = useRef("");
  const hydratedAgentQueueFocusStorageKeyRef = useRef("");

  useEffect(() => {
    const interval = setInterval(() => {
      setLineageQueueNow(Date.now());
    }, 30000);
    return () => clearInterval(interval);
  }, [setLineageQueueNow]);

  useEffect(() => {
    if (!selectedSessionId) {
      setDismissedLineageQueueKeys(emptyVisibilityKeysRecord(SESSION_LINEAGE_QUEUE_KEYS));
      setSnoozedLineageQueueUntil(emptySnoozedVisibilityRecord(SESSION_LINEAGE_QUEUE_KEYS));
      hydratedLineageQueueSessionIdRef.current = "";
      return;
    }

    const now = Date.now();
    setLineageQueueNow(now);
    hydratedLineageQueueSessionIdRef.current = "";

    if (typeof window === "undefined") {
      setDismissedLineageQueueKeys(emptyVisibilityKeysRecord(SESSION_LINEAGE_QUEUE_KEYS));
      setSnoozedLineageQueueUntil(emptySnoozedVisibilityRecord(SESSION_LINEAGE_QUEUE_KEYS));
      hydratedLineageQueueSessionIdRef.current = selectedSessionId;
      return;
    }

    const storageKey = buildScopedStorageKey(LINEAGE_QUEUE_STORAGE_PREFIX, selectedSessionId);
    const raw = window.localStorage.getItem(storageKey);
    let parsed: PersistedLineageQueueState<LineageQueueKind> | null = null;
    if (raw) {
      try {
        parsed = JSON.parse(raw) as PersistedLineageQueueState<LineageQueueKind>;
      } catch {
        parsed = null;
      }
    }

    const sanitized = sanitizePersistedLineageQueueState(
      parsed,
      now,
      SESSION_LINEAGE_QUEUE_KEYS
    );
    setDismissedLineageQueueKeys(sanitized.dismissed);
    setSnoozedLineageQueueUntil(sanitized.snoozedUntil);
    hydratedLineageQueueSessionIdRef.current = selectedSessionId;

    if (isPersistedLineageQueueStateEmpty(sanitized, SESSION_LINEAGE_QUEUE_KEYS)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    selectedSessionId,
    setDismissedLineageQueueKeys,
    setLineageQueueNow,
    setSnoozedLineageQueueUntil,
  ]);

  useEffect(() => {
    if (!selectedSessionId || hydratedLineageQueueSessionIdRef.current !== selectedSessionId) {
      return;
    }
    if (typeof window === "undefined") return;

    const sanitized = sanitizePersistedLineageQueueState(
      {
        dismissed: dismissedLineageQueueKeys,
        snoozedUntil: snoozedLineageQueueUntil,
      },
      lineageQueueNow,
      SESSION_LINEAGE_QUEUE_KEYS
    );
    const storageKey = buildScopedStorageKey(LINEAGE_QUEUE_STORAGE_PREFIX, selectedSessionId);

    if (isPersistedLineageQueueStateEmpty(sanitized, SESSION_LINEAGE_QUEUE_KEYS)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    dismissedLineageQueueKeys,
    lineageQueueNow,
    selectedSessionId,
    snoozedLineageQueueUntil,
  ]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSessionQueueFocusDelta(null);
      hydratedSessionQueueFocusStorageKeyRef.current = "";
      return;
    }

    const storageKey = buildScopedStorageKey(
      SESSION_QUEUE_FOCUS_STORAGE_PREFIX,
      selectedSessionId
    );
    hydratedSessionQueueFocusStorageKeyRef.current = "";

    if (typeof window === "undefined") {
      hydratedSessionQueueFocusStorageKeyRef.current = storageKey;
      return;
    }
    const sanitized = readPersistedQueueAdvanceFocusDelta(storageKey);
    setSessionQueueFocusDelta(sanitized);
    hydratedSessionQueueFocusStorageKeyRef.current = storageKey;
    persistQueueAdvanceFocusDelta(storageKey, sanitized);
  }, [selectedSessionId, setSessionQueueFocusDelta]);

  useEffect(() => {
    if (!selectedSessionId) return;
    const storageKey = buildScopedStorageKey(
      SESSION_QUEUE_FOCUS_STORAGE_PREFIX,
      selectedSessionId
    );
    if (hydratedSessionQueueFocusStorageKeyRef.current !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;
    persistQueueAdvanceFocusDelta(storageKey, sessionQueueFocusDelta);
  }, [
    selectedSessionId,
    sessionQueueFocusDelta,
  ]);

  useEffect(() => {
    if (!selectedAgentId) {
      setDismissedAgentTimelineKeys([]);
      setSnoozedAgentTimelineUntil({});
      hydratedAgentTimelineStorageKeyRef.current = "";
      return;
    }

    const now = Date.now();
    setLineageQueueNow(now);
    hydratedAgentTimelineStorageKeyRef.current = "";

    if (typeof window === "undefined") {
      setDismissedAgentTimelineKeys([]);
      setSnoozedAgentTimelineUntil({});
      hydratedAgentTimelineStorageKeyRef.current = buildScopedStorageKey(
        AGENT_TIMELINE_STORAGE_PREFIX,
        selectedAgentId
      );
      return;
    }

    const storageKey = buildScopedStorageKey(AGENT_TIMELINE_STORAGE_PREFIX, selectedAgentId);
    const raw = window.localStorage.getItem(storageKey);
    let parsed: PersistedAgentTimelineState | null = null;
    if (raw) {
      try {
        parsed = JSON.parse(raw) as PersistedAgentTimelineState;
      } catch {
        parsed = null;
      }
    }

    const sanitized = sanitizePersistedAgentTimelineState(parsed, now);
    setDismissedAgentTimelineKeys(sanitized.dismissed);
    setSnoozedAgentTimelineUntil(sanitized.snoozedUntil);
    hydratedAgentTimelineStorageKeyRef.current = storageKey;

    if (isPersistedAgentTimelineStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    selectedAgentId,
    setDismissedAgentTimelineKeys,
    setLineageQueueNow,
    setSnoozedAgentTimelineUntil,
  ]);

  useEffect(() => {
    if (!selectedAgentId) return;
    const storageKey = buildScopedStorageKey(AGENT_TIMELINE_STORAGE_PREFIX, selectedAgentId);
    if (hydratedAgentTimelineStorageKeyRef.current !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;

    const sanitized = sanitizePersistedAgentTimelineState(
      {
        dismissed: dismissedAgentTimelineKeys,
        snoozedUntil: snoozedAgentTimelineUntil,
      },
      lineageQueueNow
    );

    if (isPersistedAgentTimelineStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    dismissedAgentTimelineKeys,
    lineageQueueNow,
    selectedAgentId,
    snoozedAgentTimelineUntil,
  ]);

  useEffect(() => {
    if (!selectedAgentId) {
      setAgentQueueFocusDelta(null);
      hydratedAgentQueueFocusStorageKeyRef.current = "";
      return;
    }

    const storageKey = buildScopedStorageKey(AGENT_QUEUE_FOCUS_STORAGE_PREFIX, selectedAgentId);
    hydratedAgentQueueFocusStorageKeyRef.current = "";

    if (typeof window === "undefined") {
      hydratedAgentQueueFocusStorageKeyRef.current = storageKey;
      return;
    }
    const sanitized = readPersistedQueueAdvanceFocusDelta(storageKey);
    setAgentQueueFocusDelta(sanitized);
    hydratedAgentQueueFocusStorageKeyRef.current = storageKey;
    persistQueueAdvanceFocusDelta(storageKey, sanitized);
  }, [selectedAgentId, setAgentQueueFocusDelta]);

  useEffect(() => {
    if (!selectedAgentId) return;
    const storageKey = buildScopedStorageKey(AGENT_QUEUE_FOCUS_STORAGE_PREFIX, selectedAgentId);
    if (hydratedAgentQueueFocusStorageKeyRef.current !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;
    persistQueueAdvanceFocusDelta(storageKey, agentQueueFocusDelta);
  }, [
    agentQueueFocusDelta,
    selectedAgentId,
  ]);
}
