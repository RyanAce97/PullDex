"""Card-data updater routes.

Stage 1 exposes a read-only ``/card-data/update-check`` diagnostic. Stage 2B
adds ``POST /card-data/update`` which performs the real reference-data update
(download + validate + backup + atomic merge). The update never touches user
data (collection, ownership, quantities, binder, profiles) and never replaces
the database file.
"""

import threading

from fastapi import APIRouter, Depends

from app.database import get_session
from app.schemas.card_data_update import (
    CardDataUpdateResultRead,
    CardDataUpdateStatusRead,
)
from app.services.card_data_update_service import CardDataUpdateService
from app.services.card_data_updater_service import (
    CardDataUpdater,
    UpdateResult,
    UpdateResultStatus,
)
from app.services.card_data_version_service import get_local_card_data_version

router = APIRouter(prefix="/card-data", tags=["Card Data"])

# In-process guard so two overlapping update requests can never run the merge
# concurrently (defence-in-depth alongside the UI's duplicate-click guard).
_update_lock = threading.Lock()


@router.get(
    "/update-check",
    response_model=CardDataUpdateStatusRead,
    summary="Check whether newer card data is available (read-only)",
)
def update_check(session=Depends(get_session)):
    """Compare the remote card-data manifest against the local version.

    Read-only: reads the local card-data version and fetches the remote
    manifest. Never downloads set files or modifies card/collection data.
    Safe if the network or remote host is unavailable — the failure is
    reported as ``REMOTE_UNAVAILABLE`` rather than raising.
    """
    local_version = get_local_card_data_version(session)
    service = CardDataUpdateService(local_data_version=local_version)
    result = service.check()
    return result.to_dict()


@router.post(
    "/update",
    response_model=CardDataUpdateResultRead,
    summary="Download, validate, and merge newer card reference data",
)
def update_card_data(session=Depends(get_session)):
    """Perform the real card-data update (Stage 2B).

    Downloads the set files referenced by the remote manifest, validates them
    (SHA-256 + structure), backs up the database, and atomically merges the
    reference data. User data (collection, quantities, binder, profiles) is
    never modified and the database file is never replaced. All expected
    failures are returned as a safe status/message — no stack traces are
    exposed.
    """
    # Duplicate-run protection: if an update is already running, report a safe
    # "in progress" style failure rather than starting a second merge.
    if not _update_lock.acquire(blocking=False):
        local_version = get_local_card_data_version(session)
        busy = UpdateResult(
            status=UpdateResultStatus.DATABASE_UPDATE_FAILED,
            local_data_version=local_version,
            error="An update is already in progress.",
        )
        return busy.to_dict()

    try:
        updater = CardDataUpdater(session=session)
        result = updater.update_card_data()
        return result.to_dict()
    finally:
        _update_lock.release()
