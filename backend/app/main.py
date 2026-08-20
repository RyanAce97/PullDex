import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import create_db_and_tables, run_migrations
import app.models  # noqa: F401 — registers all table metadata with SQLModel
from app.routers import cards as cards_router
from app.routers import collection as collection_router
from app.routers import progress as progress_router
from app.routers import recommendations as recommendations_router
from app.routers import sets as sets_router
from app.routers import species as species_router
from app.routers import profiles as profiles_router
from app.routers import binder as binder_router
from app.routers import data as data_router


# ---------------------------------------------------------------------------
# Static files directory (desktop mode only)
# ---------------------------------------------------------------------------

def _get_static_dir() -> Path | None:
    """Resolve the path to bundled frontend static files.

    In desktop/packaged mode (PyInstaller), static files are bundled at
    ``{_MEIPASS}/static/``.  In development, this returns None so the
    app behaves as a pure API server.
    """
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        static = bundle_dir / "static"
        if static.is_dir():
            return static
    return None


_STATIC_DIR = _get_static_dir()


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the first request, cleanup on shutdown."""
    # In desktop mode, run Alembic migrations before anything else.
    if settings.pulldex_desktop:
        run_migrations()

    # Ensure the database file and tables exist.
    create_db_and_tables()
    yield
    # Nothing to clean up for SQLite, but the hook is here for future use.


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Pokémon TCG Living Pokédex tracker — pull, track, and discover.",
    docs_url="/docs" if not settings.pulldex_desktop else None,
    redoc_url="/redoc" if not settings.pulldex_desktop else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards_router.router)
app.include_router(collection_router.router)
app.include_router(progress_router.router)
app.include_router(recommendations_router.router)
app.include_router(sets_router.router)
app.include_router(species_router.router)
app.include_router(profiles_router.router)
app.include_router(binder_router.router)
app.include_router(data_router.router)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["General"], summary="Health check")
def health():
    """Health check endpoint for uptime monitors and orchestrators."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static file serving (desktop mode only)
# ---------------------------------------------------------------------------

if _STATIC_DIR:
    # Serve bundled frontend assets (JS, CSS, images).
    # These have content-hashed filenames from Vite (e.g., index-DlEttoej.js)
    # so they can be cached indefinitely — a new build generates new filenames.
    app.mount(
        "/assets",
        StaticFiles(directory=_STATIC_DIR / "assets"),
        name="static-assets",
    )

    @app.get("/", include_in_schema=False)
    async def serve_index():
        """Serve the React SPA index.html at the root.

        Served with Cache-Control: no-cache so that after a PullDex update,
        Electron's Chromium always fetches the latest index.html which
        references the new hashed asset filenames.
        """
        return FileResponse(
            _STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str):
        """Catch-all: serve index.html for client-side routing.

        Only triggered for paths that did not match an API route above.
        """
        # If the path corresponds to a real file in static dir, serve it.
        file_path = _STATIC_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        # Otherwise, return index.html for SPA routing (also no-cache).
        return FileResponse(
            _STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
else:
    # Development mode — simple root/welcome endpoint.
    @app.get("/", tags=["General"], summary="Root")
    def root():
        """Welcome endpoint — confirms the API is reachable."""
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }
