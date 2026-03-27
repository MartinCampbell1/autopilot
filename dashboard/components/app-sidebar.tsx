"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { AccountHealth } from "@/lib/types";

const NAV_ITEMS = [
  {
    label: "Projects",
    href: "/",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
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
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5v14M5 12h14" />
      </svg>
    ),
  },
];

interface AppSidebarProps {
  health: AccountHealth | null;
}

export function AppSidebar({ health }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-[240px] flex-col border-r border-[#e3e2e0] bg-[#f7f7f5]">
      {/* Logo */}
      <div className="flex h-[48px] items-center gap-2.5 px-4">
        <div className="flex h-[26px] w-[26px] items-center justify-center rounded-md bg-[#37352f]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <span className="text-[14px] font-semibold tracking-[-0.01em] text-[#37352f]">Autopilot</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 pt-1">
        <div className="space-y-px">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2 py-[6px] text-[14px] transition-all duration-100",
                  isActive
                    ? "bg-[#ebebea] font-medium text-[#37352f]"
                    : "font-normal text-[#787774] hover:bg-[#ebebea]/60 hover:text-[#37352f]"
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

      {/* Account Health */}
      {health && (
        <div className="border-t border-[#e3e2e0] px-4 py-3">
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-[#9b9a97]">Accounts</span>
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
