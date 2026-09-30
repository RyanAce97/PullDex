import { useEffect, useMemo, useState } from "react";
import { useLocalSearchParams } from "expo-router";
import { FlatList, Image, Pressable, StyleSheet, Text, View } from "react-native";
import type { CardWithContext, PokemonSpecies } from "@pulldex/shared";

import { Screen, LoadingState, EmptyState, OwnershipBadge } from "../../src/components/ui";
import { useDatabase } from "../../src/db/provider";
import { useDataVersionValue, useMutation } from "../../src/hooks";
import {
  getCardsForSpecies,
  getOwnedCardIds,
  getSpeciesById,
  isSpeciesOwned,
  markCardOwned,
  removeCardOwnership,
  setBinderCard,
} from "../../src/db/repository";
import { useTheme } from "../../src/theme";

export default function SpeciesDetail() {
  const t = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const speciesId = Number(id);
  const db = useDatabase();
  const dataVersion = useDataVersionValue();
  const mutate = useMutation();

  const [species, setSpecies] = useState<PokemonSpecies | null>(null);
  const [cards, setCards] = useState<CardWithContext[] | null>(null);
  const [ownedIds, setOwnedIds] = useState<Set<number>>(new Set());
  const [owned, setOwned] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!db || !speciesId) return;
    (async () => {
      const [sp, cs, ids, own] = await Promise.all([
        getSpeciesById(db, speciesId),
        getCardsForSpecies(db, speciesId),
        getOwnedCardIds(db),
        isSpeciesOwned(db, speciesId),
      ]);
      if (cancelled) return;
      setSpecies(sp);
      setCards(cs);
      setOwnedIds(ids);
      setOwned(own);
    })();
    return () => {
      cancelled = true;
    };
  }, [db, speciesId, dataVersion]);

  const ownedCount = useMemo(
    () => (cards ? cards.filter((c) => ownedIds.has(c.id)).length : 0),
    [cards, ownedIds],
  );

  if (!species || !cards) {
    return <Screen><LoadingState message="Loading…" /></Screen>;
  }

  return (
    <Screen style={{ padding: 16 }}>
      <View style={styles.header}>
        <View>
          <Text style={[styles.dex, { color: t.textMuted }]}>
            #{String(species.national_dex_number).padStart(4, "0")}
          </Text>
          <Text style={[styles.name, { color: t.text }]}>{species.name}</Text>
          {species.generation != null && (
            <Text style={[styles.muted, { color: t.textMuted }]}>Generation {species.generation}</Text>
          )}
        </View>
        <OwnershipBadge owned={owned} />
      </View>

      <Text style={[styles.section, { color: t.textMuted }]}>
        Cards ({ownedCount}/{cards.length} owned)
      </Text>

      <FlatList
        data={cards}
        keyExtractor={(c) => String(c.id)}
        renderItem={({ item }) => {
          const isOwned = ownedIds.has(item.id);
          return (
            <View style={[styles.card, { backgroundColor: isOwned ? t.ownedBg : t.card, borderColor: t.border }]}>
              {item.image_url ? (
                <Image source={{ uri: item.image_url }} style={styles.thumb} resizeMode="contain" />
              ) : (
                <View style={[styles.thumb, { backgroundColor: t.cardAlt }]} />
              )}
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={[styles.cardName, { color: t.text }]} numberOfLines={1}>
                  {item.set_name ?? "Unknown set"}
                </Text>
                <Text style={[styles.muted, { color: t.textMuted }]}>
                  {item.rarity ?? "—"}{item.card_number ? ` · #${item.card_number}` : ""}
                </Text>
                {isOwned && (
                  <Pressable onPress={() => mutate((d) => setBinderCard(d, item.id))}>
                    <Text style={{ color: t.accent, fontSize: 12, fontWeight: "700" }}>
                      ★ Show in Pokédex Binder
                    </Text>
                  </Pressable>
                )}
              </View>
              <Pressable
                onPress={() =>
                  mutate((d) => (isOwned ? removeCardOwnership(d, item.id) : markCardOwned(d, item.id, 1)))
                }
                style={[styles.toggle, { backgroundColor: isOwned ? t.missingBg : t.accent }]}
              >
                <Text style={{ color: isOwned ? t.missing : t.accentText, fontWeight: "700", fontSize: 12 }}>
                  {isOwned ? "Remove" : "Add"}
                </Text>
              </Pressable>
            </View>
          );
        }}
        ListEmptyComponent={<EmptyState icon="🃏" message="No cards found for this Pokémon." />}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 16 },
  dex: { fontSize: 14, fontVariant: ["tabular-nums"] },
  name: { fontSize: 26, fontWeight: "800", textTransform: "capitalize" },
  section: { fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10 },
  card: { flexDirection: "row", alignItems: "center", gap: 12, borderWidth: 1, borderRadius: 10, padding: 10, marginBottom: 8 },
  thumb: { width: 44, height: 60, borderRadius: 4 },
  cardName: { fontSize: 15, fontWeight: "600" },
  muted: { fontSize: 12 },
  toggle: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8 },
});
