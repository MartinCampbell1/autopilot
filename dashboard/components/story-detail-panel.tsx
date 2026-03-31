"use client";

import { ActionButtons } from "./action-buttons";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ProjectRunStatus, Story, TimelineEvent } from "@/lib/types";

const STATUS_LABELS: Record<Story["status"], string> = {
  open: "Open",
  in_progress: "In Progress",
  done: "Done",
  stuck: "Stuck",
  skipped: "Skipped",
  merge_blocked: "Merge Blocked",
};

const STATUS_STYLES: Record<Story["status"], string> = {
  open: "bg-neutral-100 text-neutral-600",
  in_progress: "bg-blue-50 text-blue-600",
  done: "bg-emerald-50 text-emerald-600",
  stuck: "bg-red-50 text-red-600",
  skipped: "bg-neutral-100 text-neutral-500",
  merge_blocked: "bg-amber-50 text-amber-700",
};

interface StoryDetailPanelProps {
  projectId: string;
  projectStatus: ProjectRunStatus;
  story: Story | null;
  timeline: TimelineEvent[];
  guardrails: string;
  logTail: string;
  onAction?: () => void | Promise<void>;
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

function formatTaskSource(event: TimelineEvent) {
  const taskSource = event.task_source;
  if (!taskSource) return "";
  return [taskSource.source_kind, taskSource.external_id, taskSource.repo].filter(Boolean).join(" / ");
}

export function StoryDetailPanel({
  projectId,
  projectStatus,
  story,
  timeline,
  guardrails,
  logTail,
  onAction,
}: StoryDetailPanelProps) {
  if (!story) {
    return (
      <aside className="sticky top-[52px] h-[calc(100vh-52px)] w-[420px] border-l border-[#e5e5e3] bg-white p-5">
        <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-[#e5e5e3] bg-[#fbfbf9] px-6 text-center text-[13px] text-[#9b9a97]">
          Select a story to inspect progress, logs, guidance, and errors.
        </div>
      </aside>
    );
  }

  const storyTimeline = timeline.filter(
    (event) => event.story_id === story.id || event.story_id == null
  );

  return (
    <aside className="sticky top-[52px] h-[calc(100vh-52px)] w-[420px] overflow-y-auto border-l border-[#e5e5e3] bg-white">
      <div className="border-b border-[#ecebe8] px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Story #{story.id}</p>
            <h2 className="mt-1 text-[18px] font-semibold leading-snug tracking-[-0.02em] text-[#37352f]">
              {story.title}
            </h2>
          </div>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${STATUS_STYLES[story.status]}`}>
            {STATUS_LABELS[story.status]}
          </span>
        </div>
        {story.description && (
          <p className="mt-3 text-[13px] leading-relaxed text-[#6b6b6b]">{story.description}</p>
        )}
      </div>

      <div className="px-5 py-5">
        <div className="grid grid-cols-2 gap-3 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Worker</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">{story.agent || "Unassigned"}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Critic</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">{story.critic || "Unassigned"}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Iteration</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">{story.iteration ?? 0}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Updated</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">{formatTimestamp(story.updated_at)}</p>
          </div>
        </div>

        <div className="mt-5">
          <p className="mb-2 text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Actions</p>
          <ActionButtons
            projectId={projectId}
            storyId={story.id}
            projectStatus={projectStatus}
            onAction={onAction}
          />
        </div>

        <Tabs defaultValue="timeline" className="mt-6">
          <TabsList className="w-full justify-start bg-[#f1f1ef]">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="logs">Logs</TabsTrigger>
            <TabsTrigger value="guardrails">Guardrails</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4">
            <div className="space-y-3 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4 text-[13px] text-[#6b6b6b]">
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Started</p>
                <p className="mt-1 text-[#37352f]">{formatTimestamp(story.started_at)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Completed</p>
                <p className="mt-1 text-[#37352f]">{formatTimestamp(story.completed_at)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Last Error</p>
                <p className="mt-1 whitespace-pre-wrap text-[#37352f]">
                  {story.last_error || "No story-scoped errors yet."}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Team Mode</p>
                <p className="mt-1 text-[#37352f]">{story.team_mode || "solo"}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Worktree</p>
                <p className="mt-1 break-all text-[#37352f]">{story.worktree_path || "Main workspace"}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Branch</p>
                <p className="mt-1 text-[#37352f]">{story.branch_name || story.github_pr?.head_branch || "main"}</p>
              </div>
            </div>

            <div className="mt-4 space-y-3 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4 text-[13px] text-[#6b6b6b]">
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">GitHub Handoff</p>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Pull Request</p>
                {story.github_pr?.url ? (
                  <a
                    href={story.github_pr.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-flex text-[#2a6690] underline-offset-2 hover:underline"
                  >
                    {story.github_pr.number ? `PR #${story.github_pr.number}` : story.github_pr.title || story.github_pr.url}
                  </a>
                ) : (
                  <p className="mt-1 text-[#37352f]">Not opened yet</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">PR State</p>
                  <p className="mt-1 text-[#37352f]">{sentenceCase(story.github_pr?.state)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">CI State</p>
                  <p className="mt-1 text-[#37352f]">{sentenceCase(story.github_pr?.ci_status)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Review State</p>
                  <p className="mt-1 text-[#37352f]">{sentenceCase(story.github_pr?.review_status)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Handoff</p>
                  <p className="mt-1 text-[#37352f]">{sentenceCase(story.github_pr?.handoff_status)}</p>
                </div>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Merge State</p>
                <p className="mt-1 text-[#37352f]">{sentenceCase(story.github_pr?.merge_state)}</p>
              </div>
            </div>

            <div className="mt-4 space-y-3 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4 text-[13px] text-[#6b6b6b]">
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Planned Tools</p>
                {story.tools?.length ? (
                  <div className="mt-2 space-y-2">
                    {story.tools.map((tool) => (
                      <div key={tool.tool_id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[13px] font-medium text-[#37352f]">{tool.name}</p>
                          <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1 text-[11px] text-[#787774]">
                            {tool.kind}
                          </span>
                        </div>
                        <p className="mt-1 text-[12px] text-[#787774]">{tool.tool_id}</p>
                        <p className="mt-2 text-[12px] text-[#6b6b6b]">
                          Scope: {tool.scope} · Approval: {tool.approval_policy}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-[#37352f]">{story.connectors?.join(", ") || "None"}</p>
                )}
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Activation Errors</p>
                <p className="mt-1 whitespace-pre-wrap text-[#37352f]">
                  {story.activation_errors?.length ? story.activation_errors.join("\n") : "No connector activation errors."}
                </p>
              </div>
            </div>

            <div className="mt-4 space-y-3 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4 text-[13px] text-[#6b6b6b]">
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Team Assignments</p>
              {story.team_members?.length ? (
                story.team_members.map((member) => (
                  <div key={member.member_id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{member.label}</p>
                      <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1 text-[11px] text-[#787774]">
                        {member.provider}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] text-[#787774]">{member.role_id}</p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">
                      Skills: {member.skill_packs.join(", ") || "none"}
                    </p>
                    <p className="mt-1 text-[12px] text-[#6b6b6b]">
                      Planned connectors: {member.planned_connectors.join(", ") || "none"}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-[#9b9a97]">No team assignments resolved yet.</p>
              )}
            </div>

            <div className="mt-4 space-y-3 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4 text-[13px] text-[#6b6b6b]">
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Runtime-Active Tools</p>
              {story.active_tools?.length ? (
                story.active_tools.map((tool) => (
                  <div key={tool.tool_id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{tool.name}</p>
                      <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1 text-[11px] text-[#787774]">
                        {tool.status}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] text-[#787774]">{tool.tool_id}</p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">
                      {tool.kind} · {tool.scope} · {tool.reason || "No activation note."}
                    </p>
                  </div>
                ))
              ) : story.connector_activation?.length ? (
                story.connector_activation.map((connector) => (
                  <div key={connector.id} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-medium text-[#37352f]">{connector.name}</p>
                      <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1 text-[11px] text-[#787774]">
                        {connector.status}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] text-[#787774]">{connector.id}</p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">{connector.reason || "No activation note."}</p>
                  </div>
                ))
              ) : (
                <p className="text-[#9b9a97]">No tool activation recorded yet.</p>
              )}
            </div>
          </TabsContent>

          <TabsContent value="timeline" className="mt-4">
            <div className="space-y-3">
              {storyTimeline.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#e5e5e3] px-4 py-6 text-[13px] text-[#9b9a97]">
                  No timeline events yet.
                </div>
              ) : (
                [...storyTimeline].reverse().map((event, index) => (
                  <div key={`${event.timestamp}-${index}`} className="rounded-xl border border-[#ecebe8] px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[12px] font-semibold uppercase tracking-[0.06em] text-[#9b9a97]">
                        {event.event.replaceAll("_", " ")}
                      </p>
                      <span className="text-[11px] text-[#9b9a97]">{formatTimestamp(event.timestamp)}</span>
                    </div>
                    <p className="mt-2 text-[13px] leading-relaxed text-[#37352f]">{event.message}</p>
                    {(event.task_source || event.handoff) && (
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {event.task_source && (
                          <div className="rounded-[10px] border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
                            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Source</p>
                            <p className="mt-1 text-[12px] font-medium text-[#37352f]">{formatTaskSource(event)}</p>
                            <p className="mt-2 text-[11px] text-[#787774]">
                              Branch policy: {event.task_source.branch_policy}
                            </p>
                          </div>
                        )}
                        {event.handoff && (
                          <div className="rounded-[10px] border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
                            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Handoff</p>
                            <p className="mt-1 text-[12px] font-medium text-[#37352f]">
                              {event.handoff.number
                                ? `PR #${event.handoff.number}`
                                : event.handoff.head_branch || event.handoff.story_title}
                            </p>
                            <p className="mt-2 text-[11px] text-[#787774]">
                              {sentenceCase(event.handoff.handoff_status)} / {sentenceCase(event.handoff.merge_state)}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </TabsContent>

          <TabsContent value="logs" className="mt-4">
            <div className="rounded-xl border border-[#ecebe8] bg-[#111111] p-4">
              <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap text-[12px] leading-relaxed text-[#e7e7e7]">
                {logTail || "No execution log yet."}
              </pre>
            </div>
          </TabsContent>

          <TabsContent value="guardrails" className="mt-4">
            <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <pre className="whitespace-pre-wrap text-[12px] leading-relaxed text-[#37352f]">
                {guardrails || "No guardrails yet."}
              </pre>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </aside>
  );
}
