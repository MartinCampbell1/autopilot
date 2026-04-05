"use client";

import type { ProjectMonitoringSnapshot } from "@/lib/types";

interface ProjectObservabilityPanelProps {
  monitoring?: ProjectMonitoringSnapshot | null;
}

function formatCurrency(value?: number) {
  return `$${Number(value || 0).toFixed(4)}`;
}

function formatTokens(value?: number) {
  return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function formatTimestamp(value?: string | null) {
  if (!value) return "No timestamp";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function sentenceCase(value?: string | null) {
  return value ? value.replaceAll("_", " ") : "Unknown";
}

export function ProjectObservabilityPanel({ monitoring }: ProjectObservabilityPanelProps) {
  if (!monitoring) {
    return (
      <section className="rounded-2xl border border-[#ecebe8] bg-white px-5 py-4">
        <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Observability</p>
        <p className="mt-2 text-[13px] text-[#787774]">No monitoring snapshot has been recorded yet.</p>
      </section>
    );
  }

  const latestRun = monitoring.latest_run ?? null;
  const comparison = monitoring.trace?.comparison || {};
  const recentRuns = monitoring.trace?.runs?.slice(-3).reverse() || [];
  const recentFailures = monitoring.trace?.recent_failures?.slice(-3).reverse() || [];
  const topStories = monitoring.cost?.top_stories?.slice(0, 3) || [];

  return (
    <section className="rounded-2xl border border-[#ecebe8] bg-white px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Observability</p>
          <h2 className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Cost, regressions, and replay signals
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
              monitoring.regressions?.cost ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"
            }`}
          >
            Cost {monitoring.regressions?.cost ? "regressed" : "stable"}
          </span>
          <span
            className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
              monitoring.regressions?.reliability ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
            }`}
          >
            Reliability {monitoring.regressions?.reliability ? "regressed" : "stable"}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Current Run</p>
            <p className="mt-2 text-[20px] font-semibold text-[#37352f]">
              {formatCurrency(monitoring.cost?.run?.estimated_cost_usd)}
            </p>
            <p className="mt-1 text-[12px] text-[#787774]">
              {formatTokens(monitoring.cost?.run?.total_tokens)} tokens
            </p>
          </div>
          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Project Total</p>
            <p className="mt-2 text-[20px] font-semibold text-[#37352f]">
              {formatCurrency(monitoring.cost?.project?.estimated_cost_usd)}
            </p>
            <p className="mt-1 text-[12px] text-[#787774]">
              {formatTokens(monitoring.cost?.project?.total_tokens)} tokens
            </p>
          </div>
          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Latest Run</p>
            <p className="mt-2 text-[16px] font-semibold text-[#37352f]">
              {sentenceCase(latestRun?.status)}
            </p>
            <p className="mt-1 text-[12px] text-[#787774]">
              {latestRun?.iteration_count || 0} iterations · {latestRun?.failure_count || 0} failures
            </p>
          </div>
        </div>

        <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Latest Comparison</p>
          <div className="mt-3 grid grid-cols-2 gap-3 text-[13px] text-[#6b6b6b]">
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Cost Delta</p>
              <p className="mt-1 font-medium text-[#37352f]">
                {formatCurrency(Number(comparison.cost_delta_usd || 0))}
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Token Delta</p>
              <p className="mt-1 font-medium text-[#37352f]">
                {formatTokens(Number(comparison.total_tokens_delta || 0))}
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Failure Delta</p>
              <p className="mt-1 font-medium text-[#37352f]">{Number(comparison.failure_delta || 0)}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Quality Delta</p>
              <p className="mt-1 font-medium text-[#37352f]">
                {Number(comparison.quality_regression_delta || 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Recent Runs</p>
          <div className="mt-3 space-y-2">
            {recentRuns.length ? (
              recentRuns.map((run) => (
                <div key={run.run_id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[13px] font-medium text-[#37352f]">{run.run_id}</p>
                    <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1 text-[11px] text-[#787774]">
                      {sentenceCase(run.status)}
                    </span>
                  </div>
                  <p className="mt-1 text-[12px] text-[#787774]">
                    {run.iteration_count || 0} iterations · {run.failure_count || 0} failures
                  </p>
                  <p className="mt-1 text-[12px] text-[#787774]">{formatTimestamp(run.finished_at || run.last_timestamp)}</p>
                </div>
              ))
            ) : (
              <p className="text-[13px] text-[#787774]">No run snapshots yet.</p>
            )}
          </div>
        </div>

        <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Top Cost Stories</p>
          <div className="mt-3 space-y-2">
            {topStories.length ? (
              topStories.map((story) => (
                <div key={`story-cost-${story.story_id}`} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                  <p className="text-[13px] font-medium text-[#37352f]">Story #{story.story_id}</p>
                  <p className="mt-1 text-[12px] text-[#787774]">
                    {formatCurrency(story.estimated_cost_usd)} · {formatTokens(story.total_tokens)} tokens
                  </p>
                </div>
              ))
            ) : (
              <p className="text-[13px] text-[#787774]">No story spend recorded yet.</p>
            )}
          </div>
        </div>

        <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Recent Failures</p>
          <div className="mt-3 space-y-2">
            {recentFailures.length ? (
              recentFailures.map((failure, index) => (
                <div key={`failure-${index}-${String(failure.timestamp || "")}`} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                  <p className="text-[13px] font-medium text-[#37352f]">{sentenceCase(String(failure.event || ""))}</p>
                  <p className="mt-1 text-[12px] text-[#787774]">{String(failure.message || "No failure detail.")}</p>
                </div>
              ))
            ) : (
              <p className="text-[13px] text-[#787774]">No recent failure signals.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
