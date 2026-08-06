"""Response schema for the set summary endpoint."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class SetSummaryRead(BaseModel):
    """Set-level summary with species ownership statistics.

    Used by the Set Explorer page to show how each set relates to
    the user's Living Dex progress.
    """

    model_config = ConfigDict(from_attributes=True)

    set_id: int
    api_set_id: str | None
    name: str
    series: str
    release_date: date | None
    total_species_in_set: int
    owned_species_in_set: int
    missing_species_in_set: int
