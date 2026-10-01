import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View, Pressable, useColorScheme } from "react-native";
import Constants from "expo-constants";
import { MIN_BINDER_DIMENSION, MAX_BINDER_DIMENSION, BINDER_LAYOUT_PRESETS } from "@pulldex/shared";

import { Screen, LoadingState } from "../../src/components/ui";
import { useBinderLayout, useSummary } from "../../src/hooks";
import { useDatabase } from "../../src/db/provider";
import { getCatalogueGeneratedAt } from "../../src/db/repository";
import { useTheme } from "../../src/theme";

const DIMS = Array.from(
  { length: MAX_BINDER_DIMENSION - MIN_BINDER_DIMENSION + 1 },
  (_, i) => MIN_BINDER_DIMENSION + i,
);

export default function Settings() {
  const t = useTheme();
  const scheme = useColorScheme();
  const db = useDatabase();
  const summary = useSummary();
  const { layout, save } = useBinderLayout();

  const [rows, setRows] = useState<number | null>(null);
  const [cols, setCols] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!db) return;
    getCatalogueGeneratedAt(db).then(setGeneratedAt);
  }, [db]);

  if (!layout || !summary) {
    return <Screen><LoadingState message="Loading settings…" /></Screen>;
  }

  const effRows = rows ?? layout.rows;
  const effCols = cols ?? layout.columns;
  const changed = effRows !== layout.rows || effCols !== layout.columns;
  const appVersion = Constants.expoConfig?.version ?? "0.1.0";

  async function onSave() {
    await save(effRows, effCols);
    setRows(null);
    setCols(null);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16 }}>
        <Text style={[styles.h1, { color: t.text }]}>Settings</Text>

        {/* Pokédex Binder layout */}
        <Section title="Pokédex Binder Layout">
          <Text style={[styles.hint, { color: t.textMuted }]}>
            Rows and columns per binder page. Applies to the Pokédex binder.
          </Text>
          <View style={styles.presets}>
            {BINDER_LAYOUT_PRESETS.map((p) => {
              const active = p.rows === effRows && p.columns === effCols;
              return (
                <Pressable
                  key={p.label}
                  onPress={() => {
                    setRows(p.rows);
                    setCols(p.columns);
                  }}
                  style={[styles.preset, { borderColor: active ? t.accent : t.border, backgroundColor: active ? t.accent : t.card }]}
                >
                  <Text style={{ color: active ? t.accentText : t.text, fontWeight: "700" }}>{p.label}</Text>
                </Pressable>
              );
            })}
          </View>
          <View style={styles.dimRow}>
            <Stepper label="Rows" value={effRows} onChange={setRows} />
            <Stepper label="Columns" value={effCols} onChange={setCols} />
          </View>
          <Pressable
            onPress={onSave}
            disabled={!changed}
            style={[styles.saveBtn, { backgroundColor: changed ? t.accent : t.cardAlt }]}
          >
            <Text style={{ color: changed ? t.accentText : t.textMuted, fontWeight: "700" }}>
              {saved ? "Saved!" : "Save layout"}
            </Text>
          </Pressable>
          <Text style={[styles.hint, { color: t.textMuted }]}>
            {effRows}×{effCols} = {effRows * effCols} cards per page
          </Text>
        </Section>

        {/* Theme */}
        <Section title="Appearance">
          <Row label="Theme" value={scheme === "dark" ? "Dark (system)" : "Light (system)"} />
          <Text style={[styles.hint, { color: t.textMuted }]}>
            PullDex follows your device light/dark setting.
          </Text>
        </Section>

        {/* Catalogue + app info */}
        <Section title="Catalogue & App">
          <Row label="App version" value={appVersion} />
          <Row label="Cards" value={summary.totalCatalogueCards.toLocaleString()} />
          <Row label="Sets" value={String(summary.totalSets)} />
          <Row label="Promo sets" value={String(summary.promoSets)} />
          <Row label="Species" value={String(summary.progress.totalSpecies)} />
          {generatedAt && <Row label="Catalogue snapshot" value={generatedAt.slice(0, 10)} />}
          <Text style={[styles.hint, { color: t.textMuted }]}>
            The card catalogue is bundled and works fully offline.
          </Text>
        </Section>

        {/* Data — deferred */}
        <Section title="Backup & Restore">
          <Text style={[styles.hint, { color: t.textMuted }]}>
            Local backup/restore and desktop import are not available in this build. The desktop
            PullDex backup is a full desktop-format database; safely importing it on Android will be
            added in a later release. Your collection is stored locally on this device.
          </Text>
        </Section>

        {/* Sync placeholder */}
        <Section title="Sync">
          <View style={[styles.soonBadge, { backgroundColor: t.cardAlt }]}>
            <Text style={{ color: t.textMuted, fontWeight: "700" }}>Coming soon</Text>
          </View>
          <Text style={[styles.hint, { color: t.textMuted }]}>
            Windows ↔ Android cloud sync is planned for a future version. This build is fully
            offline and local-only.
          </Text>
        </Section>
      </ScrollView>
    </Screen>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const t = useTheme();
  return (
    <View style={[styles.section, { backgroundColor: t.card, borderColor: t.border }]}>
      <Text style={[styles.sectionTitle, { color: t.text }]}>{title}</Text>
      {children}
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const t = useTheme();
  return (
    <View style={styles.infoRow}>
      <Text style={{ color: t.textMuted }}>{label}</Text>
      <Text style={{ color: t.text, fontWeight: "600" }}>{value}</Text>
    </View>
  );
}

function Stepper({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  const t = useTheme();
  return (
    <View style={{ flex: 1 }}>
      <Text style={{ color: t.textMuted, fontSize: 12, marginBottom: 4 }}>{label}</Text>
      <View style={styles.stepper}>
        <Pressable
          onPress={() => onChange(Math.max(MIN_BINDER_DIMENSION, value - 1))}
          style={[styles.stepBtn, { borderColor: t.border }]}
          accessibilityLabel={`Decrease ${label}`}
        >
          <Text style={{ color: t.text, fontSize: 18, fontWeight: "700" }}>−</Text>
        </Pressable>
        <Text style={{ color: t.text, fontSize: 18, fontWeight: "700", minWidth: 28, textAlign: "center" }}>
          {value}
        </Text>
        <Pressable
          onPress={() => onChange(Math.min(MAX_BINDER_DIMENSION, value + 1))}
          style={[styles.stepBtn, { borderColor: t.border }]}
          accessibilityLabel={`Increase ${label}`}
        >
          <Text style={{ color: t.text, fontSize: 18, fontWeight: "700" }}>+</Text>
        </Pressable>
      </View>
    </View>
  );
}

// DIMS retained for potential future use (explicit rows/cols pickers).
void DIMS;

const styles = StyleSheet.create({
  h1: { fontSize: 26, fontWeight: "800" },
  section: { borderWidth: 1, borderRadius: 12, padding: 16, gap: 10 },
  sectionTitle: { fontSize: 16, fontWeight: "800" },
  hint: { fontSize: 12, lineHeight: 17 },
  presets: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  preset: { borderWidth: 1, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  dimRow: { flexDirection: "row", gap: 16 },
  stepper: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  stepBtn: { borderWidth: 1, borderRadius: 8, width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  saveBtn: { borderRadius: 10, paddingVertical: 12, alignItems: "center" },
  infoRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  soonBadge: { alignSelf: "flex-start", borderRadius: 999, paddingHorizontal: 12, paddingVertical: 4 },
});
