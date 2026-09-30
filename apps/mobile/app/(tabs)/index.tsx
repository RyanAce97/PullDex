import { Link } from "expo-router";
import { StyleSheet, Text, View, Pressable } from "react-native";

import { Screen, ProgressBar, LoadingState } from "../../src/components/ui";
import { useProgress } from "../../src/hooks";
import { catalogueCounts } from "../../src/db/seed";
import { useTheme } from "../../src/theme";

export default function Dashboard() {
  const t = useTheme();
  const progress = useProgress();
  const counts = catalogueCounts();

  if (!progress) {
    return (
      <Screen>
        <LoadingState message="Loading collection…" />
      </Screen>
    );
  }

  return (
    <Screen style={{ padding: 16 }}>
      <Text style={[styles.h1, { color: t.text }]}>PullDex</Text>
      <Text style={[styles.sub, { color: t.textMuted }]}>Living Pokédex — offline</Text>

      <View style={[styles.card, { backgroundColor: t.card, borderColor: t.border }]}>
        <Text style={[styles.cardTitle, { color: t.text }]}>Pokédex progress</Text>
        <Text style={[styles.big, { color: t.accent }]}>
          {progress.ownedSpecies} / {progress.totalSpecies}
        </Text>
        <ProgressBar percentage={progress.percentage} />
        <Text style={[styles.muted, { color: t.textMuted }]}>
          {progress.percentage}% complete · {progress.missingSpecies} missing
        </Text>
      </View>

      <View style={[styles.card, { backgroundColor: t.card, borderColor: t.border }]}>
        <Text style={[styles.cardTitle, { color: t.text }]}>Catalogue</Text>
        <Text style={[styles.muted, { color: t.textMuted }]}>
          {counts.cards.toLocaleString()} cards · {counts.sets} sets · {counts.species} species (bundled, offline)
        </Text>
      </View>

      <View style={{ gap: 10, marginTop: 8 }}>
        <QuickLink href="/show" label="⚡ Card Show Mode" hint="Fast owned / not-owned check" />
        <QuickLink href="/collection" label="📋 Collection" hint="Browse, search, mark owned" />
        <QuickLink href="/pokedex" label="🔴 Pokédex" hint="National Dex progress" />
        <QuickLink href="/binder" label="📔 Binder" hint="Pokédex binder view" />
      </View>
    </Screen>
  );
}

function QuickLink({ href, label, hint }: { href: string; label: string; hint: string }) {
  const t = useTheme();
  return (
    <Link href={href} asChild>
      {/* Flatten styles: expo-router's <Link asChild> renders through a Radix
          <Slot>, which (SDK 57+) rejects an ARRAY style on its direct child.
          StyleSheet.flatten yields a single style object — same visual result. */}
      <Pressable style={StyleSheet.flatten([styles.link, { backgroundColor: t.card, borderColor: t.border }])}>
        <Text style={[styles.linkLabel, { color: t.text }]}>{label}</Text>
        <Text style={[styles.muted, { color: t.textMuted }]}>{hint}</Text>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  h1: { fontSize: 28, fontWeight: "800" },
  sub: { fontSize: 14, marginBottom: 12 },
  card: { borderWidth: 1, borderRadius: 12, padding: 16, marginBottom: 12, gap: 8 },
  cardTitle: { fontSize: 14, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5 },
  big: { fontSize: 32, fontWeight: "800" },
  muted: { fontSize: 13 },
  link: { borderWidth: 1, borderRadius: 12, padding: 16, gap: 2 },
  linkLabel: { fontSize: 16, fontWeight: "700" },
});
