import { SetCatalogue } from "../components/SetCatalogue";

/**
 * Dedicated Promos page — the promotional set catalogue.
 *
 * Reuses the shared SetCatalogue browser, filtered to promotional sets only
 * (``is_promo === true``). Uses the existing ``is_promo`` field; no set IDs are
 * hard-coded.
 */
export function Promos() {
  return (
    <SetCatalogue
      title="Promo Explorer"
      pool="promos"
      fromPath="/promos"
      noun="promos"
      emptyIcon="✨"
      emptyMessage="No promo sets available yet."
      testId="set-catalogue-promos"
    />
  );
}
