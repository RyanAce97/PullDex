/** @type {import('@jest/types').Config.InitialOptions} */
// React Native component/render tests (jest-expo preset). Separate from the
// node-based DB tests in jest.config.cjs so the two environments don't clash.
const path = require("path");

module.exports = {
  preset: "jest-expo",
  roots: ["<rootDir>/__tests__/components"],
  testMatch: ["**/*.test.tsx"],
  moduleNameMapper: {
    "^@pulldex/shared$": path.resolve(__dirname, "../../packages/shared/src/index.ts"),
  },
  transformIgnorePatterns: [
    "node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg))",
  ],
};
