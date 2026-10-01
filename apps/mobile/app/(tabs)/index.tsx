import { ScrollView, StyleSheet, Text, View } from "react-native";

import { Screen, ProgressBar, StatCard, LoadingState } from "../../src/components/ui";
import { useSummary } from "../../src/hooks";
import { useTheme } from "../../src/theme";

export default function Dashboard() {
  const t = useTheme();
  const summary = useSummary();

  if (!summary) {
    return (
      <Screen>
        <LoadingState message="Loading progress…" />
      </Screen>
    );
  }

  const { progress, totalCatalogueCards, totalSets, promoSets, ownedCardEntries } = summary;

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16 }}>
        <View>
          <Text style={[styles.h1, { color: t.text }]}>Living Dex Progress</Text>
          <Text style={[styles.sub, { color: t.textMuted }]}>PullDex · offline on this device</Text>
        </View>

        <View style={{ gap: 8 }}>
          <ProgressBar percentage={progress.percentage} />
          <Text style={[styles.progressLabel, { color: t.textMuted }]}>
            {progress.ownedSpecies} / {progress.totalSpecies} species · {progress.percentage}%
          </Text>
        </View>

        {/* Living Dex stat cards (mirrors desktop Dashboard) */}
        <View style={styles.grid}>
          <StatCard label="Total Species" value={progress.totalSpecies} />
          <StatCard label="Owned" value={progress.ownedSpecies} />
        </View>
        <View style={styles.grid}>
          <StatCard label="Missing" value={progress.missingSpecies} />
          <StatCard label="Completion" value={`${progress.percentage}%`} />
        </View>

        {/* Collection + catalogue summary */}
        <Text style={[styles.section, { color: t.textMuted }]}>Collection</Text>
        <View style={styles.grid}>
          <StatCard label="Owned cards" value={ownedCardEntries} />
          <StatCard label="Catalogue cards" value={totalCatalogueCards.toLocaleString()} />
        </View>
        <View style={styles.grid}>
          <StatCard label="Sets" value={totalSets} />
          <StatCard label="Promo sets" value={promoSets} />
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  h1: { fontSize: 26, fontWeight: "800" },
  sub: { fontSize: 13, marginTop: 2 },
  progressLabel: { fontSize: 13 },
  section: { fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 4 },
  grid: { flexDirection: "row", gap: 12 },
});
