# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for PullDex desktop backend.

Builds a one-folder distribution containing:
  - The FastAPI application and all Python dependencies
  - Alembic migration scripts
  - Frontend production build (static files)
  - Seed database for new installations

Build command (run from backend/ directory):
    pyinstaller --noconfirm desktop.spec

Output:
    dist/pulldex-backend/
        pulldex-backend.exe
        _internal/
        ...
"""

import os
from pathlib import Path

# Paths relative to this spec file (which lives in backend/)
BACKEND_DIR = Path(os.path.abspath(SPECPATH))
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
ALEMBIC_DIR = BACKEND_DIR / "alembic"
SEED_DB = PROJECT_ROOT / "backups" / "pulldex_backup_initial_import.db"

# Validate required build artifacts exist
if not FRONTEND_DIST.is_dir():
    raise FileNotFoundError(
        f"Frontend dist not found at {FRONTEND_DIST}. "
        "Run 'npm run build' in frontend/ first."
    )

if not ALEMBIC_DIR.is_dir():
    raise FileNotFoundError(f"Alembic directory not found at {ALEMBIC_DIR}")

if not SEED_DB.is_file():
    raise FileNotFoundError(f"Seed database not found at {SEED_DB}")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    ["app/desktop_entry.py"],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=[
        # Bundle Alembic scripts (needed for programmatic migrations)
        (str(ALEMBIC_DIR), "alembic"),
        # Bundle frontend production build as static files
        (str(FRONTEND_DIST), "static"),
        # Bundle seed database
        (str(SEED_DB), "seed"),
    ],
    hiddenimports=[
        # uvicorn internals that PyInstaller misses
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # FastAPI / Starlette internals
        "multipart",
        "multipart.multipart",
        # Alembic
        "alembic",
        "alembic.config",
        "alembic.command",
        "alembic.runtime.migration",
        "alembic.script",
        # SQLModel / SQLAlchemy
        "sqlmodel",
        "sqlalchemy.dialects.sqlite",
        # Application modules
        "app",
        "app.main",
        "app.config",
        "app.database",
        "app.models",
        "app.models.pokemon_species",
        "app.models.set",
        "app.models.card",
        "app.models.collection",
        "app.routers",
        "app.routers.cards",
        "app.routers.collection",
        "app.routers.progress",
        "app.routers.recommendations",
        "app.routers.sets",
        "app.routers.species",
        "app.services",
        "app.services.card_service",
        "app.services.collection_service",
        "app.services.pokemon_species_service",
        "app.services.progress_service",
        "app.services.recommendation_service",
        "app.services.set_service",
        "app.services.set_summary_service",
        "app.services.species_summary_service",
        "app.schemas",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Development-only packages not needed in production
        "pytest",
        "httpx",
        "pip",
        "setuptools",
    ],
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pulldex-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for debugging; Electron hides it anyway
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="pulldex-backend",
)
