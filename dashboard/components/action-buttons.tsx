"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { addStoryGuidance, pauseProject, skipStory } from "@/lib/api";
import type { ProjectRunStatus } from "@/lib/types";

interface ActionButtonsProps {
  projectId: string;
  storyId: number;
  projectStatus: ProjectRunStatus;
  onAction?: () => void | Promise<void>;
}

export function ActionButtons({
  projectId,
  storyId,
  projectStatus,
  onAction,
}: ActionButtonsProps) {
  const [guidance, setGuidance] = useState("");
  const [showGuidance, setShowGuidance] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const runAction = async (task: () => Promise<{ message: string }>) => {
    setLoading(true);
    setMessage("");
    try {
      const result = await task();
      setMessage(result.message);
      await onAction?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={loading || projectStatus !== "running"}
          onClick={() => void runAction(() => pauseProject(projectId))}
          className="h-8 rounded-lg text-[12px] font-medium"
        >
          Pause
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={loading}
          onClick={() => void runAction(() => skipStory(projectId, storyId))}
          className="h-8 rounded-lg text-[12px] font-medium"
        >
          Skip
        </Button>
        <Button
          size="sm"
          variant={showGuidance ? "default" : "outline"}
          onClick={() => setShowGuidance(!showGuidance)}
          className="h-8 rounded-lg text-[12px] font-medium"
        >
          Guidance
        </Button>
      </div>

      {showGuidance && (
        <div className="space-y-2">
          <Textarea
            placeholder="Add guidance for the next iteration..."
            value={guidance}
            onChange={(event) => setGuidance(event.target.value)}
            className="min-h-[90px] resize-none rounded-lg border-border/60 text-[13px]"
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
                void runAction(() => addStoryGuidance(projectId, storyId, guidance));
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

      {message && (
        <div className="rounded-lg border border-[#e5e5e3] bg-[#fbfbf9] px-3 py-2 text-[12px] text-[#6b6b6b]">
          {message}
        </div>
      )}
    </div>
  );
}
