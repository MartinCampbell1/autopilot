"use client";

import { useEffect, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420/api";

export function useSSE(onEvent: (event: string, data: unknown) => void) {
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    let isClosed = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let source: EventSource | null = null;

    const connect = () => {
      source = new EventSource(`${API_BASE}/events/`);

      const handler = (type: string) => (event: MessageEvent) => {
        try {
          onEventRef.current(type, JSON.parse(event.data));
        } catch {
          onEventRef.current(type, event.data);
        }
      };

      [
        "project_created",
        "run_started",
        "story_started",
        "iteration_started",
        "worker_progress",
        "worker_failed",
        "critic_rejected",
        "story_done",
        "story_stuck",
        "paused",
        "resumed",
        "guidance_added",
        "story_skipped",
        "run_finished",
        "run_failed",
        "project_archived",
      ].forEach((type) => {
        source?.addEventListener(type, handler(type));
      });

      source.onerror = () => {
        source?.close();
        if (!isClosed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      isClosed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      source?.close();
    };
  }, []);
}
