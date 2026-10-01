import { useEffect, useMemo, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  pokedexTotalPages,
  rankSpeciesSearch,
  type PokedexBinderPage,
  type PokedexBinderSlot,
  type SpeciesOwnership,
} from "@pulldex/shared";

import { Screen, LoadingState } from "../../src/components/ui";
import { CardZoomModal, type ZoomCard } from "../../src/components/CardZoomModal";
import { useDatabase } from "../../src/db/provider";
import {
  getBinderLayout,
  getCardsForSpecies,
  getPokedexBinderPage,
  setBinderCard,
  type BinderLayout,
} from "../../src/db/repository";
import { useDataVersionValue, useMutation, useSpeciesOwnership } from "../../src/hooks";
import { useTheme } from "../../src/theme";

// Allowance for the bottom tab bar; combined with the safe-area inset this
// guarantees the final binder row scrolls fully clear of the Android nav area.
const TAB_BAR_ALLOWANCE = 64;

export default function Binder() {
  const t = useTheme();
  const db = useDatabase();
  const insets = useSafeAreaInsets();
  const dataVersion = useDataVersionValue();
  const mutate = useMutation();
  const { rows: speciesRows } = useSpeciesOwnership();

  const [layout, setLayout] = useState<BinderLayout>({ rows: 5, columns: 4 });
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [data, setData] = useState<PokedexBinderPage | null>(null);
  const [zoom, setZoom] = useState<ZoomCard | null>(null);
  const [repSlot, setRepSlot] = useState<PokedexBinderSlot | null>(null);
  const [query, setQuery] = useState("");

  const pageSize = layout.rows * layout.columns;
  const totalPages = pokedexTotalPages(pageSize);

  // Load persisted layout (configurable in Settings).
  useEffect(() => {
    let cancelled = false;
    if (!db) return;
    getBinderLayout(db).then((l) => !cancelled && setLayout(l));
    return () => {
      cancelled = true;
    };
  }, [db, dataVersion]);

  // Clamp page when layout changes.
  useEffect(() => {
    setPage((p) => Math.max(1, Math.min(totalPages, p)));
  }, [totalPages]);

  useEffect(() => {
    let cancelled = false;
    if (!db) return;
    setData(null);
    getPokedexBinderPage(db, page, pageSize).then((d) => !cancelled && setData(d));
    return () => {
      cancelled = true;
    };
  }, [db, page, pageSize, dataVersion]);

  function goToPage(target: number) {
    const clamped = Math.max(1, Math.min(totalPages, target));
    setPage(clamped);
    setPageInput(String(clamped));
  }

  // Jump search: type a Pokémon name or dex number → jump to its binder page.
  const searchResults = useMemo(
    () => (speciesRows && query.trim() ? rankSpeciesSearch(speciesRows, query, 8) : []),
    [speciesRows, query],
  );

  function jumpToSpecies(row: SpeciesOwnership) {
    const targetPage = Math.ceil(row.species.national_dex_number / pageSize);
    goToPage(targetPage);
    setQuery("");
  }

  async function openRepresentativePicker(slot: PokedexBinderSlot) {
    setRepSlot(slot);
  }

  return (
    <Screen style={{ padding: 12 }}>
      {/* Jump-to-Pokémon search (Pokédex binder) */}
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Jump to Pokémon or Dex #"
        placeholderTextColor={t.textMuted}
        autoCorrect={false}
        autoCapitalize="none"
        style={[styles.search, { backgroundColor: t.card, borderColor: t.border, color: t.text }]}
      />
      {searchResults.length > 0 && (
        <View style={[styles.searchResults, { backgroundColor: t.card, borderColor: t.border }]}>
          {searchResults.map((r) => (
            <Pressable key={r.species.id} onPress={() => jumpToSpecies(r)} style={styles.searchRow}>
              <Text style={[styles.searchDex, { color: t.textMuted }]}>
                #{String(r.species.national_dex_number).padStart(4, "0")}
              </Text>
              <Text style={[styles.searchName, { color: t.text }]}>{r.species.name}</Text>
              <View style={{ flex: 1 }} />
              <Text style={{ color: r.owned ? t.owned : t.textMuted, fontSize: 11 }}>
                {r.owned ? "Owned" : "—"}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      {/* Pager */}
      <View style={styles.pager}>
        <PagerButton label="⏮" disabled={page <= 1} onPress={() => goToPage(1)} />
        <PagerButton label="‹" disabled={page <= 1} onPress={() => goToPage(page - 1)} />
        <View style={styles.pageInputWrap}>
          <TextInput
            value={pageInput}
            onChangeText={setPageInput}
            onBlur={() => {
              const n = parseInt(pageInput, 10);
              if (Number.isNaN(n)) setPageInput(String(page));
              else goToPage(n);
            }}
            keyboardType="number-pad"
            style={[styles.pageInput, { color: t.text, borderColor: t.border }]}
            accessibilityLabel="Page number"
          />
          <Text style={[styles.pageTotal, { color: t.textMuted }]}>/ {totalPages}</Text>
        </View>
        <PagerButton label="›" disabled={page >= totalPages} onPress={() => goToPage(page + 1)} />
        <PagerButton label="⏭" disabled={page >= totalPages} onPress={() => goToPage(totalPages)} />
      </View>

      {/* Binder grid — scrollable so the final row clears the bottom nav.
          Bottom padding accounts for the safe-area inset + tab bar height. */}
      {!data ? (
        <LoadingState message="Loading binder…" />
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingBottom: insets.bottom + TAB_BAR_ALLOWANCE }}
          showsVerticalScrollIndicator
        >
          <View style={styles.grid}>
            {data.slots.map((slot, i) => (
              <BinderSlotView
                key={slot.dex_number ?? `pad-${i}`}
                slot={slot}
                columns={layout.columns}
                onZoom={() => slot.card && setZoom(cardToZoom(slot))}
                onPickRepresentative={() => openRepresentativePicker(slot)}
              />
            ))}
          </View>
          <Text style={[styles.note, { color: t.textMuted }]}>
            Page {page} / {totalPages} · {layout.rows}×{layout.columns} · tap a card to zoom, long-press an owned slot to choose its binder card
          </Text>
        </ScrollView>
      )}

      <CardZoomModal card={zoom} onClose={() => setZoom(null)} />

      {repSlot && repSlot.species_id != null && (
        <RepresentativePicker
          slot={repSlot}
          onClose={() => setRepSlot(null)}
          onChoose={async (cardId) => {
            await mutate((d) => setBinderCard(d, cardId));
            setRepSlot(null);
          }}
        />
      )}
    </Screen>
  );
}

function BinderSlotView({
  slot,
  columns,
  onZoom,
  onPickRepresentative,
}: {
  slot: PokedexBinderSlot;
  columns: number;
  onZoom: () => void;
  onPickRepresentative: () => void;
}) {
  const t = useTheme();
  const widthPct = `${100 / columns}%` as const;

  if (slot.dex_number == null) {
    return <View style={[styles.slot, { width: widthPct, borderColor: "transparent" }]} />;
  }

  const owned = slot.owned;
  return (
    <Pressable
      onPress={slot.has_card ? onZoom : owned ? onPickRepresentative : undefined}
      onLongPress={owned ? onPickRepresentative : undefined}
      style={[
        styles.slot,
        {
          width: widthPct,
          borderColor: owned ? t.owned : t.border,
          backgroundColor: owned ? t.ownedBg : t.cardAlt,
        },
      ]}
      accessibilityLabel={`#${slot.dex_number} ${slot.species_name ?? ""}${owned ? " owned" : ""}`}
    >
      {slot.has_card && slot.card?.image_url ? (
        <Image source={{ uri: slot.card.image_url }} style={styles.slotImg} resizeMode="contain" />
      ) : (
        <View style={styles.slotPlaceholder}>
          <Text style={[styles.slotDex, { color: t.textMuted }]}>#{slot.dex_number}</Text>
          <Text
            style={[styles.slotName, { color: owned ? t.owned : t.textMuted }]}
            numberOfLines={1}
          >
            {slot.species_name}
          </Text>
          {owned && <Text style={{ color: t.owned, fontSize: 10 }}>✓</Text>}
        </View>
      )}
    </Pressable>
  );
}

// Choose which owned card represents this species in the Pokédex binder.
function RepresentativePicker({
  slot,
  onClose,
  onChoose,
}: {
  slot: PokedexBinderSlot;
  onClose: () => void;
  onChoose: (cardId: number) => void;
}) {
  const t = useTheme();
  const db = useDatabase();
  const [cards, setCards] = useState<Awaited<ReturnType<typeof getCardsForSpecies>> | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!db || slot.species_id == null) return;
    getCardsForSpecies(db, slot.species_id).then((cs) => !cancelled && setCards(cs));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, slot.species_id]);

  return (
    <View style={styles.pickerBackdrop}>
      <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close" />
      <View style={[styles.picker, { backgroundColor: t.card, borderColor: t.border }]}>
        <Text style={[styles.pickerTitle, { color: t.text }]}>
          Binder card · {slot.species_name}
        </Text>
        <Text style={[styles.pickerHint, { color: t.textMuted }]}>
          Choose which owned card is shown in the Pokédex binder. This changes binder display only,
          not ownership.
        </Text>
        <ScrollView style={{ maxHeight: 320 }}>
          {(cards ?? []).length === 0 && (
            <Text style={{ color: t.textMuted, padding: 12 }}>Loading owned cards…</Text>
          )}
          {(cards ?? []).map((c) => (
            <Pressable
              key={c.id}
              onPress={() => onChoose(c.id)}
              style={[styles.pickerRow, { borderColor: t.border }]}
            >
              {c.image_url ? (
                <Image source={{ uri: c.image_url }} style={styles.pickerThumb} resizeMode="contain" />
              ) : (
                <View style={[styles.pickerThumb, { backgroundColor: t.cardAlt }]} />
              )}
              <View style={{ flex: 1 }}>
                <Text style={{ color: t.text, fontWeight: "600" }} numberOfLines={1}>
                  {c.set_name ?? "Unknown set"}
                </Text>
                <Text style={{ color: t.textMuted, fontSize: 12 }} numberOfLines={1}>
                  {[c.variant, c.card_number ? `#${c.card_number}` : null, c.rarity].filter(Boolean).join(" · ")}
                </Text>
              </View>
            </Pressable>
          ))}
        </ScrollView>
        <Pressable onPress={onClose} style={[styles.pickerClose, { backgroundColor: t.cardAlt }]}>
          <Text style={{ color: t.text, fontWeight: "700" }}>Close</Text>
        </Pressable>
      </View>
    </View>
  );
}

function PagerButton({ label, disabled, onPress }: { label: string; disabled?: boolean; onPress: () => void }) {
  const t = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={[styles.pagerBtn, { borderColor: t.border, opacity: disabled ? 0.3 : 1 }]}
    >
      <Text style={{ color: t.text, fontSize: 16 }}>{label}</Text>
    </Pressable>
  );
}

function cardToZoom(slot: PokedexBinderSlot): ZoomCard {
  const c = slot.card!;
  return {
    image_url: c.image_url,
    pokemon_name: c.pokemon_name ?? slot.species_name,
    national_dex_number: c.national_dex_number ?? slot.dex_number,
    set_name: c.set_name,
    set_code: c.set_code,
    card_number: c.card_number,
    rarity: c.rarity,
    variant: c.variant,
  };
}

const styles = StyleSheet.create({
  search: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, marginBottom: 8 },
  searchResults: { borderWidth: 1, borderRadius: 10, marginBottom: 8, overflow: "hidden" },
  searchRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 10 },
  searchDex: { fontSize: 12, fontVariant: ["tabular-nums"] },
  searchName: { fontSize: 15, fontWeight: "600", textTransform: "capitalize" },
  pager: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 10 },
  pagerBtn: { borderWidth: 1, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  pageInputWrap: { flexDirection: "row", alignItems: "center", gap: 4 },
  pageInput: { borderWidth: 1, borderRadius: 6, minWidth: 44, textAlign: "center", paddingVertical: 4, paddingHorizontal: 6 },
  pageTotal: { fontSize: 14 },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  slot: { aspectRatio: 0.72, borderWidth: 1, borderRadius: 8, padding: 2, alignItems: "center", justifyContent: "center" },
  slotImg: { width: "100%", height: "100%", borderRadius: 4 },
  slotPlaceholder: { alignItems: "center", justifyContent: "center", gap: 1 },
  slotDex: { fontSize: 9, fontVariant: ["tabular-nums"] },
  slotName: { fontSize: 9, fontWeight: "600", textTransform: "capitalize", paddingHorizontal: 2 },
  note: { fontSize: 11, textAlign: "center", marginTop: 10 },
  pickerBackdrop: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.6)", alignItems: "center", justifyContent: "center", padding: 20 },
  picker: { width: "100%", maxWidth: 440, borderWidth: 1, borderRadius: 14, padding: 16, gap: 8 },
  pickerTitle: { fontSize: 16, fontWeight: "800", textTransform: "capitalize" },
  pickerHint: { fontSize: 12 },
  pickerRow: { flexDirection: "row", alignItems: "center", gap: 10, borderWidth: 1, borderRadius: 8, padding: 8, marginBottom: 6 },
  pickerThumb: { width: 36, height: 50, borderRadius: 4 },
  pickerClose: { borderRadius: 8, paddingVertical: 12, alignItems: "center", marginTop: 4 },
});
