import { useQuery } from "@tanstack/react-query";
import { getProgress } from "../api/progress";

export function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["progress"],
    queryFn: getProgress,
  });

  if (isLoading) {
    return <p className="text-gray-500">Loading progress...</p>;
  }

  if (error) {
    return (
      <p className="text-red-600">
        Failed to load progress. Is the backend running on :8000?
      </p>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Living Dex Progress</h2>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard label="Total Species" value={data.total_species} />
        <StatCard label="Owned" value={data.owned_species} />
        <StatCard label="Missing" value={data.missing_species} />
        <StatCard label="Completion" value={`${data.completion_percentage}%`} />
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-900">{value}</p>
    </div>
  );
}
