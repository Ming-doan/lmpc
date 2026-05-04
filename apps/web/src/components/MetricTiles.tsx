import type { MetricEvent } from "@/hooks/useRunStream";

export default function MetricTiles({ latest }: { latest: MetricEvent | null }) {
  if (!latest) return <div className="text-gray-500 text-sm">Waiting for metrics…</div>;
  const tiles = [
    { label: "Latency", value: `${parseFloat(latest.latency_ms).toFixed(0)} ms` },
    { label: "Throughput", value: `${parseFloat(latest.throughput_tps).toFixed(1)} tok/s` },
    { label: "TTFT", value: `${parseFloat(latest.ttft_ms).toFixed(0)} ms` },
    { label: "TPS", value: `${parseFloat(latest.tps).toFixed(1)}` },
    { label: "Concurrency", value: latest.concurrency },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {tiles.map(({ label, value }) => (
        <div key={label} className="bg-gray-800 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-white">{value}</div>
          <div className="text-xs text-gray-400 mt-1">{label}</div>
        </div>
      ))}
    </div>
  );
}
