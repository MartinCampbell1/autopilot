"use client";

import { useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { IntakeChat } from "@/components/intake-chat";
import { Button } from "@/components/ui/button";
import type { PRD } from "@/lib/types";

export default function IntakePage() {
  const [prd, setPRD] = useState<PRD | null>(null);

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={null} />

      <main className="flex-1 pl-[240px]">
        <header className="sticky top-0 z-30 flex h-[52px] items-center border-b border-[#e5e5e3] bg-white px-6">
          <h1 className="text-[15px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">New Project</h1>
        </header>

        <div className="mx-auto max-w-2xl px-6 py-8">
          <IntakeChat onPRDReady={setPRD} />

          {prd && (
            <div className="mt-8 rounded-xl border border-[#e5e5e3] bg-white overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
              <div className="px-5 py-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-[17px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">
                    {prd.title}
                  </h3>
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-[12px] font-semibold text-emerald-700">
                    Ready
                  </span>
                </div>
                <p className="mt-2.5 text-[14px] text-[#6b6b6b] leading-relaxed">
                  {prd.description}
                </p>
              </div>

              <div className="border-t border-[#e5e5e3] px-5 py-5">
                <h4 className="text-[12px] font-semibold uppercase tracking-wider text-[#9ca3af] mb-3">
                  Stories ({prd.stories?.length || 0})
                </h4>
                <div className="space-y-2">
                  {prd.stories?.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-start gap-3 rounded-lg border border-[#e5e5e3] px-4 py-3"
                    >
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[#f0f0ee] text-[11px] font-bold tabular-nums text-[#6b6b6b]">
                        {s.id}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[14px] font-medium text-[#1a1a1a]">{s.title}</p>
                        {s.description && (
                          <p className="mt-0.5 text-[13px] text-[#9ca3af] truncate">
                            {s.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border-t border-[#e5e5e3] px-5 py-3.5 flex justify-end gap-2">
                <Button variant="outline" size="sm" className="h-9 rounded-lg text-[13px] border-[#e5e5e3]">
                  Edit PRD
                </Button>
                <Button size="sm" className="h-9 rounded-lg text-[13px] bg-[#1a1a1a] hover:bg-[#333]">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  Launch Project
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
