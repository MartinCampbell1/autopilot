"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { storyAction } from "@/lib/api";

interface ActionButtonsProps {
  projectName: string;
  storyId: number;
  onAction?: () => void;
}

export function ActionButtons({ projectName, storyId, onAction }: ActionButtonsProps) {
  const [guidance, setGuidance] = useState("");
  const [showGuidance, setShowGuidance] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleAction = async (action: string, payload = "") => {
    setLoading(true);
    try {
      await storyAction(projectName, storyId, action, payload);
      onAction?.();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={loading}
          onClick={() => handleAction("pause")}
          className="h-8 rounded-lg text-[12px] font-medium"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mr-1.5">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
          Pause
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={loading}
          onClick={() => handleAction("skip")}
          className="h-8 rounded-lg text-[12px] font-medium"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mr-1.5">
            <path d="M5 4l10 8-10 8V4z" />
            <line x1="19" y1="5" x2="19" y2="19" />
          </svg>
          Skip
        </Button>
        <Button
          size="sm"
          variant={showGuidance ? "default" : "outline"}
          onClick={() => setShowGuidance(!showGuidance)}
          className="h-8 rounded-lg text-[12px] font-medium"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mr-1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          Guidance
        </Button>
      </div>

      {showGuidance && (
        <div className="space-y-2">
          <Textarea
            placeholder="Add guidance for the agent..."
            value={guidance}
            onChange={(e) => setGuidance(e.target.value)}
            className="min-h-[80px] resize-none rounded-lg border-border/60 text-[13px] placeholder:text-muted-foreground/50"
          />
          <div className="flex justify-end gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setShowGuidance(false);
                setGuidance("");
              }}
              className="h-7 text-[12px]"
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!guidance.trim() || loading}
              onClick={() => {
                handleAction("add_guidance", guidance);
                setGuidance("");
                setShowGuidance(false);
              }}
              className="h-7 text-[12px]"
            >
              Send
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
