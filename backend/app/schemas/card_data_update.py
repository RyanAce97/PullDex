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
