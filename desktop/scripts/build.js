/**
 * PullDex Desktop — Build Orchestration Script
 *
 * Orchestrates the complete desktop build:
 *   1. Build frontend (Vite production build)
 *   2. Build backend (PyInstaller one-folder)
 *   3. Build Electron package/installer
 *
 * Run from the desktop/ directory:
 *   node scripts/build.js
 *
 * Or individual steps:
 *   node scripts/build.js --frontend-only
 *   node scripts/build.js --backend-only
 *   node scripts/build.js --electron-only
 */

const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.resolve(__dirname, "../..");
const FRONTEND_DIR = path.join(ROOT, "frontend");
const BACKEND_DIR = path.join(ROOT, "backend");
const DESKTOP_DIR = path.join(ROOT, "desktop");

const args = process.argv.slice(2);
const frontendOnly = args.includes("--frontend-only");
const backendOnly = args.includes("--backend-only");
const electronOnly = args.includes("--electron-only");
const buildAll = !frontendOnly && !backendOnly && !electronOnly;

function run(cmd, cwd, label) {
  console.log(`\n${"=".repeat(60)}`);
  console.log(`  ${label}`);
  console.log(`${"=".repeat(60)}`);
  console.log(`  > ${cmd}`);
  console.log(`  > cwd: ${cwd}\n`);

  try {
    execSync(cmd, {
      cwd,
      stdio: "inherit",
      shell: true,
    });
  } catch (error) {
    console.error(`\n❌ FAILED: ${label}`);
    process.exit(1);
  }
}

function checkPrerequisites() {
  // Check frontend dist will be available for backend build
  if ((buildAll || backendOnly) && !frontendOnly) {
    const distIndex = path.join(FRONTEND_DIR, "dist", "index.html");
    if (!fs.existsSync(distIndex) && !buildAll) {
      console.error("❌ Frontend dist not found. Run with --frontend-only first, or use no flags for full build.");
      process.exit(1);
    }
  }

  // Check seed database exists
  const seedDb = path.join(ROOT, "backups", "pulldex_backup_initial_import.db");
  if (!fs.existsSync(seedDb)) {
    console.error(`❌ Seed database not found at: ${seedDb}`);
    process.exit(1);
  }

  // Check backend PyInstaller output exists for electron build
  if (electronOnly) {
    const backendExe = path.join(BACKEND_DIR, "dist", "pulldex-backend", "pulldex-backend.exe");
    if (!fs.existsSync(backendExe)) {
      console.error("❌ Backend PyInstaller build not found. Run with --backend-only first.");
      process.exit(1);
    }
  }
}

// ---------------------------------------------------------------------------
// Build steps
// ---------------------------------------------------------------------------

function buildFrontend() {
  run("npm run build", FRONTEND_DIR, "Building frontend (Vite production build)");
}

function buildBackend() {
  // Ensure PyInstaller is available
  run("uv run pip install pyinstaller", BACKEND_DIR, "Installing PyInstaller");
  run("uv run pyinstaller --noconfirm desktop.spec", BACKEND_DIR, "Building backend (PyInstaller)");
}

function buildElectron() {
  // Ensure electron deps are installed
  if (!fs.existsSync(path.join(DESKTOP_DIR, "node_modules"))) {
    run("npm install", DESKTOP_DIR, "Installing Electron dependencies");
  }
  run("npm run build", DESKTOP_DIR, "Building Electron installer");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

console.log("╔══════════════════════════════════════════════════════════╗");
console.log("║  PullDex Desktop — Build Pipeline                        ║");
console.log("╚══════════════════════════════════════════════════════════╝");

checkPrerequisites();

if (buildAll || frontendOnly) {
  buildFrontend();
}

if (buildAll || backendOnly) {
  buildBackend();
}

if (buildAll || electronOnly) {
  buildElectron();
}

console.log(`\n${"=".repeat(60)}`);
console.log("  ✅ Build complete!");
console.log(`${"=".repeat(60)}`);

if (buildAll || electronOnly) {
  const releaseDir = path.join(DESKTOP_DIR, "release");
  console.log(`\n  Installer output: ${releaseDir}`);
  if (fs.existsSync(releaseDir)) {
    const files = fs.readdirSync(releaseDir).filter(f => f.endsWith(".exe"));
    files.forEach(f => console.log(`    → ${f}`));
  }
}

console.log("");
