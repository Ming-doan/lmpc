import type { StepEvent } from "@/hooks/useRunStream";

export default function StepsTimeline({ steps }: { steps: StepEvent[] }) {
  return (
    <div className="space-y-2">
      {steps.map((s, i) => (
        <div key={i} className="flex items-center gap-3 text-sm">
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 ${
              s.step_status === "completed"
                ? "bg-green-400"
                : s.step_status === "failed"
                ? "bg-red-400"
                : "bg-yellow-400"
            }`}
          />
          <span className="font-mono text-gray-300">{s.step_name}</span>
          <span className="text-gray-500">{s.step_status}</span>
          {s.progress_pct && <span className="text-gray-400">{s.progress_pct}%</span>}
          {s.message && <span className="text-gray-500 truncate max-w-xs">{s.message}</span>}
        </div>
      ))}
    </div>
  );
}
