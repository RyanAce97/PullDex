import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useRecommendationSpecies } from "../hooks/useRecommendationSpecies";
import { LoadingSpinner } from "./LoadingSpinner";
import type { MissingSpeciesRead, SetRecommendation } from "../types";

interface RecommendationCardProps {
  rec: SetRecommendation;
}

const PREVIEW_COUNT = 6;

export function RecommendationCard({ rec }: RecommendationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      {/* Header — always visible */}
      <div className="p-4">
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

        {/* Stats row */}
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
          <span>
            Covers <strong>{rec.coverage_percentage}%</strong> of your missing Pokémon
          </span>
          <span>
            Density: <strong>{rec.missing_species_density_percentage}%</strong> useful cards
          </span>
        </div>

        {/* Actions */}
        <div className="mt-3 flex items-center gap-4">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
          >
            {expanded ? "Hide details ▲" : "View details ▼"}
          </button>
          <button
            onClick={() => navigate(`/recommendations/${rec.set_id}`, { state: { from: "/recommendations" } })}
            className="text-sm font-medium text-gray-500 hover:text-gray-700 transition-colors"
          >
            View full recommendation →
          </button>
        </div>
      </div>

      {/* Expandable detail section */}
      {expanded && <ExpandedSpeciesList setId={rec.set_id} />}
    </div>
  );
}

// ---------------------------------------------------------------------------

function ExpandedSpeciesList({ setId }: { setId: number }) {
  const { data, isLoading, error } = useRecommendationSpecies(setId);
  const [showAll, setShowAll] = useState(false);

  if (isLoading) {
    return (
      <div className="px-4 pb-4">
        <LoadingSpinner message="Loading species..." />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="px-4 pb-4">
        <p className="text-sm text-red-600">Failed to load species.</p>
      </div>
    );
  }

  const visible = showAll ? data : data.slice(0, PREVIEW_COUNT);
  const hasMore = data.length > PREVIEW_COUNT;

  return (
    <div className="border-t border-gray-100 bg-gray-50 px-4 py-3">
      <p className="text-xs font-medium text-gray-500 mb-2">
        Missing Pokémon you could find in this set:
      </p>
      <div className="flex flex-wrap gap-2">
        {visible.map((species) => (
          <SpeciesChip key={species.id} species={species} />
        ))}
      </div>
      {hasMore && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-2 text-xs font-medium text-indigo-600 hover:text-indigo-800"
        >
          + {data.length - PREVIEW_COUNT} more Pokémon
        </button>
      )}
      {showAll && hasMore && (
        <button
          onClick={() => setShowAll(false)}
          className="mt-2 text-xs font-medium text-gray-500 hover:text-gray-700"
        >
          Show fewer
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function SpeciesChip({ species }: { species: MissingSpeciesRead }) {
  const navigate = useNavigate();

  return (
    <button
      onClick={() => navigate(`/pokedex/${species.id}`, { state: { from: "/recommendations" } })}
      className="inline-flex items-center gap-1 bg-white border border-gray-200 rounded-full px-2.5 py-1 text-xs text-gray-700 hover:border-indigo-300 hover:shadow-sm transition-colors cursor-pointer"
    >
      <span className="font-mono text-gray-400">#{species.national_dex_number}</span>
      <span className="capitalize font-medium">{species.name}</span>
    </button>
  );
}
