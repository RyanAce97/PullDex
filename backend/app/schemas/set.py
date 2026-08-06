"""Response schemas for set-related API endpoints.

These are plain Pydantic models used as ``response_model`` on routes.
They decouple the public API contract from the SQLModel table models,
preventing internal fields (relationship objects, SQLAlchemy state, etc.)
from leaking into responses.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class SetRead(BaseModel):
    """Public representation of a Set returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    api_set_id: str | None
    name: str
    series: str
    release_date: date | None
