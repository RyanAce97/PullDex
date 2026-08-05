from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_db_and_tables
import app.models  # noqa: F401 — registers all table metadata with SQLModel


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the first request, cleanup on shutdown."""
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
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["General"], summary="Root")
def root():
    """Welcome endpoint — confirms the API is reachable."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health", tags=["General"], summary="Health check")
def health():
    """Health check endpoint for uptime monitors and orchestrators."""
    return {"status": "ok"}
