import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { PokemonSpecies, SetRecommendation } from "@pulldex/shared";

import { Screen, LoadingState, EmptyState } from "../../src/components/ui";
import { useDatabase } from "../../src/db/provider";
import { getMissingSpeciesInSet, getSetRecommendations } from "../../src/db/repository";
import { useDataVersionValue, useSummary } from "../../src/hooks";
import { useTheme } from "../../src/theme";

const TAB_BAR_ALLOWANCE = 64;
type Pool = "sets" | "promos";

export default function Recommendations() {
  const t = useTheme();
  const db = useDatabase();
  const insets = useSafeAreaInsets();
  const dataVersion = useDataVersionValue();
  const summary = useSummary();

  const [pool, setPool] = useState<Pool>("sets");
  const [recs, setRecs] = useState<SetRecommendation[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!db) return;
    setRecs(null);
    getSetRecommendations(db, pool === "promos", 10).then((r) => !cancelled && setRecs(r.recommendations));
    return () => {
      cancelled = true;
    };
  }, [db, pool, dataVersion]);

  return (
    <Screen style={{ padding: 16 }}>
      <Text style={[styles.h1, { color: t.text }]}>Pack Recommendations</Text>
      {summary && (
        <Text style={[styles.sub, { color: t.textMuted }]}>
          {summary.progress.ownedSpecies} / {summary.progress.totalSpecies} species owned ·{" "}
          {summary.progress.missingSpecies} missing
        </Text>
      )}

      <View style={styles.tabs}>
        <TabButton label="Sets" active={pool === "sets"} onPress={() => setPool("sets")} />
        <TabButton label="Promos" active={pool === "promos"} onPress={() => setPool("promos")} />
      </View>

      {!recs ? (
        <LoadingState message={`Loading ${pool}…`} />
      ) : recs.length === 0 ? (
        <EmptyState
          icon={pool === "promos" ? "✨" : "🎉"}
          message={
            pool === "promos"
              ? "No promo recommendations available yet."
              : "Living Dex complete! No set recommendations needed."
          }
        />
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + TAB_BAR_ALLOWANCE, gap: 12 }}>
          {recs.map((rec) => (
            <RecommendationCard key={rec.set_id} rec={rec} />
          ))}
        </ScrollView>
      )}
    </Screen>
  );
}

function RecommendationCard({ rec }: { rec: SetRecommendation }) {
  const t = useTheme();
  const db = useDatabase();
  const [expanded, setExpanded] = useState(false);
  const [missing, setMissing] = useState<PokemonSpecies[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!expanded || !db || missing) return;
    getMissingSpeciesInSet(db, rec.set_id).then((m) => !cancelled && setMissing(m));
    return () => {
      cancelled = true;
    };
  }, [expanded, db, rec.set_id, missing]);

  const preview = useMemo(() => (missing ? missing.slice(0, 12) : []), [missing]);

  return (
    <View style={[styles.card, { backgroundColor: t.card, borderColor: t.border }]}>
      <View style={styles.cardHeader}>
        <View style={styles.rankRow}>
          <View style={[styles.rankBadge, { backgroundColor: t.accent }]}>
            <Text style={{ color: t.accentText, fontWeight: "800" }}>{rec.rank}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.setName, { color: t.text }]} numberOfLines={1}>{rec.set_name}</Text>
            <Text style={[styles.series, { color: t.textMuted }]} numberOfLines={1}>
              {rec.series}{rec.release_date ? ` · ${rec.release_date}` : ""}
            </Text>
          </View>
          <View style={{ alignItems: "flex-end" }}>
            <Text style={[styles.missingNum, { color: t.accent }]}>{rec.missing_species_count}</Text>
            <Text style={[styles.missingLabel, { color: t.textMuted }]}>missing</Text>
          </View>
        </View>

        <View style={styles.statsRow}>
          <Text style={[styles.stat, { color: t.textMuted }]}>
            Covers <Text style={{ color: t.text, fontWeight: "700" }}>{rec.coverage_percentage}%</Text> of missing
          </Text>
          <Text style={[styles.stat, { color: t.textMuted }]}>
            Density <Text style={{ color: t.text, fontWeight: "700" }}>{rec.missing_species_density_percentage}%</Text>
          </Text>
        </View>

        <Pressable onPress={() => setExpanded((e) => !e)} hitSlop={6}>
          <Text style={{ color: t.accent, fontWeight: "700", fontSize: 13 }}>
            {expanded ? "Hide missing Pokémon ▲" : "View missing Pokémon ▼"}
          </Text>
        </Pressable>
      </View>

      {expanded && (
        <View style={[styles.expand, { borderTopColor: t.border }]}>
          {!missing ? (
            <Text style={{ color: t.textMuted }}>Loading…</Text>
          ) : (
            <View style={styles.chips}>
              {preview.map((s) => (
                <View key={s.id} style={[styles.chip, { borderColor: t.border, backgroundColor: t.cardAlt }]}>
                  <Text style={{ color: t.textMuted, fontSize: 11 }}>
                    #{s.national_dex_number}
                  </Text>
                  <Text style={{ color: t.text, fontSize: 12, fontWeight: "600", textTransform: "capitalize" }}>
                    {s.name}
                  </Text>
                </View>
              ))}
              {missing.length > preview.length && (
                <Text style={{ color: t.textMuted, fontSize: 12, alignSelf: "center" }}>
                  +{missing.length - preview.length} more
                </Text>
              )}
            </View>
          )}
        </View>
      )}
    </View>
  );
}

function TabButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  const t = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={[styles.tab, { borderColor: active ? t.accent : t.border, backgroundColor: active ? t.accent : t.card }]}
    >
      <Text style={{ color: active ? t.accentText : t.text, fontWeight: "700" }}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  h1: { fontSize: 24, fontWeight: "800" },
  sub: { fontSize: 13, marginTop: 2, marginBottom: 12 },
  tabs: { flexDirection: "row", gap: 8, marginBottom: 12 },
  tab: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 18, paddingVertical: 8 },
  card: { borderWidth: 1, borderRadius: 12, overflow: "hidden" },
  cardHeader: { padding: 14, gap: 10 },
  rankRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  rankBadge: { width: 28, height: 28, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  setName: { fontSize: 16, fontWeight: "700" },
  series: { fontSize: 12, marginTop: 1 },
  missingNum: { fontSize: 22, fontWeight: "800" },
  missingLabel: { fontSize: 10 },
  statsRow: { flexDirection: "row", gap: 16, flexWrap: "wrap" },
  stat: { fontSize: 13 },
  expand: { borderTopWidth: 1, padding: 14 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: { flexDirection: "row", alignItems: "center", gap: 4, borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
});
