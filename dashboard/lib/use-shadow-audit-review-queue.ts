"use client";

import { useCallback, useMemo, useState } from "react";
import { sortShadowAuditsByRecency } from "@/lib/shadow-audit-queue";
import type { ExecutionShadowAuditRecord } from "@/lib/types";

export function useShadowAuditReviewQueue(audits: ExecutionShadowAuditRecord[]) {
  const queueAudits = useMemo(() => sortShadowAuditsByRecency(audits), [audits]);
  const auditKey = useMemo(
    () =>
      queueAudits
        .map((audit) => `${audit.id}:${audit.updated_at}:${audit.status}`)
        .join("|"),
    [queueAudits]
  );
  const [queueState, setQueueState] = useState<{
    open: boolean;
    activeQueueAuditId: string;
    auditKey: string;
  }>({
    open: false,
    activeQueueAuditId: "",
    auditKey: "",
  });
  const queueOpen = queueState.open && queueState.auditKey === auditKey;
  const activeQueueAuditId =
    queueState.auditKey === auditKey ? queueState.activeQueueAuditId : "";

  const activeQueueAudit = useMemo(
    () => queueAudits.find((audit) => audit.id === activeQueueAuditId) || queueAudits[0] || null,
    [activeQueueAuditId, queueAudits]
  );
  const activeQueueAuditIndex = useMemo(
    () =>
      activeQueueAudit ? queueAudits.findIndex((audit) => audit.id === activeQueueAudit.id) : -1,
    [activeQueueAudit, queueAudits]
  );

  const setQueueOpen = useCallback(
    (open: boolean) => {
      setQueueState((current) => ({
        open,
        activeQueueAuditId:
          current.auditKey === auditKey
            ? current.activeQueueAuditId
            : queueAudits[0]?.id || "",
        auditKey,
      }));
    },
    [auditKey, queueAudits]
  );

  const openQueue = useCallback(
    (auditId?: string) => {
      setQueueState({
        open: true,
        activeQueueAuditId: auditId || queueAudits[0]?.id || "",
        auditKey,
      });
    },
    [auditKey, queueAudits]
  );

  const closeQueue = useCallback(() => {
    setQueueState({
      open: false,
      activeQueueAuditId: "",
      auditKey,
    });
  }, [auditKey]);

  const selectQueueAudit = useCallback(
    (auditId: string) => {
      if (!auditId) return;
      setQueueState((current) => ({
        open: current.open && current.auditKey === auditKey,
        activeQueueAuditId: auditId,
        auditKey,
      }));
    },
    [auditKey]
  );

  const selectNextQueueAudit = useCallback(() => {
    if (activeQueueAuditIndex < 0) return;
    const nextAuditId = queueAudits[activeQueueAuditIndex + 1]?.id;
    if (!nextAuditId) return;
    setQueueState((current) => ({
      open: current.open && current.auditKey === auditKey,
      activeQueueAuditId: nextAuditId,
      auditKey,
    }));
  }, [activeQueueAuditIndex, auditKey, queueAudits]);

  const selectPreviousQueueAudit = useCallback(() => {
    if (activeQueueAuditIndex <= 0) return;
    const previousAuditId = queueAudits[activeQueueAuditIndex - 1]?.id;
    if (!previousAuditId) return;
    setQueueState((current) => ({
      open: current.open && current.auditKey === auditKey,
      activeQueueAuditId: previousAuditId,
      auditKey,
    }));
  }, [activeQueueAuditIndex, auditKey, queueAudits]);

  return {
    queueAudits,
    queueOpen,
    setQueueOpen,
    activeQueueAuditId,
    activeQueueAudit,
    activeQueueAuditIndex,
    openQueue,
    closeQueue,
    selectQueueAudit,
    selectNextQueueAudit,
    selectPreviousQueueAudit,
  };
}
