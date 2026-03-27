"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { AccountHealth, ProjectSummary } from "@/lib/types";

const NAV_ITEMS = [
  {
    label: "Projects",
    href: "/",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    label: "New Project",
    href: "/intake",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5v14M5 12h14" />
      </svg>
    ),
  },
  {
    label: "Accounts",
    href: "/accounts",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    label: "Settings",
    href: "/settings",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 .6 1.65 1.65 0 0 0-.33 1.82v.08a2 2 0 0 1-1.64 1.1 2 2 0 0 1-1.64-1.1v-.08a1.65 1.65 0 0 0-.33-1.82 1.65 1.65 0 0 0-1-.6 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-.6-1 1.65 1.65 0 0 0-1.82-.33h-.08a2 2 0 0 1-1.1-1.64 2 2 0 0 1 1.1-1.64h.08a1.65 1.65 0 0 0 1.82-.33 1.65 1.65 0 0 0 .6-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-.6 1.65 1.65 0 0 0 .33-1.82V2.1a2 2 0 0 1 1.64-1.1 2 2 0 0 1 1.64 1.1v.08a1.65 1.65 0 0 0 .33 1.82 1.65 1.65 0 0 0 1 .6 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.24.27.48.59.6 1 .15.51.15 1.1 0 1.6-.12.41-.36.73-.6 1Z" />
      </svg>
    ),
  },
];

const STATUS_DOT: Record<ProjectSummary["status"], string> = {
  idle: "bg-[#9b9a97]",
  running: "bg-[#2a6690]",
  paused: "bg-[#d9730d]",
  completed: "bg-[#2b6e3f]",
  failed: "bg-[#93370d]",
};

interface AppSidebarProps {
  health: AccountHealth | null;
  projects?: ProjectSummary[];
  activeProjectId?: string | null;
}

export function AppSidebar({ health, projects = [], activeProjectId }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-[260px] flex-col border-r border-[#e3e2e0] bg-[#f7f7f5]">
      <div className="flex h-[52px] items-center gap-2.5 border-b border-[#ecebe8] px-4">
        <div className="flex h-[28px] w-[28px] items-center justify-center rounded-md bg-[#37352f]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <span className="text-[14px] font-semibold tracking-[-0.01em] text-[#37352f]">Autopilot</span>
      </div>

      <nav className="border-b border-[#ecebe8] px-2 py-2">
        <div className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors",
                  isActive
                    ? "bg-[#ebebea] font-medium text-[#37352f]"
                    : "text-[#787774] hover:bg-[#ebebea]/70 hover:text-[#37352f]"
                )}
              >
                <span className={cn(isActive ? "text-[#37352f]" : "text-[#9b9a97]")}>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="min-h-0 flex-1 px-2 py-3">
        <div className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
          Workspace
        </div>
        <div className="space-y-1 overflow-y-auto pr-1">
          {projects.length === 0 ? (
            <div className="rounded-md px-2 py-3 text-[12px] text-[#9b9a97]">
              No active projects.
            </div>
          ) : (
            projects.map((project) => {
              const isProjectActive =
                activeProjectId === project.id || pathname === `/projects/${project.id}`;
              return (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className={cn(
                    "block rounded-md border px-2.5 py-2 transition-colors",
                    isProjectActive
                      ? "border-[#d8d7d3] bg-white shadow-[0_1px_2px_rgba(15,15,15,0.04)]"
                      : "border-transparent hover:bg-[#ebebea]/60"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="line-clamp-2 text-[12px] font-medium leading-[1.35] text-[#37352f]">
                      {project.name}
                    </p>
                    <span className={cn("mt-1 inline-block h-2 w-2 shrink-0 rounded-full", STATUS_DOT[project.status])} />
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px] text-[#9b9a97]">
                    <span>{project.stories_done}/{project.stories_total}</span>
                    <span className="capitalize">{project.status}</span>
                  </div>
                </Link>
              );
            })
          )}
        </div>
      </div>

      {health && (
        <div className="border-t border-[#e3e2e0] px-4 py-3">
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-[#9b9a97]">Agents</span>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-[#2ecc71]" />
              <span className="font-medium tabular-nums text-[#37352f]">
                {health.available}/{health.total}
              </span>
            </div>
          </div>
          {health.on_cooldown > 0 && (
            <div className="mt-1.5 flex items-center gap-2 text-[12px] text-[#9b9a97]">
              <span className="inline-block h-2 w-2 rounded-full bg-[#f5a623]" />
              {health.on_cooldown} on cooldown
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
