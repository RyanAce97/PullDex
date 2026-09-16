import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useSetSummaries } from "../hooks/useSetSummaries";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingSpinner } from "./LoadingSpinner";
import type { SetSummaryRead } from "../types";

type SortOrder = "name" | "missing" | "coverage" | "density" | "date";

interface SetCatalogueProps {
  /** Page heading, e.g. "Set Explorer" / "Promo Explorer". */
  title: string;
  /**
   * Which pool to show. When "promos", only promotional sets
   * (``is_promo === true``) are shown; when "sets", only non-promotional sets.
   * Filtering uses the existing ``is_promo`` field — no hard-coded set IDs.
   */
  pool: "sets" | "promos";
  /** Route to navigate back from when drilling into a set. */
  fromPath: string;
  /** Noun used in copy, e.g. "sets" / "promos". */
  noun: string;
  /** Empty-state shown when the (filtered) catalogue is empty. */
  emptyIcon: string;
  emptyMessage: string;
  /** data-testid for the catalogue root (aids testing). */
  testId?: string;
}

/**
 * Shared set-catalogue browser (extracted from the original Set Explorer).
 *
 * Reused by both the dedicated Sets page (non-promo) and the Promos page
 * (promo-only). The ONLY difference between them is the ``pool`` filter on the
 * existing ``is_promo`` field. This is catalogue *browsing* — it is deliberately
 * separate from the recommendation engine.
 */
export function SetCatalogue({
  title,
  pool,
  fromPath,
  noun,
  emptyIcon,
  emptyMessage,
  testId,
}: SetCatalogueProps) {
  const { data, isLoading, error } = useSetSummaries();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortOrder>("missing");

  // Pool filter first (promo vs non-promo), then search/sort.
  const pooled = useMemo(() => {
    if (!data) return [];
    const wantPromo = pool === "promos";
    return data.filter((s) => s.is_promo === wantPromo);
  }, [data, pool]);

  const filtered = useMemo(() => {
    let result = pooled;

    if (search.trim()) {
      const term = search.toLowerCase().trim();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(term) ||
          s.series.toLowerCase().includes(term),
      );
    }

    const sorted = [...result];
    switch (sort) {
      case "name":
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case "missing":
        sorted.sort((a, b) => b.missing_species_in_set - a.missing_species_in_set);
        break;
      case "coverage":
        sorted.sort((a, b) => b.total_species_in_set - a.total_species_in_set);
        break;
      case "density": {
        const density = (s: SetSummaryRead) =>
          s.total_species_in_set > 0 ? s.missing_species_in_set / s.total_species_in_set : 0;
        sorted.sort((a, b) => density(b) - density(a));
        break;
      }
      case "date":
        sorted.sort((a, b) => {
          if (!a.release_date && !b.release_date) return 0;
          if (!a.release_date) return 1;
          if (!b.release_date) return -1;
          return b.release_date.localeCompare(a.release_date);
        });
        break;
    }

    return sorted;
  }, [pooled, search, sort]);

  if (isLoading) {
    return <LoadingSpinner message={`Loading ${noun}...`} />;
  }

  if (error) {
    return <ErrorState message={`Failed to load ${noun} data.`} />;
  }

  if (!data) return null;

  if (pooled.length === 0) {
    return <EmptyState icon={emptyIcon} message={emptyMessage} />;
  }

  return (
    <div className="space-y-6" data-testid={testId}>
      <div>
        <h2 className="text-2xl font-bold">{title}</h2>
        <p className="text-sm text-gray-500 mt-1">
          {pooled.length} {noun}
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder={`Search by ${noun === "promos" ? "promo" : "set"} name or series...`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label={`Search ${noun}`}
        />
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortOrder)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label="Sort order"
        >
          <option value="missing">Most missing species</option>
          <option value="coverage">Most total species</option>
          <option value="density">Highest density</option>
          <option value="date">Newest first</option>
          <option value="name">Name (A–Z)</option>
        </select>
      </div>

      {/* Results */}
      {filtered.length === 0 ? (
        <EmptyState icon="🔍" message={`No ${noun} match your search.`} />
      ) : (
        <>
          <p className="text-sm text-gray-500">
            Showing {filtered.length} {noun}
          </p>
          <div className="space-y-3">
            {filtered.map((s) => (
              <SetSummaryCard
                key={s.set_id}
                set={s}
                onClick={() =>
                  navigate(`/recommendations/${s.set_id}`, { state: { from: fromPath } })
                }
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

interface SetSummaryCardProps {
  set: SetSummaryRead;
  onClick: () => void;
}

export function SetSummaryCard({ set, onClick }: SetSummaryCardProps) {
  const coveragePercent =
    set.total_species_in_set > 0
      ? Math.round((set.owned_species_in_set / set.total_species_in_set) * 100)
      : 0;

  return (
    <div
      className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm cursor-pointer hover:border-indigo-300 hover:shadow-md transition-colors"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{set.name}</h3>
          <p className="text-sm text-gray-500">
            {set.series}
            {set.release_date && ` • ${set.release_date}`}
          </p>
        </div>
        <div className="text-right">
          {set.missing_species_in_set > 0 ? (
            <>
              <p className="text-lg font-bold text-indigo-600">
                {set.missing_species_in_set}
              </p>
              <p className="text-xs text-gray-500">missing</p>
            </>
          ) : (
            <span className="text-xs font-semibold px-2 py-1 rounded-full bg-green-100 text-green-700">
              ✓ Complete
            </span>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
        <span>
          {set.owned_species_in_set} / {set.total_species_in_set} species owned
        </span>
        <span>{coveragePercent}% complete</span>
      </div>
    </div>
  );
}
