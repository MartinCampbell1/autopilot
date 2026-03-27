"use client";

import { useCallback, useEffect, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { Button } from "@/components/ui/button";
import {
  fetchAccounts,
  fetchAccountsHealth,
  importProviderSession,
  openProviderLogin,
} from "@/lib/api";
import type { AccountHealth, AccountsByProvider } from "@/lib/types";

const PROVIDERS = ["codex", "claude", "gemini"] as const;

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountsByProvider>({});
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [busyProvider, setBusyProvider] = useState<string>("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const [accountsData, healthData] = await Promise.all([
        fetchAccounts(),
        fetchAccountsHealth(),
      ]);
      setAccounts(accountsData.accounts || {});
      setHealth(healthData);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load accounts.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openLogin = async (provider: string) => {
    setBusyProvider(provider);
    try {
      const data = await openProviderLogin(provider);
      setMessage(data.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to open login flow.");
    } finally {
      setBusyProvider("");
    }
  };

  const importSession = async (provider: string) => {
    setBusyProvider(provider);
    try {
      const data = await importProviderSession(provider);
      setMessage(data.message);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to import session.");
    } finally {
      setBusyProvider("");
    }
  };

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={health} />

      <main className="flex-1 pl-[240px]">
        <header className="sticky top-0 z-30 flex h-[52px] items-center justify-between border-b border-[#e5e5e3] bg-white px-6">
          <h1 className="text-[15px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">Accounts</h1>
          <Button
            variant="outline"
            size="sm"
            className="h-9 rounded-[8px] border-[#e5e5e3] text-[13px]"
            onClick={() => void load()}
          >
            Refresh
          </Button>
        </header>

        <div className="mx-auto max-w-4xl px-6 py-8">
          <div className="rounded-[8px] border border-[#e3e2e0] bg-white px-5 py-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
            <p className="text-[14px] text-[#37352f]">
              Open a provider login in Terminal, complete the auth flow there, then click
              {" "}
              <span className="font-semibold">Import Current Session</span>.
            </p>
            <p className="mt-2 min-h-[20px] text-[13px] text-[#787774]">{message}</p>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {PROVIDERS.map((provider) => {
              const providerAccounts = accounts[provider] || [];
              const busy = busyProvider === provider;

              return (
                <section
                  key={provider}
                  className="rounded-[8px] border border-[#e3e2e0] bg-white p-5 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]"
                >
                  <div className="flex items-center justify-between">
                    <h2 className="text-[15px] font-semibold capitalize text-[#37352f]">{provider}</h2>
                    <span className="rounded-full bg-[#f1f1ef] px-2.5 py-1 text-[12px] font-medium text-[#787774]">
                      {providerAccounts.length} account{providerAccounts.length === 1 ? "" : "s"}
                    </span>
                  </div>

                  <div className="mt-4 space-y-2">
                    {providerAccounts.length === 0 ? (
                      <p className="text-[13px] text-[#9b9a97]">No imported accounts yet.</p>
                    ) : (
                      providerAccounts.map((account) => (
                        <div
                          key={account.name}
                          className="flex items-center justify-between rounded-[8px] border border-[#ecebe8] px-3 py-2"
                        >
                          <span className="text-[13px] font-medium text-[#37352f]">{account.name}</span>
                          <span className={account.available ? "text-[12px] text-[#2b6e3f]" : "text-[12px] text-[#93370d]"}>
                            {account.available ? "Available" : `Cooldown ${account.cooldown_remaining_sec}s`}
                          </span>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="mt-4 flex flex-col gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-9 rounded-[8px] border-[#e5e5e3] text-[13px]"
                      onClick={() => void openLogin(provider)}
                      disabled={busy}
                    >
                      Open Login
                    </Button>
                    <Button
                      size="sm"
                      className="h-9 rounded-[8px] bg-[#37352f] text-[13px] hover:bg-[#4a4a45]"
                      onClick={() => void importSession(provider)}
                      disabled={busy}
                    >
                      Import Current Session
                    </Button>
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
