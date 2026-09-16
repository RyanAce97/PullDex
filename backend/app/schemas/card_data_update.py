"""Response schemas for the card-data updater (Stage 1 — read-only check)."""

from pydantic import BaseModel


class RemoteSetInfoRead(BaseModel):
    """Per-set metadata from the remote manifest."""

    id: str
    name: str
    file: str
    version: int
    sha256: str
    card_count: int


class CardDataUpdateStatusRead(BaseModel):
    """Result of a read-only card-data update check."""

    status: str
    local_data_version: int
    remote_data_version: int | None = None
    remote_schema_version: int | None = None
    remote_set_count: int | None = None
    remote_card_count: int | None = None
    update_available: bool = False
    error: str | None = None
    sets: list[RemoteSetInfoRead] = []


class CardDataUpdateResultRead(BaseModel):
    """Result of an actual card-data update (Stage 2B).

    ``error`` carries a short, non-sensitive reason for diagnostics; it never
    contains a stack trace. The UI should prefer ``message`` for display.
    """

    status: str
    success: bool
    message: str
    local_data_version: int
    remote_data_version: int | None = None
    sets_created: int = 0
    sets_updated: int = 0
    cards_created: int = 0
    cards_updated: int = 0
    set_count: int | None = None
    card_count: int | None = None
    backup_path: str | None = None
    error: str | None = None
