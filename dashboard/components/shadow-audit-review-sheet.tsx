"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { fetchExecutionPlaneShadowAudit } from "@/lib/api";
import type {
  ExecutionArtifactRecord,
  ExecutionShadowAuditDetail,
  ExecutionShadowAuditRecord,
} from "@/lib/types";

type ShadowAuditReviewSheetProps = {
  audit: ExecutionShadowAuditRecord;
  busyActionKey: string;
  formatTimestamp: (value?: string | null) => string;
  onResolveShadowAudit?: (audit: ExecutionShadowAuditRecord) => void;
  queueState?: {
    currentIndex: number;
    totalCount: number;
    onSelectNext?: () => void;
    onSelectPrevious?: () => void;
  };
  initialOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  hideTrigger?: boolean;
  onBeforeOpen?: () => void;
  triggerLabel?: string;
  triggerClassName?: string;
};

function shadowAuditStatusClass(status: string): string {
  switch (status) {
    case "open":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "resolved":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
  }
}

function artifactToneClass(kind: "audit" | "blocked"): string {
  return kind === "audit"
    ? "border-[#d3e5ef] bg-[#f7fbfd]"
    : "border-[#f4e0c4] bg-[#fff9ef]";
}

function sourceLabel(audit: ExecutionShadowAuditRecord): string {
  const sourceName = (audit.source_name || "").trim();
  if (sourceName) return sourceName;
  const sourceKind = (audit.source_kind || "").trim();
  if (!sourceKind) return "shadow audit";
  return sourceKind.replaceAll("_", " ");
}

function ArtifactPanel({
  artifact,
  title,
  tone,
}: {
  artifact: ExecutionArtifactRecord | null | undefined;
  title: string;
  tone: "audit" | "blocked";
}) {
  return (
    <div className={`rounded-xl border p-4 ${artifactToneClass(tone)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            {title}
          </p>
          <p className="mt-2 text-[12px] text-[#6b6b6b]">
            {artifact
              ? artifact.preview || "Artifact content is available below."
              : "Artifact is not available for this review payload."}
          </p>
        </div>
        {artifact ? (
          <div className="flex flex-wrap gap-2">
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              {artifact.content_bytes} bytes
            </Badge>
            {artifact.truncated ? (
              <Badge
                variant="outline"
                className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
              >
                truncated
              </Badge>
            ) : null}
          </div>
        ) : null}
      </div>
      {artifact?.source_path ? (
        <p className="mt-3 font-mono text-[11px] text-[#9b9a97]">{artifact.source_path}</p>
      ) : null}
      {artifact ? (
        <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
          {artifact.content || "[empty]"}
        </pre>
      ) : null}
    </div>
  );
}

export function ShadowAuditReviewSheet({
  audit,
  busyActionKey,
  formatTimestamp,
  onResolveShadowAudit,
  queueState,
  initialOpen = false,
  open: controlledOpen,
  onOpenChange,
  hideTrigger = false,
  onBeforeOpen,
  triggerLabel = "Inspect review",
  triggerClassName = "h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]",
}: ShadowAuditReviewSheetProps) {
  const [internalOpen, setInternalOpen] = useState(initialOpen);
  const [detail, setDetail] = useState<ExecutionShadowAuditDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const open = controlledOpen ?? internalOpen;
  const detailMatchesAudit =
    detail !== null && detail.id === audit.id && detail.updated_at === audit.updated_at;
  const effectiveDetail = detailMatchesAudit ? detail : audit;
  const findings = useMemo(
    () => (effectiveDetail.findings || []).filter((item) => String(item).trim().length > 0),
    [effectiveDetail]
  );
  const queueTotalCount = Math.max(queueState?.totalCount ?? 0, 0);
  const queuePosition = queueState ? Math.min(queueState.currentIndex + 1, queueTotalCount) : 0;
  const queueRemainingCount = queueState ? Math.max(queueTotalCount - queuePosition, 0) : 0;
  const hasPreviousAudit = Boolean(queueState && queueState.currentIndex > 0);
  const hasNextAudit = Boolean(queueState && queuePosition < queueTotalCount);
  const resolveLabel = queueState
    ? hasNextAudit
      ? "Resolve and review next"
      : "Resolve and close queue"
    : "Resolve and release handoff";

  function loadDetail(auditId: string) {
    setLoading(true);
    setError("");
    void fetchExecutionPlaneShadowAudit(auditId)
      .then((payload) => {
        setDetail(payload);
      })
      .catch((fetchError) => {
        setError(
          fetchError instanceof Error
            ? fetchError.message
            : "Failed to load shadow-audit review detail."
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }

  function handleOpenChange(nextOpen: boolean) {
    if (nextOpen) {
      onBeforeOpen?.();
    }
    setInternalOpen(nextOpen);
    onOpenChange?.(nextOpen);
    if (!nextOpen) return;
    if (loading || detailMatchesAudit) return;
    loadDetail(audit.id);
  }

  useEffect(() => {
    if (!open || loading || detailMatchesAudit) return;
    const timeoutId = window.setTimeout(() => {
      loadDetail(audit.id);
    }, 0);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [audit.id, audit.updated_at, detailMatchesAudit, loading, open]);

  return (
    <>
      {!hideTrigger ? (
        <Button
          size="sm"
          variant="outline"
          className={triggerClassName}
          onClick={() => {
            handleOpenChange(true);
          }}
        >
          {triggerLabel}
        </Button>
      ) : null}
      <Sheet open={open} onOpenChange={handleOpenChange}>
        <SheetContent
          side="right"
          className="w-full border-l border-[#ecebe8] bg-white p-0 sm:max-w-3xl"
        >
          <SheetHeader className="border-b border-[#ecebe8] bg-[#fbfbf9]">
            <div className="flex flex-wrap items-start justify-between gap-3 pr-10">
              <div>
                <SheetTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                  Shadow Audit Review
                </SheetTitle>
                <SheetDescription className="mt-1 text-[13px] text-[#787774]">
                  Review the quarantine rationale and blocked artifact before releasing downstream handoff.
                </SheetDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge
                  variant="outline"
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${shadowAuditStatusClass(effectiveDetail.status)}`}
                >
                  {effectiveDetail.status}
                </Badge>
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {sourceLabel(effectiveDetail)}
                </Badge>
              </div>
            </div>
          </SheetHeader>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            <div className="space-y-4">
              <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-[11px] text-[#37352f]">{effectiveDetail.id}</p>
                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                      {effectiveDetail.summary ||
                        "Quarantined handoff requires explicit operator review before release."}
                    </p>
                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                      created {formatTimestamp(effectiveDetail.created_at)}
                      {effectiveDetail.updated_at
                        ? ` · updated ${formatTimestamp(effectiveDetail.updated_at)}`
                        : ""}
                    </p>
                  </div>
                  <div className="grid gap-2 text-right text-[12px] text-[#9b9a97]">
                    <span>action {effectiveDetail.action || "quarantine"}</span>
                    {effectiveDetail.blocked_artifact_owner_id ? (
                      <span>
                        blocked {effectiveDetail.blocked_artifact_owner_kind || "artifact"}{" "}
                        {effectiveDetail.blocked_artifact_owner_id}
                      </span>
                    ) : null}
                  </div>
                </div>
                {(findings.length > 0 || effectiveDetail.runtime_agent_ids.length > 0) && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {findings.map((finding) => (
                      <Badge
                        key={`${effectiveDetail.id}-${finding}`}
                        variant="outline"
                        className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                      >
                        {finding}
                      </Badge>
                    ))}
                    {effectiveDetail.runtime_agent_ids.map((runtimeAgentId) => (
                      <Badge
                        key={`${effectiveDetail.id}-${runtimeAgentId}`}
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        {runtimeAgentId}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {queueState && queueTotalCount > 0 ? (
                <div className="rounded-xl border border-[#ecebe8] bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                        Review Queue
                      </p>
                      <p className="mt-2 text-[13px] text-[#37352f]">
                        Audit {queuePosition} of {queueTotalCount}
                      </p>
                      <p className="mt-1 text-[12px] text-[#9b9a97]">
                        {queueRemainingCount > 0
                          ? `${queueRemainingCount} audit${queueRemainingCount === 1 ? "" : "s"} remaining after this review.`
                          : "This is the last open audit in the current queue."}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                        disabled={!hasPreviousAudit || loading || Boolean(busyActionKey)}
                        onClick={() => {
                          queueState.onSelectPrevious?.();
                        }}
                      >
                        Previous audit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                        disabled={!hasNextAudit || loading || Boolean(busyActionKey)}
                        onClick={() => {
                          queueState.onSelectNext?.();
                        }}
                      >
                        Next audit
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}

              {loading ? (
                <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-4 py-6 text-[13px] text-[#9b9a97]">
                  Loading shadow-audit review detail...
                </div>
              ) : null}

              {error ? (
                <div className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] px-4 py-3 text-[13px] text-[#93370d]">
                  {error}
                </div>
              ) : null}

              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                  disabled={loading}
                  onClick={() => {
                    loadDetail(audit.id);
                  }}
                >
                  {loading ? "Refreshing..." : "Refresh detail"}
                </Button>
              </div>

              <ArtifactPanel
                artifact={detailMatchesAudit ? detail.audit_artifact : null}
                title="Audit Artifact"
                tone="audit"
              />
              <ArtifactPanel
                artifact={detailMatchesAudit ? detail.blocked_artifact : null}
                title="Blocked Artifact"
                tone="blocked"
              />
            </div>
          </div>

          <SheetFooter className="border-t border-[#ecebe8] bg-[#fbfbf9]">
            <div className="flex flex-wrap justify-end gap-2">
              {onResolveShadowAudit && audit.open ? (
              <Button
                className="h-9 rounded-lg bg-[#1a1a1a] text-[12px] text-white hover:bg-[#333]"
                disabled={Boolean(busyActionKey)}
                onClick={() => {
                  void Promise.resolve(onResolveShadowAudit(audit)).catch(() => {});
                }}
              >
                  {busyActionKey === `shadow-audit-resolve:${audit.id}`
                    ? "Resolving..."
                    : resolveLabel}
                </Button>
              ) : null}
              <Button
                variant="outline"
                className="h-9 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                onClick={() => {
                  handleOpenChange(false);
                }}
              >
                Close review
              </Button>
            </div>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  );
}
