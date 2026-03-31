"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { ExecutionPlaneCountMap } from "@/lib/types";

export type RelationshipTone = "run" | "outcome" | "approval" | "issue" | "event" | "agent";

export type RelationshipStripItem = {
  key: string;
  label: string;
  tone: RelationshipTone;
  active?: boolean;
  onClick?: () => void;
};

function countEntries(values: ExecutionPlaneCountMap | undefined): [string, number][] {
  return Object.entries(values ?? {}).sort((a, b) => b[1] - a[1]);
}

function relationshipToneClass(tone: RelationshipTone): string {
  switch (tone) {
    case "run":
      return "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]";
    case "outcome":
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f] hover:bg-[#f3f3f1]";
    case "approval":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690] hover:bg-[#e3f2f8]";
    case "issue":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700] hover:bg-[#fff0d9]";
    case "event":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f] hover:bg-[#e4f3e8]";
    case "agent":
      return "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]";
  }
}

export function FilterChip({
  label,
  active,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  count?: number;
  onClick: () => void;
}) {
  return (
    <Button
      size="sm"
      variant="outline"
      className={`h-8 rounded-full px-3 text-[11px] ${
        active
          ? "border-[#1a1a1a] bg-[#1a1a1a] text-white hover:bg-[#333]"
          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
      }`}
      onClick={onClick}
    >
      {label}
      {typeof count === "number" ? ` · ${count}` : ""}
    </Button>
  );
}

export function RelationshipStrip({
  label,
  items,
}: {
  label: string;
  items: RelationshipStripItem[];
}) {
  const visibleItems = items.filter((item) => item.label);
  if (visibleItems.length === 0) return null;

  return (
    <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
        {label}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {visibleItems.map((item) =>
          item.onClick ? (
            <Button
              key={item.key}
              size="sm"
              variant="outline"
              className={`h-7 rounded-full px-2.5 text-[11px] ${
                item.active
                  ? "border-[#1a1a1a] bg-[#1a1a1a] text-white hover:bg-[#333]"
                  : relationshipToneClass(item.tone)
              }`}
              onClick={item.onClick}
            >
              {item.label}
            </Button>
          ) : (
            <Badge
              key={item.key}
              variant="outline"
              className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                item.active
                  ? "border-[#1a1a1a] bg-[#1a1a1a] text-white"
                  : relationshipToneClass(item.tone)
                      .replace(" hover:bg-[#f7f7f5]", "")
                      .replace(" hover:bg-[#f3f3f1]", "")
                      .replace(" hover:bg-[#e3f2f8]", "")
                      .replace(" hover:bg-[#fff0d9]", "")
                      .replace(" hover:bg-[#e4f3e8]", "")
              }`}
            >
              {item.label}
            </Badge>
          )
        )}
      </div>
    </div>
  );
}

export function BreakdownChips({
  label,
  values,
  emptyText,
}: {
  label: string;
  values: ExecutionPlaneCountMap | undefined;
  emptyText: string;
}) {
  const items = countEntries(values);

  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">{label}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-[13px] text-[#9b9a97]">{emptyText}</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {items.map(([key, value]) => (
            <Badge
              key={`${label}-${key}`}
              variant="outline"
              className="gap-1 rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[12px] font-medium text-[#37352f]"
            >
              <span>{key}</span>
              <span className="text-[#9b9a97]">{value}</span>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

export function SummaryStat({
  eyebrow,
  value,
  detail,
}: {
  eyebrow: string;
  value: string;
  detail: string;
}) {
  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader className="gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">{eyebrow}</p>
        <CardTitle className="text-[28px] font-semibold tracking-[-0.04em] text-[#37352f]">
          {value}
        </CardTitle>
        <CardDescription className="text-[13px] text-[#6b6b6b]">{detail}</CardDescription>
      </CardHeader>
    </Card>
  );
}

export function SessionMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-[#ecebe8] bg-white px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">{label}</p>
      <p className="mt-1 text-[16px] font-semibold text-[#37352f]">{value}</p>
      <p className="mt-1 text-[12px] text-[#787774]">{detail}</p>
    </div>
  );
}
