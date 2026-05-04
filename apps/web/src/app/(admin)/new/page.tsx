import RunForm from "@/components/RunForm";

export default function NewRunPage() {
  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">New Benchmark Run</h1>
      <RunForm />
    </main>
  );
}
