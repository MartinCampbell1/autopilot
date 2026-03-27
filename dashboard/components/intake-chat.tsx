"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { sendIntakeMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { IntakeMessage, PRD } from "@/lib/types";

interface IntakeChatProps {
  onPRDReady?: (prd: PRD) => void;
}

export function IntakeChat({ onPRDReady }: IntakeChatProps) {
  const [messages, setMessages] = useState<IntakeMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const data = await sendIntakeMessage(text, sessionId);
      setSessionId(data.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
      if (data.prd_ready && data.prd) {
        onPRDReady?.(data.prd);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Failed to connect to API. Is the server running?" },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="flex flex-col h-[560px] rounded-[8px] bg-white overflow-hidden shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      {/* Chat messages */}
      <ScrollArea className="flex-1">
        <div className="px-6 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              {/* Decorative illustration */}
              <div className="mb-5 relative">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#f7f7f5]">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9b9a97" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                </div>
                <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#dbeddb]">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#2b6e3f" strokeWidth="3">
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                </div>
              </div>
              <p className="text-[16px] font-semibold text-[#37352f]">
                Describe your project idea
              </p>
              <p className="mt-2 text-[14px] text-[#9b9a97] max-w-[300px] leading-relaxed">
                The intake agent will ask clarifying questions and generate a PRD with stories ready to execute.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              <div
                className={cn(
                  "max-w-[80%] rounded-2xl px-4 py-3",
                  msg.role === "user"
                    ? "bg-[#37352f] text-white"
                    : "bg-[#f7f7f5] text-[#37352f]"
                )}
              >
                <pre className="whitespace-pre-wrap text-[14px] leading-[1.55] font-sans">
                  {msg.content}
                </pre>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-[#f7f7f5] rounded-2xl px-4 py-3">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[#c3c2bf] animate-pulse" />
                  <span className="h-2 w-2 rounded-full bg-[#c3c2bf] animate-pulse [animation-delay:150ms]" />
                  <span className="h-2 w-2 rounded-full bg-[#c3c2bf] animate-pulse [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input — closer to empty state */}
      <div className="border-t border-[#e3e2e0] px-5 py-3.5">
        <div className="flex items-end gap-2.5">
          <textarea
            ref={inputRef}
            placeholder="Describe your project..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            rows={1}
            className="flex-1 resize-none rounded-[8px] border border-[#e3e2e0] bg-[#fbfbf9] px-4 py-2.5 text-[14px] text-[#37352f] placeholder:text-[#c3c2bf] focus:border-[#37352f] focus:bg-white focus:outline-none focus:ring-0 disabled:opacity-50 transition-colors"
          />
          <Button
            size="sm"
            onClick={send}
            disabled={loading || !input.trim()}
            className="h-10 w-10 shrink-0 rounded-[8px] bg-[#37352f] hover:bg-[#4a4a45] p-0 shadow-[0_1px_3px_rgba(15,15,15,0.15)]"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </Button>
        </div>
      </div>
    </div>
  );
}
