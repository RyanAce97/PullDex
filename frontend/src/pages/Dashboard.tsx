import { useProgress } from "../hooks/useProgress";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ProgressBar } from "../components/ProgressBar";
import { StatCard } from "../components/StatCard";

export function Dashboard() {
  const { data, isLoading, error } = useProgress();

  if (isLoading) {
    return <LoadingSpinner message="Loading progress..." />;
  }

  if (error) {
    return <ErrorState message="Failed to load progress." />;
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Living Dex Progress</h2>

      <ProgressBar
        percentage={data.completion_percentage}
        label={`${data.owned_species} / ${data.total_species} species`}
      />

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard label="Total Species" value={data.total_species} />
        <StatCard label="Owned" value={data.owned_species} />
        <StatCard label="Missing" value={data.missing_species} />
        <StatCard label="Completion" value={`${data.completion_percentage}%`} />
      </div>
    </div>
  );
}
