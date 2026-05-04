"use client";
import { useRunStream } from "@/hooks/useRunStream";
import StepsTimeline from "@/components/StepsTimeline";
import MetricTiles from "@/components/MetricTiles";
import MetricCharts from "@/components/MetricCharts";
import { cancelRun } from "@/lib/api";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export default function AdminRunPage({ params }: { params: { id: string } }) {
  const { steps, metrics, status } = useRunStream(params.id);
  const latest = metrics.length > 0 ? metrics[metrics.length - 1] : null;

  return (
    <main className="container mx-auto px-4 py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Run {params.id.slice(0, 8)}…</h1>
          <p className="text-gray-400 text-sm mt-1">
            Status:{" "}
            <span
              className={
                status === "completed"
                  ? "text-green-400"
                  : status === "failed"
                  ? "text-red-400"
                  : status === "cancelled"
                  ? "text-gray-400"
                  : "text-yellow-400"
              }
            >
              {status}
            </span>
          </p>
        </div>
        {!TERMINAL_STATUSES.has(status) && (
          <button
            onClick={() => cancelRun(params.id)}
            className="bg-red-700 hover:bg-red-600 text-white px-4 py-2 rounded transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      <MetricTiles latest={latest} />

      <div>
        <h2 className="text-lg font-semibold mb-3">Steps</h2>
        <StepsTimeline steps={steps} />
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Metrics</h2>
        <MetricCharts metrics={metrics} />
      </div>
    </main>
  );
}
