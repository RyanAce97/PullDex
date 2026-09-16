"""Card-data updater routes (Stage 1 — read-only diagnostic).

Exposes a single read-only endpoint that checks the public card-data
manifest against the local card-data version. It performs NO card-data
import and makes NO changes to the database (it only reads the local
card-data version). This endpoint is intended for diagnostics and for a
future "Update Card Data" UI to call.
"""

from fastapi import APIRouter, Depends

from app.database import get_session
from app.schemas.card_data_update import CardDataUpdateStatusRead
from app.services.card_data_update_service import CardDataUpdateService
from app.services.card_data_version_service import get_local_card_data_version

router = APIRouter(prefix="/card-data", tags=["Card Data"])


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
