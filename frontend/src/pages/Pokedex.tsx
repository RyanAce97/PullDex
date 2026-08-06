import { usePokedex } from "../hooks/usePokedex";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ProgressBar } from "../components/ProgressBar";
import { SpeciesListItem } from "../components/SpeciesListItem";

export function Pokedex() {
  const { data, isLoading, error } = usePokedex();

  if (isLoading) {
    return <LoadingSpinner message="Loading Pokédex..." />;
  }

  if (error) {
    return <ErrorState message="Failed to load Pokédex data." />;
  }

  if (!data) return null;

  const { species, missingIds, progress } = data;

  if (species.length === 0) {
    return <EmptyState icon="📋" message="No species imported yet. Run the importer first." />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Pokédex</h2>
        <p className="text-sm text-gray-500 mt-1">
          {progress.owned_species} owned • {progress.missing_species} missing
        </p>
      </div>

      <ProgressBar
        percentage={progress.completion_percentage}
        label={`${progress.owned_species} / ${progress.total_species} species`}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {species.map((s) => (
          <SpeciesListItem
            key={s.id}
            species={s}
            owned={!missingIds.has(s.id)}
          />
        ))}
      </div>
    </div>
  );
}
