"""PullDex database models.

Importing this package registers all SQLModel table classes with
SQLModel.metadata, which is required for:

  - SQLModel.metadata.create_all(engine)   (startup bootstrap)
  - alembic revision --autogenerate        (migration generation)

Add new models to the imports below as they are created.
"""

from app.models.pokemon_species import PokemonSpecies  # noqa: F401
from app.models.set import Set  # noqa: F401
from app.models.card import Card  # noqa: F401
from app.models.collection import Collection  # noqa: F401

__all__ = [
    "PokemonSpecies",
    "Set",
    "Card",
    "Collection",
]
