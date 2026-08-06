from sqlmodel import Session, select, func
from app.database import engine
from app.models.card import Card
from app.models.set import Set
from app.models.pokemon_species import PokemonSpecies

with Session(engine) as session:
    card_count = session.exec(select(func.count()).select_from(Card)).one()
    set_count = session.exec(select(func.count()).select_from(Set)).one()
    species_count = session.exec(select(func.count()).select_from(PokemonSpecies)).one()

    print(f"Cards: {card_count}")
    print(f"Sets: {set_count}")
    print(f"Species: {species_count}")