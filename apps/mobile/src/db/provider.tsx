/**
 * Database lifecycle: open the on-device SQLite DB, run migrations, and seed
 * the catalogue on first launch. Exposes a React context so screens can access
 * the ready database and an init status for loading/error states.
 */

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import * as SQLite from "expo-sqlite";
import type { SQLiteDatabase } from "expo-sqlite";

import { DATABASE_NAME, runMigrations } from "./schema";
import { seedCatalogue } from "./seed";

export type DbStatus =
  | { state: "loading"; message: string }
  | { state: "ready"; db: SQLiteDatabase }
  | { state: "error"; error: string };

interface DbContextValue {
  status: DbStatus;
}

const DbContext = createContext<DbContextValue | undefined>(undefined);

/** Open, migrate, and seed the database. Returns the ready handle. */
export async function initDatabase(
  onProgress?: (message: string) => void,
): Promise<SQLiteDatabase> {
  onProgress?.("Opening database…");
  const db = await SQLite.openDatabaseAsync(DATABASE_NAME);

  onProgress?.("Applying migrations…");
  await runMigrations(db);

  onProgress?.("Loading card catalogue…");
  await seedCatalogue(db);

  return db;
}

export function DatabaseProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<DbStatus>({ state: "loading", message: "Starting…" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const db = await initDatabase((message) => {
          if (!cancelled) setStatus({ state: "loading", message });
        });
        if (!cancelled) setStatus({ state: "ready", db });
      } catch (err) {
        if (!cancelled) {
          setStatus({ state: "error", error: err instanceof Error ? err.message : String(err) });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(() => ({ status }), [status]);
  return <DbContext.Provider value={value}>{children}</DbContext.Provider>;
}

export function useDbStatus(): DbStatus {
  const ctx = useContext(DbContext);
  if (!ctx) throw new Error("useDbStatus must be used within a DatabaseProvider");
  return ctx.status;
}

/** Convenience hook: returns the DB when ready, else null. */
export function useDatabase(): SQLiteDatabase | null {
  const status = useDbStatus();
  return status.state === "ready" ? status.db : null;
}
