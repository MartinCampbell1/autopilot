"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type {
  TriageInboxFeedback,
  TriageInboxFeedbackGroup,
  TriageInboxItem,
} from "@/lib/control-plane-models";
import { triagePriorityClass } from "@/lib/control-plane-ui";

type TriageInboxFeedbackTone = "all" | "success" | "info";

type TriageInboxSectionProps = {
  triageInboxItemCount: number;
  triageInboxItems: TriageInboxItem[];
  selectedTriageInboxItem: TriageInboxItem | null;
  syncedTriageInboxItem: TriageInboxItem | null;
  formatTimestamp: (value?: string | null) => string;
  onInspectTriageInboxItem: (item: TriageInboxItem) => void;
  onInspectAndAdvanceTriageInboxItem: (item: TriageInboxItem) => void;
  onAdvanceTriageInboxCursor: () => void;
  onSyncTriageInboxCursorToSelection: () => void;
  triageInboxFeedbackHistoryCount: number;
  triageInboxFeedbackFilter: TriageInboxFeedbackTone;
  onTriageInboxFeedbackFilterChange: (value: TriageInboxFeedbackTone) => void;
  triageInboxFeedbackCounts: Record<TriageInboxFeedbackTone, number>;
  triageInboxFeedback: TriageInboxFeedback | null;
  groupedRecentTriageInboxFeedback: TriageInboxFeedbackGroup[];
  recentTriageInboxFeedbackCount: number;
  expandedTriageInboxResultGroups: string[];
  currentTriageInboxFeedbackGroup: TriageInboxFeedbackGroup | null;
  onExpandAllTriageInboxResultGroups: () => void;
  onCollapseAllTriageInboxResultGroups: () => void;
  onOpenCurrentTriageInboxResultGroup: () => void;
  onToggleTriageInboxResultGroup: (itemKey: string) => void;
  onOpenTriageInboxHistoryGroup: (itemKey: string) => void;
  onSnoozeTriageInboxItem: (item: TriageInboxItem) => void;
  onDismissTriageInboxItem: (item: TriageInboxItem) => void;
};

export function TriageInboxSection({
  triageInboxItemCount,
  triageInboxItems,
  selectedTriageInboxItem,
  syncedTriageInboxItem,
  formatTimestamp,
  onInspectTriageInboxItem,
  onInspectAndAdvanceTriageInboxItem,
  onAdvanceTriageInboxCursor,
  onSyncTriageInboxCursorToSelection,
  triageInboxFeedbackHistoryCount,
  triageInboxFeedbackFilter,
  onTriageInboxFeedbackFilterChange,
  triageInboxFeedbackCounts,
  triageInboxFeedback,
  groupedRecentTriageInboxFeedback,
  recentTriageInboxFeedbackCount,
  expandedTriageInboxResultGroups,
  currentTriageInboxFeedbackGroup,
  onExpandAllTriageInboxResultGroups,
  onCollapseAllTriageInboxResultGroups,
  onOpenCurrentTriageInboxResultGroup,
  onToggleTriageInboxResultGroup,
  onOpenTriageInboxHistoryGroup,
  onSnoozeTriageInboxItem,
  onDismissTriageInboxItem,
}: TriageInboxSectionProps) {
  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
              Triage Inbox
            </CardTitle>
            <CardDescription className="text-[13px] text-[#787774]">
              One compact next-up strip across session lineage and runtime agent queues.
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
          >
            {triageInboxItemCount} active
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {triageInboxItemCount === 0 ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            No session or agent triage items are active in the current slice.
          </div>
        ) : (
          <div className="space-y-3">
            {selectedTriageInboxItem ? (
              <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                      Current Cursor
                    </p>
                    <p className="mt-1 text-[12px] text-[#787774]">
                      {selectedTriageInboxItem.label} · {selectedTriageInboxItem.queueDetail}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onInspectTriageInboxItem(selectedTriageInboxItem);
                      }}
                    >
                      Inspect current
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onInspectAndAdvanceTriageInboxItem(selectedTriageInboxItem);
                      }}
                      disabled={triageInboxItems.length <= 1}
                    >
                      Inspect + advance
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={onAdvanceTriageInboxCursor}
                      disabled={triageInboxItems.length <= 1}
                    >
                      Advance cursor
                    </Button>
                    {syncedTriageInboxItem &&
                    syncedTriageInboxItem.key !== selectedTriageInboxItem.key ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg border-[#d3e5ef] bg-[#eef7fb] px-2 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                        onClick={onSyncTriageInboxCursorToSelection}
                      >
                        Sync to selection
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(selectedTriageInboxItem.priority)}`}
                  >
                    {selectedTriageInboxItem.priority}
                  </Badge>
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${selectedTriageInboxItem.statusClassName}`}
                  >
                    {selectedTriageInboxItem.status}
                  </Badge>
                  {selectedTriageInboxItem.syncedWithSelection ? (
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                    >
                      Synced with selection
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-3 text-[13px] font-semibold text-[#37352f]">
                  {selectedTriageInboxItem.title}
                </p>
                <p className="mt-2 text-[12px] text-[#787774]">
                  {selectedTriageInboxItem.subtitle}
                </p>
                {triageInboxFeedbackHistoryCount ? (
                  <div className="mt-3 space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {[
                        { value: "all" as const, label: "All" },
                        { value: "success" as const, label: "Success" },
                        { value: "info" as const, label: "Info" },
                      ].map((option) => {
                        const selected = triageInboxFeedbackFilter === option.value;
                        const count = triageInboxFeedbackCounts[option.value];
                        return (
                          <Button
                            key={`triage-feedback-filter-${option.value}`}
                            size="sm"
                            variant={selected ? "default" : "outline"}
                            className={`h-7 rounded-full px-3 text-[11px] ${
                              selected
                                ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                            }`}
                            onClick={() => {
                              onTriageInboxFeedbackFilterChange(option.value);
                            }}
                          >
                            {option.label} · {count}
                          </Button>
                        );
                      })}
                    </div>
                    {triageInboxFeedback ? (
                      <div
                        className={`rounded-lg border p-3 ${
                          triageInboxFeedback.tone === "success"
                            ? "border-[#d6e9dc] bg-[#eef8f1]"
                            : "border-[#e5e5e3] bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p
                            className={`text-[11px] font-semibold uppercase tracking-[0.08em] ${
                              triageInboxFeedback.tone === "success"
                                ? "text-[#2b6e3f]"
                                : "text-[#9b9a97]"
                            }`}
                          >
                            Latest Result
                            {triageInboxFeedback.itemLabel ? ` · ${triageInboxFeedback.itemLabel}` : ""}
                          </p>
                          <p className="text-[11px] text-[#9b9a97]">
                            {formatTimestamp(triageInboxFeedback.timestamp)}
                          </p>
                        </div>
                        <p
                          className={`mt-2 text-[12px] ${
                            triageInboxFeedback.tone === "success"
                              ? "text-[#2b6e3f]"
                              : "text-[#6b6b6b]"
                          }`}
                        >
                          {triageInboxFeedback.message}
                        </p>
                        {triageInboxFeedback.itemKey !== selectedTriageInboxItem.key ? (
                          <p className="mt-2 text-[11px] text-[#9b9a97]">
                            Cursor moved after that action.
                          </p>
                        ) : null}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-[#e5e5e3] bg-[#fafaf9] p-3 text-[12px] text-[#9b9a97]">
                        No {triageInboxFeedbackFilter} triage results yet.
                      </div>
                    )}
                    {groupedRecentTriageInboxFeedback.length ? (
                      <div className="rounded-lg border border-[#ecebe8] bg-white p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Recent Results
                          </p>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {recentTriageInboxFeedbackCount}
                            </Badge>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={onExpandAllTriageInboxResultGroups}
                              disabled={
                                !groupedRecentTriageInboxFeedback.length ||
                                expandedTriageInboxResultGroups.length >=
                                  groupedRecentTriageInboxFeedback.length
                              }
                            >
                              Expand all
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={onCollapseAllTriageInboxResultGroups}
                              disabled={!expandedTriageInboxResultGroups.length}
                            >
                              Collapse all
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={onOpenCurrentTriageInboxResultGroup}
                              disabled={!currentTriageInboxFeedbackGroup}
                            >
                              Open current group
                            </Button>
                          </div>
                        </div>
                        <div className="mt-3 space-y-2">
                          {groupedRecentTriageInboxFeedback.map((group) => {
                            const expanded = expandedTriageInboxResultGroups.includes(group.itemKey);
                            return (
                              <div
                                key={`triage-feedback-group-${group.itemKey}`}
                                className="rounded-lg border border-[#ecebe8] bg-[#fbfbf9] p-2.5"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="text-[11px] font-semibold text-[#37352f]">
                                      {group.itemLabel}
                                    </p>
                                    <Badge
                                      variant="outline"
                                      className="rounded-full border-[#e5e5e3] bg-white px-2 py-0.5 text-[10px] font-medium text-[#37352f]"
                                    >
                                      {group.entries.length}
                                    </Badge>
                                    {!group.isActive ? (
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2 py-0.5 text-[10px] font-medium text-[#9b9a97]"
                                      >
                                        Not in inbox
                                      </Badge>
                                    ) : null}
                                  </div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="text-[11px] text-[#9b9a97]">
                                      {formatTimestamp(group.entries[0]?.timestamp || "")}
                                    </p>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                      onClick={() => {
                                        onToggleTriageInboxResultGroup(group.itemKey);
                                      }}
                                    >
                                      {expanded ? "Collapse" : "Expand"}
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                      onClick={() => {
                                        onOpenTriageInboxHistoryGroup(group.itemKey);
                                      }}
                                      disabled={!group.isActive}
                                    >
                                      Open in inbox
                                    </Button>
                                  </div>
                                </div>
                                {expanded ? (
                                  <div className="mt-2 space-y-2">
                                    {group.entries.map((feedback) => (
                                      <div
                                        key={`${feedback.itemKey}:${feedback.timestamp}`}
                                        className="rounded-lg border border-[#ecebe8] bg-white p-2"
                                      >
                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                          <Badge
                                            variant="outline"
                                            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                              feedback.tone === "success"
                                                ? "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]"
                                                : "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]"
                                            }`}
                                          >
                                            {feedback.tone}
                                          </Badge>
                                          <p className="text-[11px] text-[#9b9a97]">
                                            {formatTimestamp(feedback.timestamp)}
                                          </p>
                                        </div>
                                        <p className="mt-1 text-[12px] text-[#6b6b6b]">
                                          {feedback.message}
                                        </p>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="mt-2 text-[12px] text-[#9b9a97]">
                                    {group.entries.length} result
                                    {group.entries.length === 1 ? "" : "s"} hidden
                                  </p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="grid gap-3 xl:grid-cols-2 2xl:grid-cols-4">
              {triageInboxItems.map((item) => {
                const cursorSelected = selectedTriageInboxItem?.key === item.key;
                return (
                  <div
                    key={`triage-inbox-${item.key}`}
                    className={`rounded-xl border p-3 ${
                      cursorSelected
                        ? "border-[#d3e5ef] bg-[#f7fbfd]"
                        : "border-[#ecebe8] bg-[#fbfbf9]"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          {item.label}
                        </p>
                        <p className="mt-1 text-[12px] text-[#787774]">{item.queueDetail}</p>
                      </div>
                      <p className="text-[11px] text-[#9b9a97]">{formatTimestamp(item.timestamp)}</p>
                    </div>
                    <p className="mt-3 text-[13px] font-semibold text-[#37352f]">{item.title}</p>
                    <p className="mt-2 text-[12px] text-[#787774]">{item.subtitle}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(item.priority)}`}
                      >
                        {item.priority}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${item.statusClassName}`}
                      >
                        {item.status}
                      </Badge>
                      {item.syncedWithSelection ? (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                        >
                          Synced
                        </Badge>
                      ) : null}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant={cursorSelected ? "default" : "outline"}
                        className={`h-7 rounded-lg px-2 text-[11px] ${
                          cursorSelected
                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                        }`}
                        onClick={() => {
                          onInspectTriageInboxItem(item);
                        }}
                      >
                        {cursorSelected ? "Current" : "Inspect"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                        onClick={() => {
                          onInspectAndAdvanceTriageInboxItem(item);
                        }}
                        disabled={triageInboxItems.length <= 1}
                      >
                        Inspect + next
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                        onClick={() => {
                          onSnoozeTriageInboxItem(item);
                        }}
                      >
                        Snooze 15m
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                        onClick={() => {
                          onDismissTriageInboxItem(item);
                        }}
                      >
                        Dismiss
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
