# PullDex Desktop Application

This document explains how to build, install, and use PullDex as a standalone Windows desktop application.

## Overview

PullDex Desktop bundles the FastAPI backend, React frontend, and all reference data into a single Windows installer. Users don't need Python, Node.js, or any development tools installed.

**Architecture:**
```
PullDex.exe (Electron shell)
  ├── React frontend (served as static files)
  ├── FastAPI backend (PyInstaller .exe)
  ├── Seed database (reference data: species, sets, cards)
  └── User database stored at %LOCALAPPDATA%\PullDex\pulldex.db
```

---

## Building the Desktop Application

### Prerequisites

On the development machine, you need:

- **Python 3.11+** with `uv` package manager
- **Node.js 18+** with `npm`
- **Windows** (PyInstaller builds a Windows exe)

### Quick Build (all steps)

```bash
cd desktop
node scripts/build.js
```

This runs all three steps in order. The final installer is at:
```
desktop/release/PullDex-Setup-0.1.0.exe
```

### Step-by-Step Build

#### 1. Build Frontend

```bash
cd frontend
npm run build
```

Produces `frontend/dist/` with the production React bundle.

#### 2. Build Backend (PyInstaller)

```bash
cd backend
uv run pip install pyinstaller
uv run pyinstaller --noconfirm desktop.spec
```

Produces `backend/dist/pulldex-backend/` containing the standalone backend executable.

#### 3. Build Electron Installer

```bash
cd desktop
npm install      # first time only
npm run build
```

Produces `desktop/release/PullDex-Setup-x.y.z.exe` (NSIS installer).

---

## Installation (End User)

1. Download `PullDex-Setup-x.y.z.exe`
2. Run the installer
3. Choose installation directory (or use default)
4. Click Install
5. Launch PullDex from Start Menu or Desktop shortcut

**No Python, Node.js, or development tools required.**

---

## How It Works

### First Launch

1. Electron starts and shows a splash screen
2. Backend process starts on a local port (127.0.0.1)
3. Backend checks for user database at `%LOCALAPPDATA%\PullDex\pulldex.db`
4. If no database exists: copies the bundled seed database (with all reference data)
5. Runs any pending Alembic migrations
6. Backend becomes ready, serves the React frontend
7. Electron loads the app in the main window

### Subsequent Launches

1. Electron starts, shows splash
2. Backend starts, finds existing database
3. Runs any pending migrations (usually none)
4. App loads with all existing collection data intact

---

## User Data

### Database Location

```
%LOCALAPPDATA%\PullDex\pulldex.db
```

Typically: `C:\Users\{YourName}\AppData\Local\PullDex\pulldex.db`

### Logs

```
%LOCALAPPDATA%\PullDex\logs\backend.log
```

### What's in the Database

- **Reference data:** 1,025 Pokémon species, 174+ TCG sets, 20,000+ cards
- **Your collection:** Species ownership, card entries, quantities

---

## Backup & Restore

### Manual Backup

Copy the database file to a safe location:

```
copy "%LOCALAPPDATA%\PullDex\pulldex.db" "D:\Backups\pulldex-backup.db"
```

### Restore

Replace the database file:

```
copy "D:\Backups\pulldex-backup.db" "%LOCALAPPDATA%\PullDex\pulldex.db"
```

⚠️ Close PullDex before copying the database file.

---

## Updating PullDex

### How Updates Work

1. Download the new installer
2. Run it (installs over the existing version)
3. Your collection is preserved — it lives in `%LOCALAPPDATA%`, not the install directory
4. On next launch, any new database migrations are applied automatically

### What Survives Updates

✅ Your collection entries
✅ Your card quantities
✅ All user-specific data

### What Gets Updated

- Application code (backend + frontend)
- Reference data (only if the new version includes updated species/sets/cards)
- Any new Alembic migrations for schema changes

---

## Uninstalling

### Standard Uninstall

Use Windows "Add or Remove Programs" or the uninstaller in the Start Menu.

**Your collection database is NOT deleted.** It remains at `%LOCALAPPDATA%\PullDex\`.

### Complete Removal (including user data)

After uninstalling, manually delete:
```
rmdir /s "%LOCALAPPDATA%\PullDex"
```

---

## Troubleshooting

### Application won't start

1. Check `%LOCALAPPDATA%\PullDex\logs\backend.log` for errors
2. Ensure no other process is using port 18321 (or the app will pick another)
3. Try deleting the log file and restarting
4. If database is corrupted: rename it, restart PullDex (creates fresh from seed), then restore your backup

### Backend process stays running after close

This shouldn't happen — Electron uses `taskkill /T /F` on Windows. If it does:
1. Open Task Manager
2. Look for `pulldex-backend.exe`
3. End the process

### Database migration failed

If an update includes a migration that fails:
1. The error appears in the startup error screen
2. Your original database is preserved (never deleted on failure)
3. Check `backend.log` for the specific SQL error
4. Report the issue with the log contents

---

## Development

### Running Development Mode (unchanged)

Frontend:
```bash
cd frontend
npm run dev       # Vite dev server on :5173
```

Backend:
```bash
cd backend
uv run uvicorn app.main:app --reload    # FastAPI on :8000
```

Both still work exactly as before. The desktop packaging changes are conditional and only activate when `PULLDEX_DESKTOP=true` is set.

### Testing Desktop Mode Locally

You can test the desktop startup logic without building a full package:

```bash
cd backend

# Set desktop env vars
set PULLDEX_DESKTOP=true
set DATABASE_URL=sqlite:///C:/Users/YourName/AppData/Local/PullDex/test.db
set PULLDEX_SEED_DB=C:/path/to/backups/pulldex_backup_initial_import.db
set PULLDEX_PORT=18321

uv run python -m app.desktop_entry
```

---

## Architecture Details

### Port Selection

The app tries port 18321 first. If unavailable, it picks a random free port. The port is only bound to `127.0.0.1` (localhost) — never exposed to the network.

### Security

- Backend only listens on localhost (127.0.0.1)
- Electron uses `contextIsolation: true` and `nodeIntegration: false`
- No shell or filesystem access from the renderer process
- Preload script exposes only minimal API via contextBridge

### Process Lifecycle

```
App Start → Spawn backend.exe → Poll /health → Load UI → User works
App Close → taskkill backend.exe (with child processes) → Quit
```

If the backend crashes, the error screen shows diagnostic information.
