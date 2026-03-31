import type { QueueAdvanceFocusDelta } from "@/components/queue-advance-notice";
import { asRecord, toStringValue } from "@/lib/control-plane-data";

export type OperatorVisibilityState = {
  dismissed: string[];
  snoozedUntil: Record<string, number>;
};

export type PersistedLineageQueueState<K extends string = string> = {
  dismissed?: Partial<Record<K, string[]>>;
  snoozedUntil?: Partial<Record<K, Record<string, number>>>;
};

export type PersistedAgentTimelineState = {
  dismissed?: string[];
  snoozedUntil?: Record<string, number>;
};

export type SanitizedLineageQueueState<K extends string = string> = {
  dismissed: Record<K, string[]>;
  snoozedUntil: Record<K, Record<string, number>>;
};

export function emptyVisibilityKeysRecord<K extends string>(kinds: readonly K[]): Record<K, string[]> {
  return kinds.reduce(
    (acc, kind) => {
      acc[kind] = [];
      return acc;
    },
    {} as Record<K, string[]>
  );
}

export function emptySnoozedVisibilityRecord<K extends string>(
  kinds: readonly K[]
): Record<K, Record<string, number>> {
  return kinds.reduce(
    (acc, kind) => {
      acc[kind] = {};
      return acc;
    },
    {} as Record<K, Record<string, number>>
  );
}

export function sanitizeOperatorVisibilityState(
  value:
    | {
        dismissed?: unknown;
        snoozedUntil?: unknown;
      }
    | null
    | undefined,
  now: number
): OperatorVisibilityState {
  const dismissed = Array.isArray(value?.dismissed)
    ? [...new Set(value.dismissed.filter((entry): entry is string => typeof entry === "string"))]
    : [];
  const snoozedUntil: Record<string, number> = {};
  const rawSnoozed = asRecord(value?.snoozedUntil);
  if (rawSnoozed) {
    Object.entries(rawSnoozed).forEach(([entryKey, until]) => {
      if (!entryKey) return;
      if (typeof until !== "number" || !Number.isFinite(until)) return;
      if (until <= now) return;
      snoozedUntil[entryKey] = until;
    });
  }
  return {
    dismissed,
    snoozedUntil,
  };
}

export function isOperatorVisibilityStateEmpty(state: OperatorVisibilityState): boolean {
  return state.dismissed.length === 0 && Object.keys(state.snoozedUntil).length === 0;
}

export function sanitizePersistedLineageQueueState<K extends string>(
  value: PersistedLineageQueueState<K> | null | undefined,
  now: number,
  kinds: readonly K[]
): SanitizedLineageQueueState<K> {
  const dismissed = emptyVisibilityKeysRecord(kinds);
  const snoozedUntil = emptySnoozedVisibilityRecord(kinds);

  kinds.forEach((kind) => {
    const sanitized = sanitizeOperatorVisibilityState(
      {
        dismissed: value?.dismissed?.[kind],
        snoozedUntil: value?.snoozedUntil?.[kind],
      },
      now
    );
    dismissed[kind] = sanitized.dismissed;
    snoozedUntil[kind] = sanitized.snoozedUntil;
  });

  return {
    dismissed,
    snoozedUntil,
  };
}

export function isPersistedLineageQueueStateEmpty<K extends string>(
  state: SanitizedLineageQueueState<K>,
  kinds: readonly K[]
): boolean {
  return kinds.every((kind) =>
    isOperatorVisibilityStateEmpty({
      dismissed: state.dismissed[kind],
      snoozedUntil: state.snoozedUntil[kind],
    })
  );
}

export function sanitizePersistedAgentTimelineState(
  value: PersistedAgentTimelineState | null | undefined,
  now: number
): OperatorVisibilityState {
  return sanitizeOperatorVisibilityState(value, now);
}

export function isPersistedAgentTimelineStateEmpty(state: OperatorVisibilityState): boolean {
  return isOperatorVisibilityStateEmpty(state);
}

export function buildScopedStorageKey(prefix: string, scopeId: string): string {
  return `${prefix}${scopeId}`;
}

export function sanitizeQueueAdvanceFocusDelta(
  value: QueueAdvanceFocusDelta | null | undefined
): QueueAdvanceFocusDelta | null {
  if (!value || typeof value !== "object") return null;
  const fromLabel = toStringValue(value.fromLabel);
  const toLabel = toStringValue(value.toLabel);
  const timestamp = toStringValue(value.timestamp);
  const fromCount = Number(value.fromCount);
  const toCount = Number(value.toCount);
  if (!fromLabel || !toLabel || !timestamp) return null;
  if (!Number.isFinite(fromCount) || !Number.isFinite(toCount)) return null;
  return {
    fromLabel,
    toLabel,
    fromCount,
    toCount,
    timestamp,
  };
}

export function buildQueueAdvanceFocusDelta(
  fromLabel: string,
  toLabel: string,
  fromCount: number,
  toCount: number
): QueueAdvanceFocusDelta {
  return {
    fromLabel,
    toLabel,
    fromCount,
    toCount,
    timestamp: new Date().toISOString(),
  };
}

export function readPersistedQueueAdvanceFocusDelta(storageKey: string): QueueAdvanceFocusDelta | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) return null;
  try {
    return sanitizeQueueAdvanceFocusDelta(JSON.parse(raw) as QueueAdvanceFocusDelta);
  } catch {
    return null;
  }
}

export function persistQueueAdvanceFocusDelta(
  storageKey: string,
  value: QueueAdvanceFocusDelta | null | undefined
): void {
  if (typeof window === "undefined") return;
  const sanitized = sanitizeQueueAdvanceFocusDelta(value);
  if (!sanitized) {
    window.localStorage.removeItem(storageKey);
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
}

export function visibleEntriesByOperatorVisibilityState<T>(
  entries: T[],
  getKey: (entry: T) => string,
  state: OperatorVisibilityState,
  now: number
): T[] {
  return entries.filter((entry) => {
    const entryKey = getKey(entry);
    if (!entryKey) return true;
    if (state.dismissed.includes(entryKey)) return false;
    const snoozedUntil = state.snoozedUntil[entryKey] ?? 0;
    return snoozedUntil <= now;
  });
}
