import { useEffect, useMemo, useState } from "react";
import { useLocalSearchParams } from "expo-router";
import { FlatList, Image, Pressable, StyleSheet, Text, View } from "react-native";
import type { CardWithContext, PokemonSpecies } from "@pulldex/shared";

import { Screen, LoadingState, EmptyState, OwnershipBadge } from "../../src/components/ui";
import { CardZoomModal, type ZoomCard } from "../../src/components/CardZoomModal";
import { useDatabase } from "../../src/db/provider";
import { useDataVersionValue, useMutation } from "../../src/hooks";
import {
  getCardsForSpecies,
  getOwnedCardIds,
  getRepresentativeCardId,
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
  const [representativeId, setRepresentativeId] = useState<number | null>(null);
  const [owned, setOwned] = useState(false);
  const [zoom, setZoom] = useState<ZoomCard | null>(null);
  const [recentlyAdded, setRecentlyAdded] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!db || !speciesId) return;
    (async () => {
      const [sp, cs, ids, own, repId] = await Promise.all([
        getSpeciesById(db, speciesId),
        getCardsForSpecies(db, speciesId),
        getOwnedCardIds(db),
        isSpeciesOwned(db, speciesId),
        getRepresentativeCardId(db, speciesId),
      ]);
      if (cancelled) return;
      setSpecies(sp);
      setCards(cs);
      setOwnedIds(ids);
      setOwned(own);
      setRepresentativeId(repId);
    })();
    return () => {
      cancelled = true;
    };
  }, [db, speciesId, dataVersion]);

  const ownedCount = useMemo(
    () => (cards ? cards.filter((c) => ownedIds.has(c.id)).length : 0),
    [cards, ownedIds],
  );

  // Sort owned cards first so a newly added card is immediately visible at top.
  const sortedCards = useMemo(() => {
    if (!cards) return [];
    return [...cards].sort((a, b) => {
      const ao = ownedIds.has(a.id) ? 0 : 1;
      const bo = ownedIds.has(b.id) ? 0 : 1;
      if (ao !== bo) return ao - bo;
      return 0;
    });
  }, [cards, ownedIds]);

  async function addCard(cardId: number) {
    await mutate((d) => markCardOwned(d, cardId, 1));
    setRecentlyAdded(cardId);
  }

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
        Cards ({ownedCount}/{cards.length} owned) · tap image to zoom
      </Text>

      <FlatList
        data={sortedCards}
        keyExtractor={(c) => String(c.id)}
        renderItem={({ item }) => {
          const isOwned = ownedIds.has(item.id);
          const isRepresentative = representativeId === item.id;
          const justAdded = recentlyAdded === item.id;
          return (
            <View
              style={[
                styles.card,
                {
                  backgroundColor: isOwned ? t.ownedBg : t.card,
                  borderColor: justAdded ? t.accent : t.border,
                  borderWidth: justAdded ? 2 : 1,
                },
              ]}
            >
              <Pressable
                onPress={() => setZoom(toZoom(item))}
                accessibilityLabel={`Zoom ${item.pokemon_name ?? "card"}`}
                hitSlop={6}
              >
                {item.image_url ? (
                  <Image source={{ uri: item.image_url }} style={styles.thumb} resizeMode="contain" />
                ) : (
                  <View style={[styles.thumb, { backgroundColor: t.cardAlt, alignItems: "center", justifyContent: "center" }]}>
                    <Text style={{ color: t.textMuted, fontSize: 9 }}>No image</Text>
                  </View>
                )}
              </Pressable>

              <View style={{ flex: 1, gap: 2 }}>
                <Text style={[styles.cardName, { color: t.text }]} numberOfLines={1}>
                  {item.pokemon_name ?? "Card"}
                  {justAdded ? "  • added" : ""}
                </Text>
                <Text style={[styles.muted, { color: t.textMuted }]} numberOfLines={1}>
                  {item.set_name ?? "Unknown set"}
                </Text>
                <Text style={[styles.metaLine, { color: t.textMuted }]} numberOfLines={1}>
                  {[item.variant, item.card_number ? `#${item.card_number}` : null, item.rarity]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </Text>
                {isOwned && (
                  isRepresentative ? (
                    <Text style={{ color: t.accent, fontSize: 12, fontWeight: "700" }}>★ In Pokédex Binder</Text>
                  ) : (
                    <Pressable onPress={() => mutate((d) => setBinderCard(d, item.id))} hitSlop={6}>
                      <Text style={{ color: t.accent, fontSize: 12, fontWeight: "700" }}>
                        ☆ Show in Pokédex Binder
                      </Text>
                    </Pressable>
                  )
                )}
              </View>

              <Pressable
                onPress={() => (isOwned ? mutate((d) => removeCardOwnership(d, item.id)) : addCard(item.id))}
                style={[styles.toggle, { backgroundColor: isOwned ? t.missingBg : t.accent }]}
                accessibilityLabel={isOwned ? `Remove ${item.pokemon_name ?? "card"}` : `Add ${item.pokemon_name ?? "card"}`}
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

      <CardZoomModal card={zoom} onClose={() => setZoom(null)} />
    </Screen>
  );
}

function toZoom(c: CardWithContext): ZoomCard {
  return {
    image_url: c.image_url,
    pokemon_name: c.pokemon_name,
    national_dex_number: c.national_dex_number,
    set_name: c.set_name,
    set_code: c.set_code,
    card_number: c.card_number,
    rarity: c.rarity,
    variant: c.variant,
  };
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 16 },
  dex: { fontSize: 14, fontVariant: ["tabular-nums"] },
  name: { fontSize: 26, fontWeight: "800", textTransform: "capitalize" },
  section: { fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10 },
  card: { flexDirection: "row", alignItems: "center", gap: 12, borderRadius: 10, padding: 10, marginBottom: 8 },
  thumb: { width: 46, height: 64, borderRadius: 4 },
  cardName: { fontSize: 15, fontWeight: "700", textTransform: "capitalize" },
  muted: { fontSize: 12 },
  metaLine: { fontSize: 11 },
  toggle: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8 },
});
