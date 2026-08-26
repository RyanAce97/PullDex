# PullDex

A Pokémon TCG Living Pokédex tracker for collectors who complete their Pokédex by pulling cards from sealed booster packs.

PullDex helps you track which Pokémon species you've collected from opening packs, visualise your collection in a digital binder, and get smart recommendations for which sets to buy next to fill the gaps in your National Pokédex.

**Current version: 0.3.1**

---

## What Is PullDex?

PullDex is a Windows desktop application for tracking a Pokémon Living Pokédex through the Pokémon Trading Card Game.

The core concept: you're tracking **which Pokémon you've obtained from opening booster packs**, not simply buying individual singles. Each card can be associated with a Pokémon species, and PullDex shows your collection progress against the complete 1,025-species National Pokédex.

PullDex answers the question: *"Which packs should I buy next to fill the most gaps in my Pokédex?"*

---

## Features

### Collection Tracking

- Track ownership of all 1,025 National Pokédex Pokémon
- Species-level tracking ("I own this Pokémon") or card-level tracking with quantities
- Search and add cards from a database of 20,000+ Pokémon TCG cards across 175 sets
- Filter cards by Pokémon species, set name, rarity, and card number
- Card image preview — click any card thumbnail for an enlarged view

### Digital Binder

- Visual representation of your collection as a physical card binder
- Fixed National Pokédex positions (#1–#1025) with three slot states: owned card, owned placeholder, or empty pocket
- Configurable grid layout from 2×2 through 5×5 (default 5×4 = 20 cards per page)
- Choose which card appears in each Pokémon's binder slot when you own multiple
- Quantity badges showing total copies per species

### Binder Navigation

- **Pokémon search** — search by name or National Dex number, instantly jump to the correct binder page
- **Direct page navigation** — editable page number, first/previous/next/last buttons
- **Keyboard shortcuts** — arrow keys for page navigation, Ctrl+F to focus search, Home/End for first/last page
- **Responsive sizing** — binder grid scales to fit the application window while maintaining card aspect ratios
- **Session persistence** — binder page position is remembered while navigating the app, resets on application restart
- **Dex range display** — shows which Pokémon numbers are on the current page

### Pack Recommendations

- Set recommendations ranked by how many missing Pokémon each set can provide
- Coverage percentage, species density, and set details
- Missing species drill-down per recommended set

### Set Browser

- Browse all available Pokémon TCG sets
- View set details and missing species information

### Pokédex

- Full National Pokédex browser with ownership status
- Species detail pages showing all available cards for each Pokémon
- Add cards directly from species detail pages

### Profiles & Settings

- Multiple local profiles with independent collections
- Separate binder layout preferences per profile
- Create, rename, switch, and delete profiles

### Import, Export & Backup

- Export your collection as a portable `.pulldex` file
- **Replace** — restore a collection from an export
- **Merge** — combine an export with your current collection (additive quantities)
- **New Profile** — import as a separate profile to keep existing data intact
- Full database backup/restore using SQLite's safe backup mechanism (via Settings page)

### Contextual Navigation

- Back buttons throughout the application return to the page you came from
- Navigating from the Binder to a species detail page and back preserves your binder position
- Set details pages return to Sets or Recommendations depending on origin

---

## Digital Binder

The Binder is PullDex's core visualisation — a digital card binder ordered by National Pokédex number.

Each Pokémon has a fixed position in the binder. As you add cards to your collection, they appear in their Pokédex slots. The binder shows at a glance which species you've collected and which are still missing.

**Key capabilities:**

- **Search** — type a Pokémon name (e.g. "Pikachu") or Dex number (e.g. "25") to instantly find and jump to any species. Search results show the page number and selecting a result navigates directly there.
- **Page navigation** — type a page number directly, or use first/previous/next/last buttons. Keyboard arrow keys also work.
- **Card selection** — when you own multiple cards for the same Pokémon, choose which one appears in your binder.
- **Card preview** — click any card in the binder to see a larger view with set information, rarity, and card number.
- **Responsive layout** — the binder grid automatically scales to fit your window while keeping cards legible and maintaining proper aspect ratios.
- **Session memory** — your current binder page is remembered while you navigate elsewhere in the app. Restarting PullDex resets to page 1.

---

## Installation

### Windows

Download the latest installer from the release output:

```
PullDex Setup 0.3.1.exe
```

Run the installer and follow the prompts. PullDex is self-contained — no Python, Node.js, or developer tools are required.

After installation, launch PullDex from the Start Menu or Desktop shortcut.

### First Launch

On first launch, PullDex initialises a fresh database with all reference data (species, sets, cards) and an empty collection. The application is ready to use immediately.

---

## User Data & Backup

### Database Location

Your collection database is stored at:

```
%LOCALAPPDATA%\PullDex\pulldex.db
```

This file contains your collection, profiles, and binder selections. **Do not delete this file** unless you want to reset your collection entirely.

### Recommended Backup

Use **Settings → Backup** within PullDex to create safe database backups. This uses SQLite's backup API and is the recommended approach.

For additional safety, you can also manually copy the database file above.

### Data Safety

- Collection data is never modified by reference-data updates or application upgrades
- Uninstalling PullDex does not delete your collection database
- Database migrations run automatically on updates and preserve all existing data

---

## Data Sources

PullDex uses multiple data sources to maintain comprehensive card coverage:

| Source | Role | Data |
|--------|------|------|
| [Pokémon TCG API](https://pokemontcg.io/) | Primary | Card data, sets, images, rarity |
| [TCGdex](https://tcgdex.dev/) | Supplementary | Promo cards, gap-filling, species validation |
| [PokéAPI](https://pokeapi.co/) | Species | National Pokédex species list |

### Why Two Card Sources?

The Pokémon TCG API is comprehensive but does not include all promotional cards. In particular, the **First Partner Illustration Collection** (27 cards celebrating all starter Pokémon across 9 generations) and recent Scarlet & Violet promotional cards are only available from TCGdex.

PullDex imports these supplementary cards to ensure complete promo coverage. The supplementary import is idempotent and never duplicates cards that exist in the primary source.

### Reference Data

| Data | Count |
|------|-------|
| Pokémon species | 1,025 |
| TCG sets | 175 |
| TCG cards | 20,594 |
| Cards linked to species | 17,387 |

The application includes validated species-mapping repair tooling that corrects known data inconsistencies from the primary API without modifying collection data.

---

## Development

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

API runs on `http://localhost:8000` with interactive docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev server runs on `http://localhost:5173`.

### Tests

```bash
cd backend
uv run pytest
```

375 passing tests covering services, routes, importers, species mapping, and data integrity.

### TypeScript Check

```bash
cd frontend
npx tsc --noEmit
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

Output: `desktop/release/PullDex Setup 0.3.1.exe`

See [docs/DESKTOP.md](docs/DESKTOP.md) for build details and troubleshooting.

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
│   │   ├── scripts/      CLI utilities
│   │   ├── config.py     Application configuration
│   │   ├── database.py   Engine, sessions, migrations, species repair
│   │   └── main.py       FastAPI app + static file serving
│   ├── tests/            375 automated tests
│   ├── alembic/          Database migrations
│   └── desktop.spec      PyInstaller configuration
├── frontend/         React + TypeScript + Vite + Tailwind + TanStack Query
│   └── src/
│       ├── api/          Typed API client functions
│       ├── types/        TypeScript interfaces
│       ├── hooks/        React Query wrappers
│       ├── components/   Reusable UI (CardPreviewModal, BinderSearch, etc.)
│       ├── pages/        Route-level page components
│       └── lib/          Query keys, constants, binder state
├── desktop/          Electron shell + build scripts
│   ├── main.js           Electron main process
│   ├── scripts/build.js  Full build orchestration
│   └── electron-builder.yml  NSIS installer configuration
├── database/         Development database (gitignored)
├── backups/          Seed database for fresh installations
└── docs/             Specifications and reference documentation
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLModel, SQLite, Alembic, uvicorn |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Desktop | Electron 31, electron-builder, PyInstaller |
| Database | SQLite (via Python stdlib + SQLModel/SQLAlchemy) |
| Testing | pytest (375 tests), TypeScript strict mode |

---

## License

This project does not currently have a license file.
