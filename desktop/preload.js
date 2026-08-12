/**
 * PullDex Desktop — Preload Script
 *
 * Runs in the renderer process context before the page loads.
 * Exposes a limited API via contextBridge for security.
 */

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("pulldex", {
  platform: process.platform,
  version: process.env.npm_package_version || "0.1.0",
});
