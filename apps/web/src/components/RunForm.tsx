"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";

export default function RunForm() {
  const router = useRouter();
  const [form, setForm] = useState({
    provider: "stub",
    model_id: "stub-model",
    model_source: "ollama",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const { run_id } = await createRun({
        ...form,
        config: { concurrency_levels: [1, 10, 50, 100] },
      });
      router.push(`/runs/${run_id}`);
    } catch {
      setError("Failed to create run. Are you logged in as admin?");
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4 max-w-md">
      <div>
        <label className="block text-sm text-gray-400 mb-1">Provider</label>
        <input
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          value={form.provider}
          onChange={(e) => setForm({ ...form, provider: e.target.value })}
        />
      </div>
      <div>
        <label className="block text-sm text-gray-400 mb-1">Model ID</label>
        <input
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          value={form.model_id}
          onChange={(e) => setForm({ ...form, model_id: e.target.value })}
        />
      </div>
      <div>
        <label className="block text-sm text-gray-400 mb-1">Source</label>
        <select
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          value={form.model_source}
          onChange={(e) => setForm({ ...form, model_source: e.target.value })}
        >
          <option value="huggingface">HuggingFace</option>
          <option value="ollama">Ollama</option>
        </select>
      </div>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      <button
        type="submit"
        disabled={submitting}
        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded transition-colors"
      >
        {submitting ? "Starting…" : "Start Benchmark"}
      </button>
    </form>
  );
}
