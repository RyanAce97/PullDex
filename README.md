# PullDex

A Pokémon TCG Living Pokédex tracker for collectors who complete their Pokédex by pulling cards from sealed booster packs.

PullDex helps you track which Pokémon species you've collected, visualise your collection in a digital binder, and get smart recommendations for which sets to buy next to fill the gaps in your National Pokédex.

**Current version: 0.2.0**

---

## Features

### Collection Tracking

- Track ownership of all 1,025 National Pokédex Pokémon
- Species-level tracking (quick "I own this Pokémon") or card-level tracking with quantities
- Search and add cards from a database of 20,479 Pokémon TCG cards across 174 sets
- Filter by Pokémon species, set, rarity, and card number

### Digital Binder

- Visual representation of your collection as a physical card binder
- Fixed National Pokédex positions (#1–#1025) with owned cards, empty pockets, and species-only placeholders
- Configurable grid layout: 2×2 through 5×5 (default 5×4 = 20 cards per page)
- Choose which card appears in each Pokémon's binder slot when you own multiple
- Quantity badges for cards with multiple copies
- Card detail modal with full metadata

### Pack Recommendations

- Intelligent set recommendations ranked by how many missing Pokémon each set can provide
- Coverage percentage, species density, and set details
- Missing species drill-down per recommended set

### Local Profiles

- Multiple local profiles with independent collections on the same computer
- Separate binder preferences per profile
- Create, rename, switch, and delete profiles
- Not online accounts — purely local collection separation

### Import & Export

- Export your collection as a portable `.pulldex` file
- **Import & Replace** — restore a collection from an export (idempotent)
- **Import & Merge** — combine an export with your current collection (additive quantities)
- Import as a new profile to keep existing collection intact
- Full database backup/restore using SQLite's safe backup mechanism

### Desktop Application

- Native Windows desktop app (Electron + FastAPI + React)
- Self-contained — no Python, Node.js, or development tools required
- User data stored safely at `%LOCALAPPDATA%\PullDex\pulldex.db`
- Automatic database migrations on update
- Collection preserved across application updates and uninstalls

---

## Screenshots

> Screenshots not yet included in the repository. Recommended additions:
> - Dashboard with progress overview
> - Digital binder (5×4 layout with owned cards and empty pockets)
> - Card search with filters
> - Settings/profile management

---

## Download

### PullDex v0.2.0 (Current)

Windows installer: `PullDex Setup 0.2.0.exe`

Built from `desktop/release/` after running the build pipeline.

### Previous Releases

- v0.1.0 — Initial release with core collection tracking, card search, and recommendations

---

## Upgrading from v0.1.0

PullDex v0.2.0 performs an in-place upgrade of the existing installation:

1. Your collection database at `%LOCALAPPDATA%\PullDex\pulldex.db` is **never overwritten** by the installer
2. On first launch after upgrading, database migrations run automatically
3. All existing collection entries, quantities, and ownership data are preserved
4. New features (profiles, binder, import/export) become available immediately

**Recommended:** Before upgrading, make a manual copy of your database:

```
%LOCALAPPDATA%\PullDex\pulldex.db
```

v0.1.0 does not have in-app backup functionality, so copying the file manually is the safest approach. v0.2.0 adds proper backup/restore within the Settings page.

---

## Reference Data

PullDex includes a complete Pokémon TCG reference database:

| Data | Count |
|------|-------|
| Pokémon species | 1,025 |
| TCG sets | 174 |
| TCG cards | 20,479 |
| Cards linked to species | 17,279 |

Card and set data is sourced from the [Pokémon TCG API](https://pokemontcg.io/). Species data is sourced from [PokéAPI](https://pokeapi.co/).

For cards where the Pokémon TCG API does not provide National Pokédex numbers, PullDex uses a validated name-based fallback to correctly associate cards with their Pokémon species.

---

## Development Setup

### Prerequisites

- Python 3.11+ (managed via [uv](https://docs.astral.sh/uv/))
- Node.js 18+
- npm

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

The API runs on `http://localhost:8000` with interactive docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies API calls to the backend via `VITE_API_URL=http://localhost:8000` (configured in `frontend/.env`).

### Running Tests

```bash
cd backend
uv run pytest
```

---

## Project Structure

```
PullDex/
├── backend/          Python: FastAPI + SQLModel + SQLite + Alembic
│   ├── app/
│   │   ├── models/       SQLModel table models
│   │   ├── schemas/      Pydantic response schemas
│   │   ├── services/     Business logic + importers + API clients
│   │   ├── routers/      FastAPI route handlers
│   │   ├── scripts/      CLI utilities (import, debug, fix)
│   │   ├── config.py     Application configuration
│   │   ├── database.py   Engine, sessions, migrations, seeding
│   │   └── main.py       FastAPI app + static file serving
│   ├── tests/            Automated test suite
│   ├── alembic/          Database migrations
│   └── desktop.spec      PyInstaller packaging configuration
├── frontend/         React + TypeScript + Vite + Tailwind + TanStack Query
│   └── src/
│       ├── api/          Typed API client functions
│       ├── types/        TypeScript interfaces
│       ├── hooks/        React Query wrappers
│       ├── components/   Reusable UI components
│       ├── pages/        Route-level page components
│       └── lib/          Query keys, constants
├── desktop/          Electron shell + build scripts
│   ├── main.js           Electron main process
│   ├── scripts/build.js  Full build orchestration
│   └── electron-builder.yml  NSIS installer configuration
├── database/         Development database (gitignored)
├── backups/          Seed database for fresh installations
└── docs/             Additional documentation
```

---

## Building the Windows Installer

From the `desktop/` directory:

```bash
cd desktop
node scripts/build.js
```

This orchestrates:
1. Frontend production build (Vite)
2. Backend packaging (PyInstaller one-folder)
3. Electron packaging + NSIS installer

Output: `desktop/release/PullDex Setup 0.2.0.exe`

For individual build steps:
```bash
node scripts/build.js --frontend-only
node scripts/build.js --backend-only
node scripts/build.js --electron-only
```

See [docs/DESKTOP.md](docs/DESKTOP.md) for detailed build and troubleshooting information.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLModel, SQLite, Alembic, uvicorn |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Desktop | Electron 31, electron-builder, PyInstaller |
| Database | SQLite (via Python stdlib + SQLModel/SQLAlchemy) |
| Testing | pytest (350 tests), TypeScript strict mode |

---

## Potential Future Improvements

- Auto-update support (electron-updater)
- Code signing certificate (removes Windows SmartScreen warning)
- Mobile responsive navigation
- Toast notifications
- Online accounts / cloud sync
- macOS / Linux builds
- First-run onboarding

---

## License

This project does not currently have a license file.
