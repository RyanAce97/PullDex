import { useState } from "react";

import { useRecommendations } from "../hooks/useRecommendations";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { RecommendationCard } from "../components/RecommendationCard";
import type { RecommendationResponse } from "../types";

type TabKey = "sets" | "promos";

export function Recommendations() {
  // Sets is the default/initial tab.
  const [activeTab, setActiveTab] = useState<TabKey>("sets");

  // Both queries use the SAME recommendation logic/component; they differ only
  // by the promo flag (and therefore the query key + source pool). Keeping both
  // mounted means switching tabs is instant and cached independently, but only
  // the selected tab's list is rendered below.
  const sets = useRecommendations(10, false);
  const promos = useRecommendations(10, true);

  // Gate the page shell on the default (Sets) query, preserving the existing
  // top-of-page loading/error behaviour.
  if (sets.isLoading) {
    return <LoadingSpinner message="Loading recommendations..." />;
  }
  if (sets.error) {
    return <ErrorState message="Failed to load recommendations." />;
  }
  if (!sets.data) return null;

  const active = activeTab === "sets" ? sets : promos;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Pack Recommendations</h2>
        <p className="text-sm text-gray-500 mt-1">
          {sets.data.owned_species} / {sets.data.total_species} species owned •{" "}
          {sets.data.total_missing_species} missing
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-1" role="tablist" aria-label="Recommendation type">
          <TabButton
            label="Sets"
            isActive={activeTab === "sets"}
            onClick={() => setActiveTab("sets")}
          />
          <TabButton
            label="Promos"
            isActive={activeTab === "promos"}
            onClick={() => setActiveTab("promos")}
          />
        </nav>
      </div>

      {/* Only the selected tab's content is rendered. */}
      <div
        role="tabpanel"
        data-testid={`recommendation-panel-${activeTab}`}
      >
        <TabPanel
          data={active.data}
          isLoading={active.isLoading}
          isError={Boolean(active.error)}
          emptyIcon={activeTab === "promos" ? "✨" : "🎉"}
          emptyMessage={
            activeTab === "promos"
              ? "No promo recommendations available yet."
              : "Living Dex complete! No set recommendations needed."
          }
          loadingLabel={activeTab === "promos" ? "promos" : "sets"}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function TabButton({
  label,
  isActive,
  onClick,
}: {
  label: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      onClick={onClick}
      data-testid={`recommendation-tab-${label.toLowerCase()}`}
      className={`px-4 py-2 -mb-px text-sm font-medium border-b-2 transition-colors ${
        isActive
          ? "border-indigo-600 text-indigo-700"
          : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
      }`}
    >
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------

interface TabPanelProps {
  data: RecommendationResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  emptyIcon: string;
  emptyMessage: string;
  loadingLabel: string;
}

function TabPanel({ data, isLoading, isError, emptyIcon, emptyMessage, loadingLabel }: TabPanelProps) {
  if (isLoading) {
    return <LoadingSpinner message={`Loading ${loadingLabel}...`} />;
  }
  if (isError) {
    return <ErrorState message={`Failed to load ${loadingLabel}.`} />;
  }
  if (!data || data.recommendations.length === 0) {
    return <EmptyState icon={emptyIcon} message={emptyMessage} />;
  }
  return (
    <div className="space-y-4">
      {data.recommendations.map((rec) => (
        <RecommendationCard key={rec.set_id} rec={rec} />
      ))}
    </div>
  );
}
