// Metro configuration for the PullDex mobile app in a monorepo.
//
// The app lives at apps/mobile but imports @pulldex/shared from
// packages/shared (outside the project root). We therefore watch the repo
// root and let Metro resolve modules from both the app and the repo root.
const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const repoRoot = path.resolve(projectRoot, "..", "..");

const config = getDefaultConfig(projectRoot);

// Watch the whole repo so changes to packages/shared are picked up.
config.watchFolders = [repoRoot];

// Resolve node_modules from the app first, then the repo root.
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(repoRoot, "node_modules"),
];

// The bundled catalogue is JSON (already a default sourceExt), but ensure it.
if (!config.resolver.sourceExts.includes("json")) {
  config.resolver.sourceExts.push("json");
}

module.exports = config;
