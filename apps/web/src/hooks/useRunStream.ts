"use client";
import { useEffect, useRef, useState } from "react";

export interface StepEvent {
  step_name: string;
  step_status: string;
  progress_pct?: string;
  message?: string;
}

export interface MetricEvent {
  t_offset_ms: string;
  concurrency: string;
  latency_ms: string;
  throughput_tps: string;
  ttft_ms: string;
  tps: string;
}

export function useRunStream(runId: string) {
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [metrics, setMetrics] = useState<MetricEvent[]>([]);
  const [status, setStatus] = useState<string>("connecting");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const es = new EventSource(`${apiUrl}/runs/${runId}/events`);
    esRef.current = es;

    es.addEventListener("step", (e) => {
      setSteps((prev) => [...prev, JSON.parse(e.data)]);
    });
    es.addEventListener("metric", (e) => {
      setMetrics((prev) => [...prev.slice(-500), JSON.parse(e.data)]);
    });
    es.addEventListener("status", (e) => {
      const payload = JSON.parse(e.data);
      setStatus(payload.status || "unknown");
    });
    es.onerror = () => setStatus("error");

    return () => es.close();
  }, [runId]);

  return { steps, metrics, status };
}
