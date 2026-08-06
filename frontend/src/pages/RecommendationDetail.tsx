import { useNavigate, useParams } from "react-router-dom";
import { useRecommendationSpecies } from "../hooks/useRecommendationSpecies";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";

export function RecommendationDetail() {
  const { setId } = useParams<{ setId: string }>();
  const navigate = useNavigate();

  const numericSetId = Number(setId);

  const { data, isLoading, error } = useRecommendationSpecies(numericSetId);

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate("/recommendations")}
        className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
      >
        ← Back to Recommendations
      </button>

      <h2 className="text-2xl font-bold">Missing Species in Set</h2>

      {isLoading && <LoadingSpinner message="Loading missing species..." />}

      {error && <ErrorState message="Failed to load species data." />}

      {data && data.length === 0 && (
        <EmptyState
          icon="✅"
          message="No missing species in this set — you already own them all!"
        />
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {data.map((species) => (
            <div
              key={species.id}
              className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg p-3"
            >
              <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-gray-100 text-gray-700 text-sm font-mono font-bold">
                #{species.national_dex_number}
              </span>
              <div>
                <p className="font-medium text-gray-900 capitalize">
                  {species.name}
                </p>
                {species.generation !== null && (
                  <p className="text-xs text-gray-500">
                    Gen {species.generation}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
