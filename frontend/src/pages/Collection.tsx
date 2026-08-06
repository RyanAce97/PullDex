import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSpeciesSummary } from "../hooks/useSpeciesSummary";
import {
  useAddSpeciesToCollection,
  useRemoveSpeciesFromCollection,
} from "../hooks/useCollection";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ProgressBar } from "../components/ProgressBar";
import type { SpeciesSummaryRead } from "../types";

type OwnershipFilter = "all" | "owned" | "missing";

export function Collection() {
  const { data, isLoading, error } = useSpeciesSummary();
  const navigate = useNavigate();
  const addMutation = useAddSpeciesToCollection();
  const removeMutation = useRemoveSpeciesFromCollection();

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<OwnershipFilter>("all");
  const [pendingIds, setPendingIds] = useState<Set<number>>(() => new Set());

  const progress = useMemo(() => {
    if (!data) return null;
    const total = data.length;
    const owned = data.filter((s) => s.owned).length;
    const missing = total - owned;
    const percentage = total > 0 ? Math.round((owned / total) * 1000) / 10 : 0;
    return { total, owned, missing, percentage };
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    let result = data;

    if (filter === "owned") {
      result = result.filter((s) => s.owned);
    } else if (filter === "missing") {
      result = result.filter((s) => !s.owned);
    }

    if (search.trim()) {
      const term = search.toLowerCase().trim();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(term) ||
          String(s.national_dex_number).includes(term),
      );
    }

    return result;
  }, [data, filter, search]);

  function handleToggle(species: SpeciesSummaryRead) {
    if (pendingIds.has(species.species_id)) return;

    setPendingIds((prev) => new Set(prev).add(species.species_id));

    const onSettled = () => {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(species.species_id);
        return next;
      });
    };

    if (species.owned) {
      removeMutation.mutate(species.species_id, { onSettled });
    } else {
      addMutation.mutate(species.species_id, { onSettled });
    }
  }

  if (isLoading) return <LoadingSpinner message="Loading collection..." />;
  if (error) return <ErrorState message="Failed to load collection data." />;
  if (!data || !progress) return null;

  if (data.length === 0) {
    return <EmptyState icon="📋" message="No species data yet. Import data to get started." />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">My Collection</h2>
        <p className="text-sm text-gray-500 mt-1">
          {progress.owned} owned • {progress.missing} missing
        </p>
      </div>

      <ProgressBar
        percentage={progress.percentage}
        label={`${progress.owned} / ${progress.total} species`}
      />

      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search by name or dex #..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label="Search species"
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as OwnershipFilter)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label="Filter by ownership"
        >
          <option value="all">All ({progress.total})</option>
          <option value="owned">Owned ({progress.owned})</option>
          <option value="missing">Missing ({progress.missing})</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon="🔍" message="No species match your filters." />
      ) : (
        <>
          <p className="text-sm text-gray-500">Showing {filtered.length} species</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {filtered.map((s) => (
              <CollectionSpeciesCard
                key={s.species_id}
                species={s}
                isPending={pendingIds.has(s.species_id)}
                onToggle={() => handleToggle(s)}
                onDetail={() => navigate(`/pokedex/${s.species_id}`)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

interface CollectionSpeciesCardProps {
  species: SpeciesSummaryRead;
  isPending: boolean;
  onToggle: () => void;
  onDetail: () => void;
}

function CollectionSpeciesCard({ species, isPending, onToggle, onDetail }: CollectionSpeciesCardProps) {
  return (
    <div
      className={`rounded-lg border p-3 transition-colors ${
        species.owned ? "bg-green-50 border-green-200" : "bg-white border-gray-200"
      }`}
    >
      <div
        className="flex items-center gap-3 cursor-pointer"
        onClick={onDetail}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onDetail(); }
        }}
      >
        <span
          className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-mono font-bold ${
            species.owned ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
          }`}
        >
          #{species.national_dex_number}
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 capitalize truncate">{species.name}</p>
          {species.generation !== null && (
            <p className="text-xs text-gray-500">Gen {species.generation}</p>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <button
          onClick={onToggle}
          disabled={isPending}
          className={`text-xs font-semibold px-3 py-1.5 rounded-md transition-colors disabled:opacity-50 ${
            species.owned
              ? "bg-red-100 text-red-700 hover:bg-red-200"
              : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
          }`}
        >
          {isPending ? "..." : species.owned ? "Remove" : "Add"}
        </button>
        <button
          onClick={onDetail}
          className="text-xs text-gray-500 hover:text-indigo-600"
        >
          Details →
        </button>
      </div>
    </div>
  );
}
