import type { SetRecommendation } from "../types";

interface RecommendationCardProps {
  rec: SetRecommendation;
  onClick?: () => void;
}

export function RecommendationCard({ rec, onClick }: RecommendationCardProps) {
  return (
    <div
      className={`bg-white rounded-lg border border-gray-200 p-4 shadow-sm transition-colors ${
        onClick ? "cursor-pointer hover:border-indigo-300 hover:shadow-md" : ""
      }`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
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
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
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
