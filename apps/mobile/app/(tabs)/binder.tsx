import { useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import {
  DEFAULT_BINDER_COLUMNS,
  DEFAULT_BINDER_ROWS,
  pokedexTotalPages,
  type PokedexBinderPage,
} from "@pulldex/shared";

import { Screen, LoadingState } from "../../src/components/ui";
import { useDatabase } from "../../src/db/provider";
import { getPokedexBinderPage } from "../../src/db/repository";
import { useDataVersionValue } from "../../src/hooks";
import { useTheme } from "../../src/theme";

const ROWS = DEFAULT_BINDER_ROWS;
const COLS = DEFAULT_BINDER_COLUMNS;
const PAGE_SIZE = ROWS * COLS;

export default function Binder() {
  const t = useTheme();
  const db = useDatabase();
  const dataVersion = useDataVersionValue();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PokedexBinderPage | null>(null);
  const totalPages = pokedexTotalPages(PAGE_SIZE);

  useEffect(() => {
    let cancelled = false;
    if (!db) return;
    setData(null);
    getPokedexBinderPage(db, page, PAGE_SIZE).then((d) => !cancelled && setData(d));
    return () => {
      cancelled = true;
    };
  }, [db, page, dataVersion]);

  return (
    <Screen style={{ padding: 12 }}>
      <View style={styles.pager}>
        <PagerButton label="⏮" disabled={page <= 1} onPress={() => setPage(1)} />
        <PagerButton label="‹" disabled={page <= 1} onPress={() => setPage((p) => Math.max(1, p - 1))} />
        <Text style={[styles.pageText, { color: t.text }]}>
          Page {page} / {totalPages}
        </Text>
        <PagerButton label="›" disabled={page >= totalPages} onPress={() => setPage((p) => Math.min(totalPages, p + 1))} />
        <PagerButton label="⏭" disabled={page >= totalPages} onPress={() => setPage(totalPages)} />
      </View>

      {!data ? (
        <LoadingState message="Loading binder…" />
      ) : (
        <View style={styles.grid}>
          {data.slots.map((slot, i) => (
            <View
              key={slot.dex_number ?? `pad-${i}`}
              style={[
                styles.slot,
                {
                  width: `${100 / COLS}%`,
                  aspectRatio: 0.72,
                  borderColor: slot.owned ? t.owned : t.border,
                  backgroundColor: slot.owned ? t.ownedBg : t.cardAlt,
                },
              ]}
            >
              {slot.dex_number == null ? null : slot.has_card && slot.card?.image_url ? (
                <Image source={{ uri: slot.card.image_url }} style={styles.img} resizeMode="contain" />
              ) : (
                <View style={styles.placeholder}>
                  <Text style={[styles.slotDex, { color: t.textMuted }]}>#{slot.dex_number}</Text>
                  <Text style={[styles.slotName, { color: slot.owned ? t.owned : t.textMuted }]} numberOfLines={1}>
                    {slot.species_name}
                  </Text>
                  {slot.owned && <Text style={{ color: t.owned, fontSize: 10 }}>✓</Text>}
                </View>
              )}
            </View>
          ))}
        </View>
      )}
      <Text style={[styles.note, { color: t.textMuted }]}>
        Pokédex binder · representative card per owned species
      </Text>
    </Screen>
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

const styles = StyleSheet.create({
  pager: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 10 },
  pagerBtn: { borderWidth: 1, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  pageText: { fontSize: 14, fontWeight: "600", minWidth: 110, textAlign: "center" },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  slot: { borderWidth: 1, borderRadius: 8, padding: 2, alignItems: "center", justifyContent: "center" },
  img: { width: "100%", height: "100%", borderRadius: 4 },
  placeholder: { alignItems: "center", justifyContent: "center", gap: 1 },
  slotDex: { fontSize: 9, fontVariant: ["tabular-nums"] },
  slotName: { fontSize: 9, fontWeight: "600", textTransform: "capitalize", paddingHorizontal: 2 },
  note: { fontSize: 11, textAlign: "center", marginTop: 8 },
});
