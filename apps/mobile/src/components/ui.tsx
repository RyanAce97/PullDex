import React from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../theme";

export function Screen({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  const t = useTheme();
  return (
    <SafeAreaView style={[{ flex: 1, backgroundColor: t.bg }, style]} edges={["top", "left", "right"]}>
      {children}
    </SafeAreaView>
  );
}

export function LoadingState({ message }: { message?: string }) {
  const t = useTheme();
  return (
    <View style={styles.centre}>
      <ActivityIndicator size="large" color={t.accent} />
      {message ? <Text style={[styles.muted, { color: t.textMuted }]}>{message}</Text> : null}
    </View>
  );
}

export function ErrorState({ message }: { message: string }) {
  const t = useTheme();
  return (
    <View style={styles.centre}>
      <Text style={{ fontSize: 32 }}>⚠️</Text>
      <Text style={[styles.title, { color: t.text }]}>Something went wrong</Text>
      <Text style={[styles.muted, { color: t.textMuted }]}>{message}</Text>
    </View>
  );
}

export function EmptyState({ icon = "🔍", message }: { icon?: string; message: string }) {
  const t = useTheme();
  return (
    <View style={styles.centre}>
      <Text style={{ fontSize: 32 }}>{icon}</Text>
      <Text style={[styles.muted, { color: t.textMuted, marginTop: 8 }]}>{message}</Text>
    </View>
  );
}

export function OwnershipBadge({ owned, large }: { owned: boolean; large?: boolean }) {
  const t = useTheme();
  const bg = owned ? t.ownedBg : t.missingBg;
  const fg = owned ? t.owned : t.missing;
  return (
    <View
      style={{
        backgroundColor: bg,
        paddingHorizontal: large ? 20 : 10,
        paddingVertical: large ? 12 : 4,
        borderRadius: 999,
        alignSelf: "flex-start",
      }}
    >
      <Text style={{ color: fg, fontWeight: "700", fontSize: large ? 20 : 12 }}>
        {owned ? "✓ Owned" : "Not Owned"}
      </Text>
    </View>
  );
}

export function ProgressBar({ percentage }: { percentage: number }) {
  const t = useTheme();
  return (
    <View style={{ height: 10, borderRadius: 999, backgroundColor: t.cardAlt, overflow: "hidden" }}>
      <View
        style={{
          width: `${Math.max(0, Math.min(100, percentage))}%`,
          height: "100%",
          backgroundColor: t.accent,
        }}
      />
    </View>
  );
}

export function StatCard({ label, value }: { label: string; value: string | number }) {
  const t = useTheme();
  return (
    <View style={[stat.card, { backgroundColor: t.card, borderColor: t.border }]}>
      <Text style={[stat.label, { color: t.textMuted }]}>{label}</Text>
      <Text style={[stat.value, { color: t.text }]}>{value}</Text>
    </View>
  );
}

const stat = StyleSheet.create({
  card: { flex: 1, minWidth: 140, borderWidth: 1, borderRadius: 12, padding: 14 },
  label: { fontSize: 12 },
  value: { fontSize: 24, fontWeight: "800", marginTop: 2 },
});

const styles = StyleSheet.create({
  centre: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24, gap: 6 },
  title: { fontSize: 18, fontWeight: "700", marginTop: 8 },
  muted: { fontSize: 14, textAlign: "center" },
});
