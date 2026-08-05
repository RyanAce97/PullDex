"""Alembic environment — integrates with pydantic-settings and SQLModel."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# ---------------------------------------------------------------------------
# Import settings so the database URL is always in sync with the app config.
# ---------------------------------------------------------------------------
from app.config import settings

# ---------------------------------------------------------------------------
# Import all models here so their metadata is registered with SQLModel.
# Add new model imports beneath this comment as they are created.
# ---------------------------------------------------------------------------
# from app.models import ...  # noqa: F401  (uncomment as models are added)

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Override the URL from alembic.ini with the value from pydantic-settings.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use SQLModel's metadata so Alembic can autogenerate migrations.
target_metadata = SQLModel.metadata


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
