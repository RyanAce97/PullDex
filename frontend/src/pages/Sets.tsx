import { SetCatalogue } from "../components/SetCatalogue";

/**
 * Dedicated Sets page — the non-promotional set catalogue.
 *
 * Reuses the shared SetCatalogue browser, filtered to non-promo sets
 * (``is_promo === false``). Promotional sets are shown on the separate
 * Promos page instead.
 */
export function Sets() {
  return (
    <SetCatalogue
      title="Set Explorer"
      pool="sets"
      fromPath="/sets"
      noun="sets"
      emptyIcon="📦"
      emptyMessage="No sets imported yet."
      testId="set-catalogue-sets"
    />
  );
}
