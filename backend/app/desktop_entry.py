"""Desktop entry point for PullDex backend.

This module is the PyInstaller entry point.  It starts the FastAPI
application via uvicorn, listening on 127.0.0.1 at the port specified
by the PULLDEX_PORT environment variable.

All configuration (database path, seed path, port) is provided via
environment variables set by the Electron main process.

Usage (development testing)::

    PULLDEX_DESKTOP=true \
    PULLDEX_PORT=18321 \
    DATABASE_URL=sqlite:///path/to/pulldex.db \
    PULLDEX_SEED_DB=path/to/seed.db \
    python -m app.desktop_entry

In production, PyInstaller bundles this as ``pulldex-backend.exe``.
"""

import os
import sys


def main() -> None:
    """Start the PullDex FastAPI backend for desktop mode."""
    import uvicorn

    port = int(os.environ.get("PULLDEX_PORT", "18321"))
    host = "127.0.0.1"

    print(f"PullDex backend starting on {host}:{port}")
    print(f"  Desktop mode: {os.environ.get('PULLDEX_DESKTOP', 'false')}")
    print(f"  Database URL: {os.environ.get('DATABASE_URL', '(default)')}")
    print(f"  Seed DB: {os.environ.get('PULLDEX_SEED_DB', '(none)')}")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        # Disable reload in production/packaged mode.
        reload=False,
    )


if __name__ == "__main__":
    main()
