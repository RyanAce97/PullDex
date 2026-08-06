import { useNavigate } from "react-router-dom";
import { useRecommendations } from "../hooks/useRecommendations";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { RecommendationCard } from "../components/RecommendationCard";

export function Recommendations() {
  const navigate = useNavigate();

  const { data, isLoading, error } = useRecommendations(10);

  if (isLoading) {
    return <LoadingSpinner message="Loading recommendations..." />;
  }

  if (error) {
    return <ErrorState message="Failed to load recommendations." />;
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
        <EmptyState
          icon="🎉"
          message="Living Dex complete! No recommendations needed."
        />
      ) : (
        <div className="space-y-4">
          {data.recommendations.map((rec) => (
            <RecommendationCard
              key={rec.set_id}
              rec={rec}
              onClick={() => navigate(`/recommendations/${rec.set_id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
