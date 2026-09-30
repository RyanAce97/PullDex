/** @type {import('ts-jest').JestConfigWithTsJest} */
// Node-based tests for the mobile DATA LAYER (schema, migrations, repository).
// These do NOT run React Native. They exercise the real schema SQL and
// repository queries against an in-process SQLite (better-sqlite3) via a thin
// adapter that mimics the expo-sqlite async surface. UI is validated separately
// by `tsc --noEmit` + Expo tooling.
const path = require("path");

module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  roots: ["<rootDir>/src", "<rootDir>/__tests__"],
  testMatch: ["**/*.test.ts"],
  moduleNameMapper: {
    // Resolve the shared workspace package from source.
    "^@pulldex/shared$": path.resolve(__dirname, "../../packages/shared/src/index.ts"),
    // Swap the native expo-sqlite for a Node adapter in tests only.
    "^expo-sqlite$": path.resolve(__dirname, "__tests__/support/expoSqliteAdapter.ts"),
    // The catalogue JSON is large; tests use a tiny fixture instead.
    "\\.\\./\\.\\./assets/catalogue/catalogue.json$": path.resolve(
      __dirname,
      "__tests__/support/catalogueFixture.ts",
    ),
  },
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: {
          jsx: "react-jsx",
          esModuleInterop: true,
          types: ["jest", "node"],
          // TS6 flags baseUrl as deprecated; ignore for the test transform.
          ignoreDeprecations: "6.0",
        },
      },
    ],
  },
};
