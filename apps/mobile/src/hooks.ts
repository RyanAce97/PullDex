/**
 * React hooks over the repository. These provide the screens with data +
 * refresh, all backed by the local SQLite DB (offline). A simple in-memory
 * version counter triggers re-fetch after mutations so ownership-derived views
 * (Collection, Pokédex, Card Show, Binder) update immediately.
 */

import { useCallback, useEffect, useState } from "react";
import type { SQLiteDatabase } from "expo-sqlite";
import type { CollectionProgress, SpeciesOwnership } from "@pulldex/shared";

import { useDatabase } from "./db/provider";
import { getProgress, getSpeciesOwnership } from "./db/repository";

// A trivial global "data version" bumped on any collection mutation so all
// mounted hooks re-fetch. Keeps ownership-derived UI consistent without a
// heavier state library for the MVP.
let dataVersion = 0;
const listeners = new Set<() => void>();

export function bumpDataVersion() {
  dataVersion += 1;
  listeners.forEach((l) => l());
}

function useDataVersion(): number {
  const [v, setV] = useState(dataVersion);
  useEffect(() => {
    const l = () => setV(dataVersion);
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, []);
  return v;
}

/** Public: subscribe to the data version so a screen re-fetches after mutations. */
export function useDataVersionValue(): number {
  return useDataVersion();
}

export function useSpeciesOwnership() {
  const db = useDatabase();
  const version = useDataVersion();
  const [rows, setRows] = useState<SpeciesOwnership[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!db) return;
    setError(null);
    getSpeciesOwnership(db)
      .then((r) => !cancelled && setRows(r))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [db, version]);

  return { rows, loading: rows === null && error === null, error };
}

export function useProgress() {
  const db = useDatabase();
  const version = useDataVersion();
  const [progress, setProgress] = useState<CollectionProgress | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!db) return;
    getProgress(db).then((p) => !cancelled && setProgress(p));
    return () => {
      cancelled = true;
    };
  }, [db, version]);

  return progress;
}

/** Run a mutation against the DB, then bump the data version to refresh views. */
export function useMutation() {
  const db = useDatabase();
  return useCallback(
    async (fn: (db: SQLiteDatabase) => Promise<void>) => {
      if (!db) return;
      await fn(db);
      bumpDataVersion();
    },
    [db],
  );
}
