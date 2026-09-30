import { useMemo, useState } from "react";
import {
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { rankSpeciesSearch, type SpeciesOwnership } from "@pulldex/shared";

import { Screen, LoadingState, OwnershipBadge } from "../../src/components/ui";
import { useMutation, useSpeciesOwnership } from "../../src/hooks";
import { toggleSpeciesOwnership } from "../../src/db/repository";
import { useTheme } from "../../src/theme";

export default function CardShowMode() {
  const t = useTheme();
  const { rows, loading } = useSpeciesOwnership();
  const mutate = useMutation();

  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<SpeciesOwnership | null>(null);
  const [recentIds, setRecentIds] = useState<number[]>([]);

  const results = useMemo(() => (rows ? rankSpeciesSearch(rows, query, 25) : []), [rows, query]);

  // Keep the selected card's ownership fresh after a toggle.
  const liveSelected = useMemo(() => {
    if (!selected || !rows) return selected;
    return rows.find((r) => r.species.id === selected.species.id) ?? selected;
  }, [selected, rows]);

  const recents = useMemo(() => {
    if (!rows) return [];
    return recentIds
      .map((id) => rows.find((r) => r.species.id === id))
      .filter((r): r is SpeciesOwnership => !!r);
  }, [recentIds, rows]);

  function selectSpecies(row: SpeciesOwnership) {
    setSelected(row);
    setQuery("");
    setRecentIds((prev) => [row.species.id, ...prev.filter((id) => id !== row.species.id)].slice(0, 8));
  }

  async function toggle(row: SpeciesOwnership) {
    await mutate((db) => toggleSpeciesOwnership(db, row.species.id).then(() => undefined));
  }

  if (loading) {
    return (
      <Screen>
        <LoadingState message="Loading…" />
      </Screen>
    );
  }

  return (
    <Screen style={{ padding: 16 }}>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search Pokémon or Dex #"
        placeholderTextColor={t.textMuted}
        autoCorrect={false}
        autoCapitalize="none"
        style={[styles.search, { backgroundColor: t.card, borderColor: t.border, color: t.text }]}
      />

      {/* Search results */}
      {query.trim().length > 0 ? (
        <FlatList
          data={results}
          keyExtractor={(r) => String(r.species.id)}
          keyboardShouldPersistTaps="handled"
          renderItem={({ item }) => (
            <Pressable
              onPress={() => selectSpecies(item)}
              style={[styles.row, { backgroundColor: t.card, borderColor: t.border }]}
            >
              <Text style={[styles.dex, { color: t.textMuted }]}>
                #{String(item.species.national_dex_number).padStart(4, "0")}
              </Text>
              <Text style={[styles.name, { color: t.text }]}>{item.species.name}</Text>
              <View style={{ flex: 1 }} />
              <OwnershipBadge owned={item.owned} />
            </Pressable>
          )}
          ListEmptyComponent={
            <Text style={[styles.muted, { color: t.textMuted }]}>No Pokémon found.</Text>
          }
        />
      ) : liveSelected ? (
        <SelectedCard row={liveSelected} onToggle={() => toggle(liveSelected)} />
      ) : (
        <View style={{ flex: 1 }}>
          <Text style={[styles.hint, { color: t.textMuted }]}>
            Search a Pokémon to instantly see if you own it.
          </Text>
          {recents.length > 0 && (
            <>
              <Text style={[styles.section, { color: t.textMuted }]}>Recent</Text>
              {recents.map((r) => (
                <Pressable
                  key={r.species.id}
                  onPress={() => selectSpecies(r)}
                  style={[styles.row, { backgroundColor: t.card, borderColor: t.border }]}
                >
                  <Text style={[styles.dex, { color: t.textMuted }]}>
                    #{String(r.species.national_dex_number).padStart(4, "0")}
                  </Text>
                  <Text style={[styles.name, { color: t.text }]}>{r.species.name}</Text>
                  <View style={{ flex: 1 }} />
                  <OwnershipBadge owned={r.owned} />
                </Pressable>
              ))}
            </>
          )}
        </View>
      )}
    </Screen>
  );
}

function SelectedCard({ row, onToggle }: { row: SpeciesOwnership; onToggle: () => void }) {
  const t = useTheme();
  return (
    <View style={styles.selectedWrap}>
      <View style={[styles.selected, { backgroundColor: t.card, borderColor: t.border }]}>
        <Text style={[styles.dexBig, { color: t.textMuted }]}>
          #{String(row.species.national_dex_number).padStart(4, "0")}
        </Text>
        <Text style={[styles.nameBig, { color: t.text }]}>{row.species.name}</Text>
        <OwnershipBadge owned={row.owned} large />
        {row.owned && (
          <Text style={[styles.muted, { color: t.textMuted }]}>
            {row.ownedCardCount} card{row.ownedCardCount === 1 ? "" : "s"} tracked
          </Text>
        )}
      </View>
      <Pressable
        onPress={onToggle}
        style={[
          styles.toggle,
          { backgroundColor: row.owned ? t.missingBg : t.accent },
        ]}
      >
        <Text style={{ color: row.owned ? t.missing : t.accentText, fontWeight: "800", fontSize: 16 }}>
          {row.owned ? "Remove from collection" : "Mark as owned"}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  search: { borderWidth: 1, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 14, fontSize: 18, marginBottom: 12 },
  row: { flexDirection: "row", alignItems: "center", gap: 10, borderWidth: 1, borderRadius: 10, padding: 12, marginBottom: 8 },
  dex: { fontVariant: ["tabular-nums"], fontSize: 12 },
  name: { fontSize: 16, fontWeight: "600", textTransform: "capitalize" },
  muted: { fontSize: 13 },
  hint: { fontSize: 15, textAlign: "center", marginTop: 24 },
  section: { fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 16, marginBottom: 8 },
  selectedWrap: { flex: 1, justifyContent: "space-between", paddingBottom: 16 },
  selected: { borderWidth: 1, borderRadius: 16, padding: 24, alignItems: "center", gap: 12, marginTop: 12 },
  dexBig: { fontSize: 16, fontVariant: ["tabular-nums"] },
  nameBig: { fontSize: 32, fontWeight: "800", textTransform: "capitalize", textAlign: "center" },
  toggle: { borderRadius: 14, paddingVertical: 18, alignItems: "center" },
});
