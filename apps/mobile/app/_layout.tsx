import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { DatabaseProvider, useDbStatus } from "../src/db/provider";
import { LoadingState, ErrorState, Screen } from "../src/components/ui";
import { useTheme } from "../src/theme";

function Gate({ children }: { children: React.ReactNode }) {
  const status = useDbStatus();
  if (status.state === "loading") {
    return (
      <Screen>
        <LoadingState message={status.message} />
      </Screen>
    );
  }
  if (status.state === "error") {
    return (
      <Screen>
        <ErrorState message={status.error} />
      </Screen>
    );
  }
  return <>{children}</>;
}

function Navigator() {
  const t = useTheme();
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: t.card },
        headerTintColor: t.text,
        contentStyle: { backgroundColor: t.bg },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="species/[id]" options={{ title: "Pokémon" }} />
    </Stack>
  );
}

export default function RootLayout() {
  const t = useTheme();
  return (
    <SafeAreaProvider>
      <StatusBar style={t.mode === "dark" ? "light" : "dark"} />
      <DatabaseProvider>
        <Gate>
          <Navigator />
        </Gate>
      </DatabaseProvider>
    </SafeAreaProvider>
  );
}
