"""Local card-data version accessor.

Reads and writes the local card-data catalogue version stored in the
``app_metadata`` table. This is deliberately separate from the application
version (``settings.app_version``): the card catalogue is versioned
independently of the app.

Stage 1 only *reads* this value (to compare against the remote manifest).
The writer is provided for later stages and for the migration baseline, but
Stage 1 never changes card data.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.app_metadata import AppMetadata

CARD_DATA_VERSION_KEY = "card_data_version"

# Baseline shipped with this application build. Used only as a fallback when
# the app_metadata row is somehow absent (e.g. a very old database that has
# not yet run the migration). Kept in sync with the Alembic baseline.
DEFAULT_CARD_DATA_VERSION = 1


def get_local_card_data_version(session: Session) -> int:
    """Return the local card-data version.

    Falls back to :data:`DEFAULT_CARD_DATA_VERSION` if the metadata row is
    missing or non-numeric, so a read never fails the caller.
    """
    row = session.exec(
        select(AppMetadata).where(AppMetadata.key == CARD_DATA_VERSION_KEY)
    ).first()
    if row is None or row.value is None:
        return DEFAULT_CARD_DATA_VERSION
    try:
        return int(row.value)
    except (TypeError, ValueError):
        return DEFAULT_CARD_DATA_VERSION


def set_local_card_data_version(session: Session, version: int) -> None:
    """Persist the local card-data version.

    Provided for later stages. Stage 1 does not call this during an update
    check. This only writes to the isolated ``app_metadata`` table and never
    touches card/collection/profile/binder data.
    """
    stage_local_card_data_version(session, version)
    session.commit()


def stage_local_card_data_version(session: Session, version: int) -> None:
    """Stage the local card-data version write WITHOUT committing.

    Adds/updates the ``card_data_version`` row on the session but leaves the
    transaction open so the caller can commit it atomically alongside other
    changes (e.g. a card-data merge). Only touches the isolated
    ``app_metadata`` table.
    """
    row = session.exec(
        select(AppMetadata).where(AppMetadata.key == CARD_DATA_VERSION_KEY)
    ).first()
    if row is None:
        row = AppMetadata(key=CARD_DATA_VERSION_KEY, value=str(int(version)))
        session.add(row)
    else:
        row.value = str(int(version))
        session.add(row)
