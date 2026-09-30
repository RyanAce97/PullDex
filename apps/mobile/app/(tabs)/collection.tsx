import { useMemo, useState } from "react";
import { useRouter } from "expo-router";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { filterSpecies, type OwnershipFilter, type SpeciesOwnership } from "@pulldex/shared";

import { Screen, LoadingState, EmptyState, ProgressBar } from "../../src/components/ui";
import { useMutation, useProgress, useSpeciesOwnership } from "../../src/hooks";
import { toggleSpeciesOwnership } from "../../src/db/repository";
import { useTheme } from "../../src/theme";

const FILTERS: OwnershipFilter[] = ["all", "owned", "missing"];

export default function Collection() {
  const t = useTheme();
  const router = useRouter();
  const { rows, loading, error } = useSpeciesOwnership();
  const progress = useProgress();
  const mutate = useMutation();

  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<OwnershipFilter>("all");

  const filtered = useMemo(
    () => (rows ? filterSpecies(rows, query, filter) : []),
    [rows, query, filter],
  );

  if (loading) return <Screen><LoadingState message="Loading collection…" /></Screen>;
  if (error) return <Screen><EmptyState icon="⚠️" message={error} /></Screen>;

  return (
    <Screen style={{ padding: 16 }}>
      {progress && (
        <View style={{ marginBottom: 12, gap: 6 }}>
          <ProgressBar percentage={progress.percentage} />
          <Text style={[styles.muted, { color: t.textMuted }]}>
            {progress.ownedSpecies} owned · {progress.missingSpecies} missing · {progress.percentage}%
          </Text>
        </View>
      )}

      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search by name or Dex #"
        placeholderTextColor={t.textMuted}
        autoCorrect={false}
        autoCapitalize="none"
        style={[styles.search, { backgroundColor: t.card, borderColor: t.border, color: t.text }]}
      />

      <View style={styles.filters}>
        {FILTERS.map((f) => (
          <Pressable
            key={f}
            onPress={() => setFilter(f)}
            style={[
              styles.chip,
              { borderColor: t.border, backgroundColor: filter === f ? t.accent : t.card },
            ]}
          >
            <Text style={{ color: filter === f ? t.accentText : t.text, fontWeight: "600", textTransform: "capitalize" }}>
              {f}
            </Text>
          </Pressable>
        ))}
      </View>

      <FlatList
        data={filtered}
        keyExtractor={(r) => String(r.species.id)}
        keyboardShouldPersistTaps="handled"
        initialNumToRender={20}
        windowSize={10}
        renderItem={({ item }) => (
          <SpeciesRow
            row={item}
            onOpen={() => router.push(`/species/${item.species.id}`)}
            onToggle={() => mutate((db) => toggleSpeciesOwnership(db, item.species.id).then(() => undefined))}
          />
        )}
        ListEmptyComponent={<EmptyState message="No Pokémon match your filters." />}
      />
    </Screen>
  );
}

function SpeciesRow({
  row,
  onOpen,
  onToggle,
}: {
  row: SpeciesOwnership;
  onOpen: () => void;
  onToggle: () => void;
}) {
  const t = useTheme();
  return (
    <View
      style={[
        styles.row,
        { backgroundColor: row.owned ? t.ownedBg : t.card, borderColor: t.border },
      ]}
    >
      <Pressable onPress={onOpen} style={styles.rowMain}>
        <Text style={[styles.dex, { color: t.textMuted }]}>
          #{String(row.species.national_dex_number).padStart(4, "0")}
        </Text>
        <Text style={[styles.name, { color: t.text }]}>{row.species.name}</Text>
      </Pressable>
      <Pressable
        onPress={onToggle}
        style={[styles.toggle, { backgroundColor: row.owned ? t.missingBg : t.accent }]}
      >
        <Text style={{ color: row.owned ? t.missing : t.accentText, fontWeight: "700", fontSize: 12 }}>
          {row.owned ? "Remove" : "Add"}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  search: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 16, marginBottom: 10 },
  filters: { flexDirection: "row", gap: 8, marginBottom: 12 },
  chip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 6 },
  row: { flexDirection: "row", alignItems: "center", borderWidth: 1, borderRadius: 10, marginBottom: 8, overflow: "hidden" },
  rowMain: { flex: 1, flexDirection: "row", alignItems: "center", gap: 10, padding: 12 },
  dex: { fontSize: 12, fontVariant: ["tabular-nums"] },
  name: { fontSize: 16, fontWeight: "600", textTransform: "capitalize" },
  toggle: { paddingHorizontal: 14, paddingVertical: 12, alignSelf: "stretch", justifyContent: "center" },
  muted: { fontSize: 13 },
});
