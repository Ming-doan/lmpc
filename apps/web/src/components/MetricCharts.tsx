"use client";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { MetricEvent } from "@/hooks/useRunStream";

export default function MetricCharts({ metrics }: { metrics: MetricEvent[] }) {
  const data = metrics.map((m) => ({
    t: Math.round(parseFloat(m.t_offset_ms) / 1000),
    latency: parseFloat(m.latency_ms).toFixed(1),
    tps: parseFloat(m.tps).toFixed(1),
    ttft: parseFloat(m.ttft_ms).toFixed(1),
  }));

  return (
    <div className="space-y-6">
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <XAxis dataKey="t" stroke="#6b7280" label={{ value: "s", position: "insideRight" }} />
          <YAxis stroke="#6b7280" />
          <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "none" }} />
          <Legend />
          <Line type="monotone" dataKey="latency" stroke="#60a5fa" dot={false} name="Latency ms" />
        </LineChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <XAxis dataKey="t" stroke="#6b7280" />
          <YAxis stroke="#6b7280" />
          <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "none" }} />
          <Legend />
          <Line type="monotone" dataKey="tps" stroke="#34d399" dot={false} name="TPS" />
          <Line type="monotone" dataKey="ttft" stroke="#f59e0b" dot={false} name="TTFT ms" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
