import { useQuery } from "@tanstack/react-query";
import { getRecommendations } from "../api/recommendations";
import type { SetRecommendation } from "../types";

export function Recommendations() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => getRecommendations(10),
  });

  if (isLoading) {
    return <p className="text-gray-500">Loading recommendations...</p>;
  }

  if (error) {
    return (
      <p className="text-red-600">
        Failed to load recommendations. Is the backend running on :8000?
      </p>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Pack Recommendations</h2>
        <p className="text-sm text-gray-500 mt-1">
          {data.owned_species} / {data.total_species} species owned •{" "}
          {data.total_missing_species} missing
        </p>
      </div>

      {data.recommendations.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <p className="text-green-700 font-medium">
            🎉 Living Dex complete! No recommendations needed.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.recommendations.map((rec) => (
            <RecommendationCard key={rec.set_id} rec={rec} />
          ))}
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ rec }: { rec: SetRecommendation }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 text-sm font-bold">
              {rec.rank}
            </span>
            <h3 className="text-lg font-semibold text-gray-900">
              {rec.set_name}
            </h3>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {rec.series}
            {rec.release_date && ` • ${rec.release_date}`}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-indigo-600">
            {rec.missing_species_count}
          </p>
          <p className="text-xs text-gray-500">missing species</p>
        </div>
      </div>
      <div className="mt-3 flex gap-4 text-sm text-gray-600">
        <span>
          Coverage: <strong>{rec.coverage_percentage}%</strong>
        </span>
        <span>
          Density: <strong>{rec.missing_species_density_percentage}%</strong>
        </span>
        <span>
          {rec.total_species_in_set} species • {rec.total_cards_in_set} cards
        </span>
      </div>
    </div>
  );
}
