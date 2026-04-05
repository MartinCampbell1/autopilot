"use client";

import type { ProjectCompanyShell as ProjectCompanyShellPayload, ProjectDetail } from "@/lib/types";

interface ProjectCompanyShellProps {
  project: ProjectDetail;
}

function statusTone(status: string) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "completed" || normalized === "ready" || normalized === "active" || normalized === "live") {
    return "bg-emerald-50 text-emerald-700";
  }
  if (normalized === "warning" || normalized === "queued" || normalized === "standby" || normalized === "paused") {
    return "bg-amber-50 text-amber-700";
  }
  if (normalized === "blocked" || normalized === "offline" || normalized === "missing" || normalized === "needs_secret") {
    return "bg-red-50 text-red-700";
  }
  return "bg-stone-100 text-stone-700";
}

function formatTime(value?: string | null) {
  if (!value) return "No timestamp";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function companyOrFallback(company?: ProjectCompanyShellPayload | null) {
  return company ?? {};
}

export function ProjectCompanyShell({ project }: ProjectCompanyShellProps) {
  const company = companyOrFallback(project.company);
  const goals = company.goals?.items || [];
  const routines = company.routines?.items || [];
  const channels = company.channels?.items || [];
  const secrets = company.secrets?.items || [];
  const liveEvents = company.live_events?.items || [];
  const status = company.status || {};

  return (
    <section className="rounded-2xl border border-[#ecebe8] bg-white px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Company Shell</p>
          <h2 className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Always-on goals, routines, channels, and live activity
          </h2>
          <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-[#6b6b6b]">
            This is the persistent company runtime surface for the project: structured goals,
            guarded routines, operator channels, secret readiness, and the live execution feed.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${status.always_on_ready ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
            {status.always_on_ready ? "Always-on ready" : "Always-on warming up"}
          </span>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${status.runtime_wall_enforced ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
            Runtime wall {status.runtime_wall_enforced ? "enforced" : "missing"}
          </span>
          <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-700">
            {status.goal_count || 0} goals
          </span>
          <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-700">
            {status.active_routine_count || 0} routines active
          </span>
          <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-700">
            {status.ready_channel_count || 0} channels ready
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Goals</p>
            <div className="mt-3 space-y-2">
              {goals.length ? (
                goals.map((goal) => (
                  <div key={goal.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{goal.title}</p>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusTone(goal.status)}`}>
                        {goal.status}
                      </span>
                    </div>
                    {goal.goal ? (
                      <p className="mt-1 text-[12px] text-[#6b6b6b]">{goal.goal}</p>
                    ) : null}
                    <p className="mt-2 text-[12px] text-[#787774]">
                      {goal.progress_pct || 0}% · {goal.stories_done || 0}/{goal.stories_total || 0} stories
                      {goal.current_story_title ? ` · current: ${goal.current_story_title}` : ""}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-[13px] text-[#787774]">No company goals are defined yet.</p>
              )}
            </div>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Routines</p>
            <div className="mt-3 space-y-2">
              {routines.length ? (
                routines.map((routine) => (
                  <div key={routine.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{routine.title}</p>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusTone(routine.status)}`}>
                        {routine.status}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] text-[#6b6b6b]">{routine.description}</p>
                    <p className="mt-2 text-[12px] text-[#787774]">
                      Cadence: {routine.cadence}
                      {routine.recommended_action?.label ? ` · next: ${routine.recommended_action.label}` : ""}
                    </p>
                    {routine.blocked_by?.length ? (
                      <p className="mt-1 text-[12px] text-[#a26a1b]">
                        Blockers: {routine.blocked_by.join(", ")}
                      </p>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="text-[13px] text-[#787774]">No company routines are defined yet.</p>
              )}
            </div>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Channels</p>
            <div className="mt-3 space-y-2">
              {channels.length ? (
                channels.map((channel) => (
                  <div key={channel.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{channel.name}</p>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusTone(channel.status)}`}>
                        {channel.status}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] text-[#6b6b6b]">
                      {channel.kind}
                      {channel.target ? ` · ${channel.target}` : ""}
                    </p>
                    <p className="mt-2 text-[12px] text-[#787774]">
                      {channel.approval_capable ? "Approval-capable" : "Notification/coordination only"}
                      {channel.message_count ? ` · ${channel.message_count} messages` : ""}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-[13px] text-[#787774]">No channels are configured yet.</p>
              )}
            </div>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Secret Readiness</p>
            <div className="mt-3 space-y-2">
              {secrets.length ? (
                secrets.map((secret) => (
                  <div key={secret.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{secret.channel_name}</p>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusTone(secret.status)}`}>
                        {secret.status}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] text-[#6b6b6b]">
                      Required: {secret.required_keys.join(", ") || "None"}
                    </p>
                    {secret.missing_keys.length ? (
                      <p className="mt-1 text-[12px] text-[#a26a1b]">
                        Missing: {secret.missing_keys.join(", ")}
                      </p>
                    ) : (
                      <p className="mt-1 text-[12px] text-[#787774]">All required secret references resolve.</p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-[13px] text-[#787774]">
                  No channel-specific secret groups are configured for this project.
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Live Activity</p>
            <div className="mt-3 space-y-2">
              {liveEvents.length ? (
                liveEvents.map((event) => (
                  <div key={event.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{event.headline}</p>
                      <span className="text-[11px] text-[#9b9a97]">{formatTime(event.timestamp)}</span>
                    </div>
                    <p className="mt-1 text-[12px] text-[#6b6b6b]">{event.detail}</p>
                    <p className="mt-2 text-[12px] text-[#787774]">
                      {event.kind}
                      {event.story_id ? ` · story #${event.story_id}` : ""}
                      {event.source ? ` · ${event.source}` : ""}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-[13px] text-[#787774]">No recent company activity is available yet.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
