import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSpeciesSummary } from "../hooks/useSpeciesSummary";
import {
  useAddSpeciesToCollection,
  useRemoveSpeciesCascade,
} from "../hooks/useCollection";
import { getCardEntriesForSpecies } from "../api/collection";
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
  const removeCascade = useRemoveSpeciesCascade();

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<OwnershipFilter>("all");
  const [pendingIds, setPendingIds] = useState<Set<number>>(() => new Set());

  // Cascade removal confirmation state
  const [confirmRemoval, setConfirmRemoval] = useState<{
    species: SpeciesSummaryRead;
    cardCount: number;
  } | null>(null);

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

  async function handleRemove(species: SpeciesSummaryRead) {
    if (pendingIds.has(species.species_id)) return;

    // Check if there are card entries for this species
    try {
      const cardEntries = await getCardEntriesForSpecies(species.species_id);
      if (cardEntries.length > 0) {
        // Show confirmation dialog
        setConfirmRemoval({ species, cardCount: cardEntries.length });
        return;
      }
    } catch {
      // If we can't check, just try the cascade removal anyway
    }

    // No card entries — simple removal
    setPendingIds((prev) => new Set(prev).add(species.species_id));
    removeCascade.mutate(species.species_id, {
      onSettled: () => {
        setPendingIds((prev) => { const n = new Set(prev); n.delete(species.species_id); return n; });
      },
    });
  }

  function handleConfirmCascadeRemoval() {
    if (!confirmRemoval) return;
    const speciesId = confirmRemoval.species.species_id;

    setPendingIds((prev) => new Set(prev).add(speciesId));
    setConfirmRemoval(null);

    removeCascade.mutate(speciesId, {
      onSettled: () => {
        setPendingIds((prev) => { const n = new Set(prev); n.delete(speciesId); return n; });
      },
    });
  }

  function handleAdd(species: SpeciesSummaryRead) {
    if (pendingIds.has(species.species_id)) return;
    setPendingIds((prev) => new Set(prev).add(species.species_id));
    addMutation.mutate(species.species_id, {
      onSettled: () => {
        setPendingIds((prev) => { const n = new Set(prev); n.delete(species.species_id); return n; });
      },
    });
  }

  function handleToggle(species: SpeciesSummaryRead) {
    if (species.owned) {
      handleRemove(species);
    } else {
      handleAdd(species);
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

      {/* Cascade removal confirmation dialog */}
      {confirmRemoval && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setConfirmRemoval(null); }}
        >
          <div className="bg-white rounded-xl shadow-2xl max-w-sm w-full mx-4 p-6 space-y-4">
            <h3 className="text-lg font-bold text-gray-900">
              Remove {confirmRemoval.species.name}?
            </h3>
            <p className="text-sm text-gray-600">
              This will remove <span className="capitalize font-medium">{confirmRemoval.species.name}</span> and
              all <strong>{confirmRemoval.cardCount}</strong> card {confirmRemoval.cardCount === 1 ? "entry" : "entries"} associated
              with it from your collection.
            </p>
            <p className="text-xs text-red-600">
              This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => setConfirmRemoval(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmCascadeRemoval}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
              >
                Remove
              </button>
            </div>
          </div>
        </div>
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
