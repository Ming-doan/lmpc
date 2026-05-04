"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getRuns } from "@/lib/api";

export default function Leaderboard() {
  const { data: runs, isLoading, isError } = useQuery({
    queryKey: ["runs"],
    queryFn: () => getRuns(),
  });

  if (isLoading) return <div className="text-gray-500">Loading…</div>;
  if (isError) return <div className="text-red-400">Failed to load runs.</div>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400 text-left">
            <th className="py-3 pr-4">Model</th>
            <th className="py-3 pr-4">Provider</th>
            <th className="py-3 pr-4 text-right">Latency ms</th>
            <th className="py-3 pr-4 text-right">Tok/s</th>
            <th className="py-3 pr-4 text-right">TTFT ms</th>
            <th className="py-3 text-right">Completed</th>
          </tr>
        </thead>
        <tbody>
          {(runs || []).map((run) => (
            <tr key={run.id} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
              <td className="py-3 pr-4">
                <Link href={`/runs/${run.id}`} className="text-blue-400 hover:underline">
                  {run.model_id}
                </Link>
              </td>
              <td className="py-3 pr-4 text-gray-400">{run.provider}</td>
              <td className="py-3 pr-4 text-right tabular-nums">
                {run.avg_latency_ms?.toFixed(0) ?? "—"}
              </td>
              <td className="py-3 pr-4 text-right tabular-nums">
                {run.avg_throughput_tps?.toFixed(1) ?? "—"}
              </td>
              <td className="py-3 pr-4 text-right tabular-nums">
                {run.avg_ttft_ms?.toFixed(0) ?? "—"}
              </td>
              <td className="py-3 text-right text-gray-400">
                {run.completed_at
                  ? new Date(run.completed_at).toLocaleDateString()
                  : "—"}
              </td>
            </tr>
          ))}
          {(runs || []).length === 0 && (
            <tr>
              <td colSpan={6} className="py-8 text-center text-gray-500">
                No completed runs yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
