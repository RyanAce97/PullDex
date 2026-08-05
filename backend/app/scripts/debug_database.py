from sqlmodel import select

from app.database import get_session_context
from app.models.set import Set


with get_session_context() as session:
    sets = session.exec(select(Set)).all()
    print(f"Total sets: {len(sets)}")
    print(sets[0])