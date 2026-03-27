"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { importSpec } from "@/lib/api";
import type { PRD } from "@/lib/types";

interface SpecImportPanelProps {
  onPRDReady: (prd: PRD) => void;
}

export function SpecImportPanel({ onPRDReady }: SpecImportPanelProps) {
  const [specText, setSpecText] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleFile = async (file: File | null) => {
    if (!file) return;
    setSpecText(await file.text());
    setMessage(`Loaded ${file.name}`);
  };

  const handleImport = async () => {
    const text = specText.trim();
    if (!text || loading) return;

    setLoading(true);
    setMessage("");

    try {
      const data = await importSpec(text);
      onPRDReady(data.prd);
      setMessage("PRD generated from the uploaded spec.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to import spec.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-[8px] border border-[#e3e2e0] bg-white p-5 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-semibold text-[#37352f]">Import Spec</h2>
          <p className="mt-1 text-[13px] leading-relaxed text-[#787774]">
            Paste a PRD/spec directly or load a `.md`, `.txt`, or `.json` file.
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center rounded-[8px] border border-[#e3e2e0] bg-[#fbfbf9] px-3 py-2 text-[13px] font-medium text-[#37352f]">
          Load file
          <input
            type="file"
            accept=".md,.txt,.json,.prd"
            className="hidden"
            onChange={(event) => void handleFile(event.target.files?.[0] ?? null)}
          />
        </label>
      </div>

      <textarea
        value={specText}
        onChange={(event) => setSpecText(event.target.value)}
        placeholder="Paste the specification or PRD here..."
        className="mt-4 h-[320px] w-full resize-none rounded-[8px] border border-[#e3e2e0] bg-[#fbfbf9] px-4 py-3 text-[14px] leading-[1.55] text-[#37352f] outline-none transition-colors focus:border-[#37352f] focus:bg-white"
      />

      <div className="mt-4 flex items-center justify-between gap-4">
        <p className="min-h-[20px] text-[13px] text-[#787774]">{message}</p>
        <Button
          onClick={handleImport}
          disabled={loading || !specText.trim()}
          className="h-9 rounded-[8px] bg-[#37352f] px-4 text-[13px] hover:bg-[#4a4a45]"
        >
          {loading ? "Generating PRD..." : "Generate PRD"}
        </Button>
      </div>
    </div>
  );
}
