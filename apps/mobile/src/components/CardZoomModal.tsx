import React from "react";
import { Image, Modal, Pressable, StyleSheet, Text, View } from "react-native";

import { useTheme } from "../theme";

export interface ZoomCard {
  image_url: string | null;
  pokemon_name: string | null;
  national_dex_number: number | null;
  set_name: string | null;
  set_code: string | null;
  card_number: string | null;
  rarity: string | null;
  variant: string | null;
}

/**
 * Full-screen card inspector. Mirrors the desktop CardPreviewModal:
 * a large card image plus identifying details, with an obvious close action.
 * Touch-friendly: tap the backdrop, the ✕, or hardware back to dismiss.
 */
export function CardZoomModal({ card, onClose }: { card: ZoomCard | null; onClose: () => void }) {
  const t = useTheme();
  const visible = card !== null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close card view">
        {/* Inner pressable swallows taps so tapping the card doesn't close it. */}
        <Pressable style={styles.inner} onPress={() => {}}>
          <Pressable
            onPress={onClose}
            style={[styles.close, { backgroundColor: t.card, borderColor: t.border }]}
            accessibilityLabel="Close"
            hitSlop={12}
          >
            <Text style={{ color: t.text, fontSize: 18, fontWeight: "700" }}>✕</Text>
          </Pressable>

          {card?.image_url ? (
            <Image source={{ uri: card.image_url }} style={styles.image} resizeMode="contain" />
          ) : (
            <View style={[styles.noImage, { backgroundColor: t.cardAlt }]}>
              <Text style={{ color: t.textMuted }}>No image available</Text>
            </View>
          )}

          {card && (
            <View style={[styles.details, { backgroundColor: t.card, borderColor: t.border }]}>
              <View style={styles.detailRow}>
                <Text style={[styles.name, { color: t.text }]}>{card.pokemon_name ?? "Card"}</Text>
                {card.national_dex_number != null && (
                  <Text style={[styles.dex, { color: t.textMuted }]}>
                    #{String(card.national_dex_number).padStart(4, "0")}
                  </Text>
                )}
              </View>
              <View style={styles.meta}>
                {card.set_name && <Meta label="Set" value={card.set_name} />}
                {card.variant && <Meta label="Type" value={card.variant} />}
                {card.card_number && <Meta label="Number" value={`#${card.card_number}`} />}
                {card.rarity && <Meta label="Rarity" value={card.rarity} />}
                {card.set_code && <Meta label="Set code" value={card.set_code.toUpperCase()} />}
              </View>
            </View>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  const t = useTheme();
  return (
    <View style={{ minWidth: 100 }}>
      <Text style={{ color: t.textMuted, fontSize: 11 }}>{label}</Text>
      <Text style={{ color: t.text, fontSize: 14, fontWeight: "600" }}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.8)",
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
  },
  inner: { width: "100%", maxWidth: 480, alignItems: "center", gap: 14 },
  close: {
    position: "absolute",
    top: -6,
    right: -6,
    zIndex: 10,
    width: 40,
    height: 40,
    borderRadius: 999,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  image: { width: "88%", height: 420, borderRadius: 12 },
  noImage: { width: "70%", height: 300, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  details: { width: "100%", borderWidth: 1, borderRadius: 12, padding: 14, gap: 10 },
  detailRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  name: { fontSize: 20, fontWeight: "800", textTransform: "capitalize" },
  dex: { fontSize: 14, fontVariant: ["tabular-nums"] },
  meta: { flexDirection: "row", flexWrap: "wrap", gap: 14 },
});
