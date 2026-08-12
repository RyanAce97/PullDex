/**
 * Apply PullDex icon to the packaged Electron executable.
 *
 * electron-builder's signAndEditExecutable option is disabled in WSL
 * (due to winCodeSign symlink issues), so we apply the icon manually
 * using rcedit after packaging.
 *
 * This script finds rcedit in the electron-builder cache and uses it
 * to embed build/icon.ico into release/win-unpacked/PullDex.exe.
 */

const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const DESKTOP_DIR = __dirname.replace(/[\\/]scripts$/, "");
const EXE_PATH = path.join(DESKTOP_DIR, "release", "win-unpacked", "PullDex.exe");
const ICO_PATH = path.join(DESKTOP_DIR, "build", "icon.ico");

// Find rcedit in electron-builder cache
function findRcedit() {
  const cacheBase = path.join(
    process.env.LOCALAPPDATA || path.join(require("os").homedir(), "AppData", "Local"),
    "electron-builder",
    "Cache",
    "winCodeSign"
  );

  if (!fs.existsSync(cacheBase)) {
    return null;
  }

  const dirs = fs.readdirSync(cacheBase).filter((d) => {
    const full = path.join(cacheBase, d);
    return fs.statSync(full).isDirectory();
  });

  for (const dir of dirs) {
    const rcedit = path.join(cacheBase, dir, "rcedit-x64.exe");
    if (fs.existsSync(rcedit)) {
      return rcedit;
    }
  }
  return null;
}

// Main
if (!fs.existsSync(EXE_PATH)) {
  console.error(`ERROR: PullDex.exe not found at: ${EXE_PATH}`);
  console.error("Run electron-builder first to create the unpacked app.");
  process.exit(1);
}

if (!fs.existsSync(ICO_PATH)) {
  console.error(`ERROR: icon.ico not found at: ${ICO_PATH}`);
  process.exit(1);
}

const rcedit = findRcedit();
if (!rcedit) {
  console.error("ERROR: rcedit-x64.exe not found in electron-builder cache.");
  console.error("Run electron-builder once to download the required tools.");
  process.exit(1);
}

console.log(`Applying icon to PullDex.exe...`);
console.log(`  rcedit: ${rcedit}`);
console.log(`  exe:    ${EXE_PATH}`);
console.log(`  icon:   ${ICO_PATH}`);

try {
  execSync(`"${rcedit}" "${EXE_PATH}" --set-icon "${ICO_PATH}"`, {
    stdio: "inherit",
    shell: true,
  });
  console.log("Icon applied successfully.");
} catch (error) {
  console.error("ERROR: Failed to apply icon:", error.message);
  process.exit(1);
}
