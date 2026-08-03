import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { LiveDecisionResponse } from "../types/decision";

interface UseLiveDecisionResult {
  data: LiveDecisionResponse | null;
  error: string | null;
  loading: boolean;
  lastUpdated: number | null;
  transport: "websocket" | "polling" | null;
}

const POLL_INTERVAL_MS = 3000;
const WS_RECONNECT_DELAY_MS = 4000;

function wsUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL?.trim() || window.location.origin;
  return base.replace(/^http/, "ws") + "/ws/decision";
}

/**
 * Prefers a live WebSocket connection to /ws/decision (real-time push, no
 * wasted requests). If the socket can't connect or drops and won't come
 * back, falls back to polling GET /api/decision/live every 3s so the
 * dashboard degrades gracefully instead of going dark.
 */
export function useLiveDecision(): UseLiveDecisionResult {
  const [data, setData] = useState<LiveDecisionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [transport, setTransport] = useState<"websocket" | "polling" | null>(null);
  const lastTimestamp = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let pollId: ReturnType<typeof setInterval> | null = null;
    let reconnectId: ReturnType<typeof setTimeout> | null = null;
    let wsFailureCount = 0;

    function applyPayload(resp: LiveDecisionResponse) {
      if (cancelled) return;
      setError(null);
      setLoading(false);
      if (resp.timestamp !== lastTimestamp.current) {
        lastTimestamp.current = resp.timestamp;
        setData(resp);
        setLastUpdated(Date.now());
      }
    }

    function startPolling() {
      if (pollId) return;
      setTransport("polling");
      const poll = async () => {
        try {
          const resp = await api.getLiveDecision();
          applyPayload(resp);
        } catch (e) {
          if (!cancelled) setError(e instanceof Error ? e.message : "Unknown error fetching live decision");
        }
      };
      poll();
      pollId = setInterval(poll, POLL_INTERVAL_MS);
    }

    function stopPolling() {
      if (pollId) {
        clearInterval(pollId);
        pollId = null;
      }
    }

    function connectWebSocket() {
      if (cancelled) return;
      try {
        ws = new WebSocket(wsUrl());
      } catch {
        startPolling();
        return;
      }

      ws.onopen = () => {
        wsFailureCount = 0;
        stopPolling();
        setTransport("websocket");
      };
      ws.onmessage = (event) => {
        try {
          const resp = JSON.parse(event.data) as LiveDecisionResponse;
          applyPayload(resp);
        } catch {
          /* ignore malformed frame, wait for next tick */
        }
      };
      ws.onerror = () => {
        /* onclose will fire next and handle fallback/reconnect */
      };
      ws.onclose = () => {
        if (cancelled) return;
        wsFailureCount += 1;
        // after a couple of failed attempts, degrade to polling so the
        // dashboard stays live while we keep retrying the socket in the background
        if (wsFailureCount >= 2) startPolling();
        reconnectId = setTimeout(connectWebSocket, WS_RECONNECT_DELAY_MS);
      };
    }

    connectWebSocket();

    return () => {
      cancelled = true;
      stopPolling();
      if (reconnectId) clearTimeout(reconnectId);
      if (ws) {
        ws.onclose = null; // prevent reconnect logic firing during teardown
        ws.close();
      }
    };
  }, []);

  return { data, error, loading, lastUpdated, transport };
}
