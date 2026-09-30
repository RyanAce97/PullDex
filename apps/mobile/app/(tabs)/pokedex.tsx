import { useMemo, useState } from "react";
import { useRouter } from "expo-router";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { filterSpecies, type SpeciesOwnership } from "@pulldex/shared";

import { Screen, LoadingState, EmptyState, ProgressBar } from "../../src/components/ui";
import { useProgress, useSpeciesOwnership } from "../../src/hooks";
import { useTheme } from "../../src/theme";

export default function Pokedex() {
  const t = useTheme();
  const router = useRouter();
  const { rows, loading, error } = useSpeciesOwnership();
  const progress = useProgress();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => (rows ? filterSpecies(rows, query, "all") : []), [rows, query]);

  if (loading) return <Screen><LoadingState message="Loading Pokédex…" /></Screen>;
  if (error) return <Screen><EmptyState icon="⚠️" message={error} /></Screen>;

  return (
    <Screen style={{ padding: 16 }}>
      {progress && (
        <View style={{ marginBottom: 12, gap: 6 }}>
          <ProgressBar percentage={progress.percentage} />
          <Text style={[styles.muted, { color: t.textMuted }]}>
            {progress.ownedSpecies} / {progress.totalSpecies} caught · {progress.percentage}%
          </Text>
        </View>
      )}
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search Pokédex"
        placeholderTextColor={t.textMuted}
        autoCorrect={false}
        autoCapitalize="none"
        style={[styles.search, { backgroundColor: t.card, borderColor: t.border, color: t.text }]}
      />
      <FlatList
        data={filtered}
        keyExtractor={(r) => String(r.species.id)}
        numColumns={2}
        columnWrapperStyle={{ gap: 8 }}
        keyboardShouldPersistTaps="handled"
        initialNumToRender={20}
        renderItem={({ item }) => (
          <PokedexCell row={item} onOpen={() => router.push(`/species/${item.species.id}`)} />
        )}
        ListEmptyComponent={<EmptyState message="No Pokémon match." />}
      />
    </Screen>
  );
}

function PokedexCell({ row, onOpen }: { row: SpeciesOwnership; onOpen: () => void }) {
  const t = useTheme();
  return (
    <Pressable
      onPress={onOpen}
      style={[
        styles.cell,
        {
          backgroundColor: row.owned ? t.ownedBg : t.card,
          borderColor: row.owned ? t.owned : t.border,
        },
      ]}
    >
      <Text style={[styles.cellDex, { color: t.textMuted }]}>
        #{String(row.species.national_dex_number).padStart(4, "0")}
      </Text>
      <Text style={[styles.cellName, { color: t.text }]} numberOfLines={1}>
        {row.species.name}
      </Text>
      <Text style={{ color: row.owned ? t.owned : t.textMuted, fontSize: 12, fontWeight: "700" }}>
        {row.owned ? "✓ Owned" : "—"}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  search: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 16, marginBottom: 12 },
  cell: { flex: 1, borderWidth: 1, borderRadius: 10, padding: 12, marginBottom: 8, gap: 2 },
  cellDex: { fontSize: 11, fontVariant: ["tabular-nums"] },
  cellName: { fontSize: 15, fontWeight: "700", textTransform: "capitalize" },
  muted: { fontSize: 13 },
});
