from sqlmodel import Session, select, func

from app.database import engine
from app.models.pokemon_species import PokemonSpecies


with Session(engine) as session:
    count = session.exec(
        select(func.count()).select_from(PokemonSpecies)
    ).one()

    print(f"Pokemon species count: {count}")