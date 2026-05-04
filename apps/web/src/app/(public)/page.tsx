import Leaderboard from "@/components/Leaderboard";

export default function HomePage() {
  return (
    <main className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">LLM Speed Leaderboard</h1>
        <a href="/login" className="text-sm text-gray-400 hover:text-white transition-colors">
          Admin →
        </a>
      </div>
      <Leaderboard />
    </main>
  );
}
