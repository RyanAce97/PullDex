# Alembic Migrations

Migration scripts are stored in this directory.

## Common commands (run from the `backend/` folder)

```bash
# Generate a new migration after changing models
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history --verbose
```
