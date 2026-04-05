"use client";

import { useCallback } from "react";
import { useShadowAuditReviewQueue } from "@/lib/use-shadow-audit-review-queue";
import type { ExecutionShadowAuditRecord } from "@/lib/types";

type UseShadowAuditReviewControllerArgs = {
  audits: ExecutionShadowAuditRecord[];
  onInspectShadowAudit?: (audit: ExecutionShadowAuditRecord) => void;
  onResolveShadowAudit?: (audit: ExecutionShadowAuditRecord) => Promise<void> | void;
  singleReviewLabel?: string;
  multiReviewLabel?: string;
};

export function useShadowAuditReviewController({
  audits,
  onInspectShadowAudit,
  onResolveShadowAudit,
  singleReviewLabel = "Open review",
  multiReviewLabel = "Review queue",
}: UseShadowAuditReviewControllerArgs) {
  const {
    queueAudits,
    queueOpen,
    setQueueOpen,
    activeQueueAudit,
    activeQueueAuditIndex,
    openQueue,
    closeQueue,
    selectQueueAudit,
  } = useShadowAuditReviewQueue(audits);

  const reviewQueueLabel =
    queueAudits.length > 1 ? multiReviewLabel : singleReviewLabel;

  const openReviewQueue = useCallback(
    (auditId?: string) => {
      const nextAuditId = auditId || activeQueueAudit?.id || queueAudits[0]?.id || "";
      if (!nextAuditId) return;
      const nextAudit = queueAudits.find((audit) => audit.id === nextAuditId) || null;
      if (nextAudit) {
        onInspectShadowAudit?.(nextAudit);
      }
      openQueue(nextAuditId);
    },
    [activeQueueAudit, onInspectShadowAudit, openQueue, queueAudits]
  );

  const handleSelectNextQueuedAudit = useCallback(() => {
    const nextAuditId = queueAudits[activeQueueAuditIndex + 1]?.id;
    if (!nextAuditId) return;
    selectQueueAudit(nextAuditId);
    const nextAudit = queueAudits.find((audit) => audit.id === nextAuditId) || null;
    if (nextAudit) {
      onInspectShadowAudit?.(nextAudit);
    }
  }, [activeQueueAuditIndex, onInspectShadowAudit, queueAudits, selectQueueAudit]);

  const handleSelectPreviousQueuedAudit = useCallback(() => {
    if (activeQueueAuditIndex <= 0) return;
    const previousAuditId = queueAudits[activeQueueAuditIndex - 1]?.id;
    if (!previousAuditId) return;
    selectQueueAudit(previousAuditId);
    const previousAudit = queueAudits.find((audit) => audit.id === previousAuditId) || null;
    if (previousAudit) {
      onInspectShadowAudit?.(previousAudit);
    }
  }, [activeQueueAuditIndex, onInspectShadowAudit, queueAudits, selectQueueAudit]);

  const handleResolveQueuedShadowAudit = useCallback(
    async (audit: ExecutionShadowAuditRecord) => {
      if (!onResolveShadowAudit) return;
      const currentIndex = queueAudits.findIndex((entry) => entry.id === audit.id);
      const nextAuditId = queueAudits[currentIndex + 1]?.id || "";
      try {
        await onResolveShadowAudit(audit);
      } catch {
        return;
      }
      if (nextAuditId) {
        selectQueueAudit(nextAuditId);
        setQueueOpen(true);
        const nextAudit = queueAudits.find((entry) => entry.id === nextAuditId) || null;
        if (nextAudit) {
          onInspectShadowAudit?.(nextAudit);
        }
        return;
      }
      closeQueue();
    },
    [
      closeQueue,
      onInspectShadowAudit,
      onResolveShadowAudit,
      queueAudits,
      selectQueueAudit,
      setQueueOpen,
    ]
  );

  return {
    queueAudits,
    queueOpen,
    setQueueOpen,
    activeQueueAudit,
    activeQueueAuditIndex,
    reviewQueueLabel,
    openReviewQueue,
    handleSelectNextQueuedAudit,
    handleSelectPreviousQueuedAudit,
    handleResolveQueuedShadowAudit,
  };
}
