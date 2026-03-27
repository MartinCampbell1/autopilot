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

      source.addEventListener("story_update", handler("story_update"));
      source.addEventListener("account_update", handler("account_update"));
      source.addEventListener("iteration_complete", handler("iteration_complete"));

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
