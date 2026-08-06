import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePokedex } from "../hooks/usePokedex";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ProgressBar } from "../components/ProgressBar";
import { SpeciesListItem } from "../components/SpeciesListItem";
import type { PokemonSpeciesRead } from "../types";

type OwnershipFilter = "all" | "owned" | "missing";
type SortOrder = "dex" | "name";

export function Pokedex() {
  const { data, isLoading, error } = usePokedex();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<OwnershipFilter>("all");
  const [sort, setSort] = useState<SortOrder>("dex");

  const filtered = useMemo(() => {
    if (!data) return [];

    let result: PokemonSpeciesRead[] = data.species;

    // Filter by ownership
    if (filter === "owned") {
      result = result.filter((s) => !data.missingIds.has(s.id));
    } else if (filter === "missing") {
      result = result.filter((s) => data.missingIds.has(s.id));
    }

    // Filter by name search
    if (search.trim()) {
      const term = search.toLowerCase().trim();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(term) ||
          String(s.national_dex_number).includes(term),
      );
    }

    // Sort
    if (sort === "name") {
      result = [...result].sort((a, b) => a.name.localeCompare(b.name));
    } else {
      result = [...result].sort(
        (a, b) => a.national_dex_number - b.national_dex_number,
      );
    }

    return result;
  }, [data, search, filter, sort]);

  if (isLoading) {
    return <LoadingSpinner message="Loading Pokédex..." />;
  }

  if (error) {
    return <ErrorState message="Failed to load Pokédex data." />;
  }

  if (!data) return null;

  const { missingIds, progress } = data;

  if (data.species.length === 0) {
    return (
      <EmptyState
        icon="📋"
        message="No species imported yet. Run the importer first."
      />
    );
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

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search by name or dex #..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label="Search species"
        />
        <FilterSelect value={filter} onChange={setFilter} />
        <SortSelect value={sort} onChange={setSort} />
      </div>

      {/* Results */}
      {filtered.length === 0 ? (
        <EmptyState icon="🔍" message="No species match your filters." />
      ) : (
        <>
          <p className="text-sm text-gray-500">
            Showing {filtered.length} species
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {filtered.map((s) => (
              <SpeciesListItem
                key={s.id}
                species={s}
                owned={!missingIds.has(s.id)}
                onClick={() => navigate(`/pokedex/${s.id}`)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Filter Select ────────────────────────────────────────────────────────────

interface FilterSelectProps {
  value: OwnershipFilter;
  onChange: (value: OwnershipFilter) => void;
}

function FilterSelect({ value, onChange }: FilterSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as OwnershipFilter)}
      className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      aria-label="Filter by ownership"
    >
      <option value="all">All</option>
      <option value="owned">Owned</option>
      <option value="missing">Missing</option>
    </select>
  );
}

// ─── Sort Select ──────────────────────────────────────────────────────────────

interface SortSelectProps {
  value: SortOrder;
  onChange: (value: SortOrder) => void;
}

function SortSelect({ value, onChange }: SortSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as SortOrder)}
      className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      aria-label="Sort order"
    >
      <option value="dex">Dex # (ascending)</option>
      <option value="name">Name (A–Z)</option>
    </select>
  );
}
