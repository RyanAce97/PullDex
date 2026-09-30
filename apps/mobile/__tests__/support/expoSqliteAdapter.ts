/**
 * Test-only adapter that mimics the subset of the expo-sqlite async API used by
 * the mobile data layer, backed by Node's built-in `node:sqlite` (DatabaseSync).
 *
 * Using the built-in avoids a fragile native dependency (better-sqlite3) whose
 * prebuilt binaries must match the exact Node ABI — which broke when the
 * environment's Node version changed. `node:sqlite` ships with Node (>=22.5),
 * needs no native build, and exposes the same prepare().run/get/all + exec API.
 *
 * This lets the REAL schema SQL (schema.ts), seeding (seed.ts) and repository
 * queries (repository.ts) run unchanged inside Node/jest, so the tests exercise
 * genuine SQL behaviour rather than mocks.
 */

// eslint-disable-next-line @typescript-eslint/no-var-requires
const { DatabaseSync } = require("node:sqlite") as typeof import("node:sqlite");

type Params = unknown[];
type RawDb = InstanceType<typeof DatabaseSync>;

class TxAdapter {
  constructor(protected raw: RawDb) {}

  async execAsync(sql: string): Promise<void> {
    this.raw.exec(sql);
  }

  async runAsync(sql: string, params: Params = []): Promise<{ changes: number; lastInsertRowId: number }> {
    const info = this.raw.prepare(sql).run(...(normalize(params) as never[]));
    return { changes: Number(info.changes), lastInsertRowId: Number(info.lastInsertRowid) };
  }

  async getFirstAsync<T>(sql: string, params: Params = []): Promise<T | null> {
    const row = this.raw.prepare(sql).get(...(normalize(params) as never[]));
    return (row as T) ?? null;
  }

  async getAllAsync<T>(sql: string, params: Params = []): Promise<T[]> {
    return this.raw.prepare(sql).all(...(normalize(params) as never[])) as T[];
  }
}

export class SQLiteDatabase extends TxAdapter {
  async withExclusiveTransactionAsync(fn: (tx: TxAdapter) => Promise<void>): Promise<void> {
    this.raw.exec("BEGIN");
    try {
      await fn(this);
      this.raw.exec("COMMIT");
    } catch (e) {
      this.raw.exec("ROLLBACK");
      throw e;
    }
  }

  closeSync(): void {
    this.raw.close();
  }
}

function normalize(params: Params): unknown[] {
  // node:sqlite binds null (not undefined); coerce booleans to 0/1 to match
  // the integer columns used for is_promo / is_binder_card.
  return params.map((p) => {
    if (p === undefined || p === null) return null;
    if (typeof p === "boolean") return p ? 1 : 0;
    return p;
  });
}

/** Mirrors expo-sqlite's openDatabaseAsync(name). Uses in-memory unless a path. */
export async function openDatabaseAsync(name: string): Promise<SQLiteDatabase> {
  const raw = new DatabaseSync(name === ":memory:" ? ":memory:" : name);
  return new SQLiteDatabase(raw);
}

export default { openDatabaseAsync };
