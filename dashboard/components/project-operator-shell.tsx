"use client";

import Link from "next/link";
import type {
  ProjectAuditChainSummary,
  ProjectBootstrapStatus,
  ProjectDetail,
  ProjectRuntimeDiagnosticsReport,
} from "@/lib/types";

interface ProjectOperatorShellProps {
  project: ProjectDetail;
}

function sentenceCase(value?: string | null) {
  return value ? value.replaceAll("_", " ") : "Unknown";
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

function statusChipClass(healthy: boolean, warning = false) {
  if (healthy) return "bg-emerald-50 text-emerald-700";
  if (warning) return "bg-amber-50 text-amber-700";
  return "bg-red-50 text-red-700";
}

function operatorReadiness(
  bootstrap?: ProjectBootstrapStatus | null,
  diagnostics?: ProjectRuntimeDiagnosticsReport | null,
  audit?: ProjectAuditChainSummary | null,
  runtimeControlAvailable?: boolean
) {
  const verificationReady = Boolean(bootstrap?.verification?.artifact_exists);
  const githubReady =
    !bootstrap?.github?.github_repo || Boolean(bootstrap?.github?.workflow_exists);
  const sourceAuditVerified = Boolean(audit?.source_verification?.verified);
  const warningCount = Number(diagnostics?.summary?.warning_count || 0);
  const errorCount = Number(diagnostics?.summary?.error_count || 0);

  return {
    verificationReady,
    githubReady,
    sourceAuditVerified,
    runtimeControlAvailable: Boolean(runtimeControlAvailable),
    warningCount,
    errorCount,
    doctorHealthy: errorCount === 0 && warningCount === 0,
  };
}

export function ProjectOperatorShell({ project }: ProjectOperatorShellProps) {
  const bootstrap = project.bootstrap;
  const diagnostics = project.runtime_diagnostics;
  const audit = project.audit;
  const deliveryStatus = project.delivery_status;
  const readiness = operatorReadiness(
    bootstrap,
    diagnostics,
    audit,
    project.runtime_control_available
  );
  const nextActions = (diagnostics?.diagnostics || [])
    .map((diagnostic) => diagnostic.fix || diagnostic.message)
    .filter(Boolean)
    .slice(0, 4);
  const technicalRunbook = [
    `autopilot doctor ${project.path} --refresh`,
    `autopilot review ${project.path} --github-markdown`,
    `autopilot ship ${project.path}`,
    `autopilot audit ${project.path}`,
  ];

  return (
    <section className="rounded-2xl border border-[#ecebe8] bg-white px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Operator Shell</p>
          <h2 className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            Onboarding, diagnosis, ship, and runtime drill-down
          </h2>
          <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-[#6b6b6b]">
            Business operators can stay in the dashboard, while technical users still get runtime,
            audit, and GitHub drill-down paths from the same workspace.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/control-plane"
            className="inline-flex h-9 items-center justify-center rounded-lg bg-[#1a1a1a] px-3 text-[13px] font-medium text-white transition hover:bg-[#333]"
          >
            Open control plane
          </Link>
          {bootstrap?.github?.compare_url ? (
            <a
              href={bootstrap.github.compare_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center justify-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[13px] font-medium text-[#37352f] transition hover:bg-[#f6f6f4]"
            >
              Open compare
            </a>
          ) : null}
          {project.latest_handoff?.url ? (
            <a
              href={project.latest_handoff.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center justify-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[13px] font-medium text-[#37352f] transition hover:bg-[#f6f6f4]"
            >
              Open PR
            </a>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusChipClass(readiness.doctorHealthy, readiness.warningCount > 0)}`}>
          Doctor {readiness.doctorHealthy ? "ready" : readiness.errorCount > 0 ? "blocked" : "warnings"}
        </span>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusChipClass(readiness.verificationReady, true)}`}>
          Verifiers {readiness.verificationReady ? "installed" : "missing"}
        </span>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusChipClass(readiness.githubReady, true)}`}>
          GitHub loop {readiness.githubReady ? "ready" : "needs bootstrap"}
        </span>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusChipClass(readiness.sourceAuditVerified, true)}`}>
          Audit {readiness.sourceAuditVerified ? "verified" : "check needed"}
        </span>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusChipClass(readiness.runtimeControlAvailable, true)}`}>
          Runtime {readiness.runtimeControlAvailable ? "live" : "offline"}
        </span>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Bootstrap</p>
            <div className="mt-3 space-y-3 text-[13px] text-[#6b6b6b]">
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Verifier checks</p>
                <p className="mt-1 font-medium text-[#37352f]">
                  {bootstrap?.verification?.artifact_exists
                    ? `${bootstrap?.verification?.check_count || 0} checks installed`
                    : "Verifier bootstrap missing"}
                </p>
                <p className="mt-1 break-all text-[12px] text-[#787774]">
                  {bootstrap?.verification?.artifact_path || "No verifier artifact path recorded."}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">GitHub workflow</p>
                <p className="mt-1 font-medium text-[#37352f]">
                  {bootstrap?.github?.workflow_exists
                    ? `Installed for ${bootstrap?.github?.github_repo || "repo"}`
                    : bootstrap?.github?.github_repo
                      ? "Managed workflow missing"
                      : "No GitHub repo identity yet"}
                </p>
                <p className="mt-1 break-all text-[12px] text-[#787774]">
                  {bootstrap?.github?.workflow_path || "No workflow path recorded."}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Doctor Summary</p>
            <div className="mt-3 grid grid-cols-3 gap-3 text-[13px] text-[#6b6b6b]">
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Errors</p>
                <p className="mt-1 font-medium text-[#37352f]">{readiness.errorCount}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Warnings</p>
                <p className="mt-1 font-medium text-[#37352f]">{readiness.warningCount}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Info</p>
                <p className="mt-1 font-medium text-[#37352f]">
                  {Number(diagnostics?.summary?.info_count || 0)}
                </p>
              </div>
            </div>
            <div className="mt-3 space-y-2">
              {(diagnostics?.diagnostics || []).slice(0, 3).map((diagnostic) => (
                <div key={`${diagnostic.code}-${diagnostic.scope}`} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3">
                  <p className="text-[12px] font-medium text-[#37352f]">
                    {sentenceCase(diagnostic.severity)} · {diagnostic.code}
                  </p>
                  <p className="mt-1 text-[12px] text-[#6b6b6b]">{diagnostic.message}</p>
                </div>
              ))}
              {!diagnostics?.diagnostics?.length ? (
                <p className="text-[13px] text-[#787774]">No runtime diagnostics are active.</p>
              ) : null}
            </div>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Delivery Loop</p>
            <p className="mt-3 text-[16px] font-semibold text-[#37352f]">
              {deliveryStatus?.headline || "Source to handoff"}
            </p>
            <p className="mt-1 text-[13px] text-[#6b6b6b]">
              {deliveryStatus?.detail || "Track the project from brief to PR or handoff artifact."}
            </p>
            <p className="mt-3 text-[12px] text-[#787774]">
              Next step: {deliveryStatus?.next_step || "Keep the project moving toward handoff."}
            </p>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Runtime Drill-down</p>
            <div className="mt-3 space-y-3 text-[13px] text-[#6b6b6b]">
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Session</p>
                <p className="mt-1 font-medium text-[#37352f]">
                  {project.runtime_session_id || "No live runtime session"}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Execution log</p>
                <p className="mt-1 break-all text-[#37352f]">{project.log_path || "No log path recorded."}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Trace / audit</p>
                <p className="mt-1 break-all text-[#37352f]">{project.trace_path || "No trace file recorded."}</p>
                <p className="mt-1 text-[12px] text-[#787774]">
                  Source audit hash: {audit?.source_verification?.latest_hash || "Not available"}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Next Actions</p>
            <div className="mt-3 space-y-2">
              {nextActions.length ? (
                nextActions.map((action, index) => (
                  <div key={`${index}-${action}`} className="rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3 text-[13px] text-[#37352f]">
                    {action}
                  </div>
                ))
              ) : (
                <p className="text-[13px] text-[#787774]">
                  Doctor is quiet. Use review, ship, or control-plane actions as needed.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">GitHub Loop</p>
            <div className="mt-3 space-y-3 text-[13px] text-[#6b6b6b]">
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Repo</p>
                <p className="mt-1 font-medium text-[#37352f]">
                  {bootstrap?.github?.github_repo || "No GitHub repo identity yet"}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Current branch</p>
                  <p className="mt-1 text-[#37352f]">{bootstrap?.github?.current_branch || "Unknown"}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Base branch</p>
                  <p className="mt-1 text-[#37352f]">{bootstrap?.github?.default_branch || "Unknown"}</p>
                </div>
              </div>
              <p className="text-[12px] text-[#787774]">
                Updated {formatTimestamp(bootstrap?.github?.updated_at || bootstrap?.verification?.updated_at)}
              </p>
            </div>
          </div>

          <div className="rounded-[14px] border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Technical Runbook</p>
            <div className="mt-3 space-y-2">
              {technicalRunbook.map((command) => (
                <pre
                  key={command}
                  className="overflow-x-auto rounded-[10px] border border-[#ecebe8] bg-white px-3 py-3 text-[12px] leading-relaxed text-[#37352f]"
                >
                  {command}
                </pre>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
