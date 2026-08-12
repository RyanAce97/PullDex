/**
 * PullDex Desktop — Electron Main Process
 *
 * Responsibilities:
 * 1. Find a free local port
 * 2. Spawn the bundled FastAPI backend
 * 3. Wait for the backend to become ready
 * 4. Load the React frontend (served by FastAPI)
 * 5. Gracefully shut down the backend on quit
 */

const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const net = require("net");
const fs = require("fs");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const PREFERRED_PORT = 18321;
const HEALTH_CHECK_INTERVAL_MS = 200;
const HEALTH_CHECK_TIMEOUT_MS = 20000;
const BACKEND_SHUTDOWN_TIMEOUT_MS = 5000;

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

function getResourcesPath() {
  // In packaged app: resources are in the extraResources directory
  if (app.isPackaged) {
    return path.join(process.resourcesPath);
  }
  // In development: resources are relative to this file
  return path.join(__dirname, "resources");
}

function getBackendExePath() {
  const resources = getResourcesPath();
  return path.join(resources, "backend", "pulldex-backend.exe");
}

function getSeedDbPath() {
  const resources = getResourcesPath();
  return path.join(resources, "seed", "pulldex_seed.db");
}

function getUserDataPath() {
  // Use LOCALAPPDATA on Windows
  const localAppData = process.env.LOCALAPPDATA;
  if (localAppData) {
    return path.join(localAppData, "PullDex");
  }
  // Fallback to Electron's userData
  return app.getPath("userData");
}

function getUserDbPath() {
  return path.join(getUserDataPath(), "pulldex.db");
}

function getLogPath() {
  return path.join(getUserDataPath(), "logs");
}

// ---------------------------------------------------------------------------
// Port detection
// ---------------------------------------------------------------------------

function isPortFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(port, "127.0.0.1", () => {
      server.close(() => resolve(true));
    });
    server.on("error", () => resolve(false));
  });
}

async function findFreePort() {
  if (await isPortFree(PREFERRED_PORT)) {
    return PREFERRED_PORT;
  }
  // Find a random free port
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

// ---------------------------------------------------------------------------
// Backend process management
// ---------------------------------------------------------------------------

let backendProcess = null;
let backendPort = null;
let backendOutput = "";

function startBackend(port) {
  const exePath = getBackendExePath();
  const userDbPath = getUserDbPath();
  const seedDbPath = getSeedDbPath();
  const logDir = getLogPath();

  // Ensure log directory exists
  fs.mkdirSync(logDir, { recursive: true });

  // Ensure user data directory exists
  fs.mkdirSync(path.dirname(userDbPath), { recursive: true });

  const databaseUrl = `sqlite:///${userDbPath.replace(/\\/g, "/")}`;

  console.log(`Starting backend: ${exePath}`);
  console.log(`  Port: ${port}`);
  console.log(`  Database: ${databaseUrl}`);
  console.log(`  Seed DB: ${seedDbPath}`);

  const env = {
    ...process.env,
    PULLDEX_PORT: String(port),
    PULLDEX_DESKTOP: "true",
    DATABASE_URL: databaseUrl,
    PULLDEX_SEED_DB: seedDbPath,
  };

  backendProcess = spawn(exePath, [], {
    env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  backendProcess.stdout.on("data", (data) => {
    const text = data.toString();
    backendOutput += text;
    console.log(`[backend] ${text.trim()}`);
  });

  backendProcess.stderr.on("data", (data) => {
    const text = data.toString();
    backendOutput += text;
    console.error(`[backend] ${text.trim()}`);
  });

  backendProcess.on("error", (err) => {
    console.error(`Backend process error: ${err.message}`);
    backendOutput += `\nProcess error: ${err.message}`;
  });

  backendProcess.on("exit", (code, signal) => {
    console.log(`Backend exited with code ${code}, signal ${signal}`);
    backendProcess = null;
  });

  // Write log file
  const logFile = path.join(logDir, "backend.log");
  const logStream = fs.createWriteStream(logFile, { flags: "w" });
  backendProcess.stdout.pipe(logStream);
  backendProcess.stderr.pipe(logStream);

  return backendProcess;
}

function waitForBackend(port) {
  const startTime = Date.now();
  const url = `http://127.0.0.1:${port}/health`;

  return new Promise((resolve, reject) => {
    const check = () => {
      if (Date.now() - startTime > HEALTH_CHECK_TIMEOUT_MS) {
        reject(new Error(
          `Backend failed to start within ${HEALTH_CHECK_TIMEOUT_MS / 1000}s.\n\n` +
          `Backend output:\n${backendOutput.slice(-2000)}`
        ));
        return;
      }

      // If backend process has already exited, don't keep polling
      if (!backendProcess) {
        reject(new Error(
          `Backend process exited unexpectedly.\n\n` +
          `Backend output:\n${backendOutput.slice(-2000)}`
        ));
        return;
      }

      const http = require("http");
      const req = http.get(url, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          setTimeout(check, HEALTH_CHECK_INTERVAL_MS);
        }
      });
      req.on("error", () => {
        setTimeout(check, HEALTH_CHECK_INTERVAL_MS);
      });
      req.setTimeout(1000, () => {
        req.destroy();
        setTimeout(check, HEALTH_CHECK_INTERVAL_MS);
      });
    };

    check();
  });
}

function stopBackend() {
  if (!backendProcess) return Promise.resolve();

  return new Promise((resolve) => {
    const timeout = setTimeout(() => {
      // Force kill if graceful shutdown fails
      if (backendProcess) {
        console.log("Force killing backend process...");
        backendProcess.kill("SIGKILL");
      }
      resolve();
    }, BACKEND_SHUTDOWN_TIMEOUT_MS);

    backendProcess.on("exit", () => {
      clearTimeout(timeout);
      resolve();
    });

    // On Windows, SIGTERM doesn't work well — use taskkill for tree kill
    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", String(backendProcess.pid), "/T", "/F"], {
        windowsHide: true,
      });
    } else {
      backendProcess.kill("SIGTERM");
    }
  });
}

// ---------------------------------------------------------------------------
// Window management
// ---------------------------------------------------------------------------

let mainWindow = null;

function createSplashWindow() {
  const splash = new BrowserWindow({
    width: 400,
    height: 300,
    frame: false,
    transparent: false,
    resizable: false,
    center: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });
  splash.loadFile(path.join(__dirname, "splash.html"));
  return splash;
}

function createMainWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    show: false,
    title: "PullDex",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${port}/`);

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  // Remove the default menu bar
  mainWindow.setMenuBarVisibility(false);

  return mainWindow;
}

function showErrorWindow(errorMessage) {
  const errorWin = new BrowserWindow({
    width: 700,
    height: 500,
    title: "PullDex — Startup Error",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  const errorHtml = path.join(__dirname, "error.html");
  errorWin.loadFile(errorHtml);

  // Pass error message to the error page via a query param
  errorWin.webContents.on("did-finish-load", () => {
    errorWin.webContents.executeJavaScript(
      `document.getElementById("error-details").textContent = ${JSON.stringify(errorMessage)};`
    );
  });

  errorWin.setMenuBarVisibility(false);
  return errorWin;
}

// ---------------------------------------------------------------------------
// Application lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
  let splash = null;

  try {
    splash = createSplashWindow();

    // 1. Find a free port
    backendPort = await findFreePort();
    console.log(`Using port: ${backendPort}`);

    // 2. Start the backend
    startBackend(backendPort);

    // 3. Wait for the backend to be ready
    await waitForBackend(backendPort);

    // 4. Create main window and load the app
    createMainWindow(backendPort);

    // 5. Close splash once main window is showing
    if (mainWindow) {
      mainWindow.once("ready-to-show", () => {
        if (splash && !splash.isDestroyed()) {
          splash.close();
        }
      });
    }
  } catch (error) {
    console.error("Startup failed:", error.message);
    if (splash && !splash.isDestroyed()) {
      splash.close();
    }
    showErrorWindow(error.message);
  }
});

app.on("window-all-closed", async () => {
  await stopBackend();
  app.quit();
});

app.on("before-quit", async (event) => {
  if (backendProcess) {
    event.preventDefault();
    await stopBackend();
    app.quit();
  }
});

// Ensure backend is killed if the app crashes
process.on("exit", () => {
  if (backendProcess) {
    backendProcess.kill();
  }
});

process.on("SIGINT", async () => {
  await stopBackend();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await stopBackend();
  process.exit(0);
});
