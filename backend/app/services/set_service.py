"""Service layer for Set queries.

Provides read functions used by API routes and other consumers.
All functions accept an open SQLModel Session and return model instances
or lists — no HTTP concerns live here.
"""

from sqlmodel import Session, select

from app.models.set import Set


def get_set_by_id(session: Session, set_id: int) -> Set | None:
    """Return a single Set by its local primary key, or None if not found.

    Args:
        session: An open SQLModel Session.
        set_id:  The local integer primary key of the set.

    Returns:
        The matching :class:`Set`, or ``None``.
    """
    return session.get(Set, set_id)


def get_set_by_api_id(session: Session, api_set_id: str) -> Set | None:
    """Return a single Set by its external API identifier, or None if not found.

    Args:
        session:    An open SQLModel Session.
        api_set_id: External set identifier, e.g. ``"sv1"``.

    Returns:
        The matching :class:`Set`, or ``None``.
    """
    return session.exec(
        select(Set).where(Set.api_set_id == api_set_id)
    ).first()


def get_all_sets(
    session: Session,
    limit: int = 250,
    offset: int = 0,
) -> list[Set]:
    """Return all sets, paginated.

    Args:
        session: An open SQLModel Session.
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of :class:`Set` instances, possibly empty.
    """
    statement = select(Set).offset(offset).limit(limit)
    return list(session.exec(statement).all())


def search_sets_by_name(
    session: Session,
    name: str,
    limit: int = 50,
    offset: int = 0,
) -> list[Set]:
    """Return sets whose name contains the search term (case-insensitive substring).

    Args:
        session: An open SQLModel Session.
        name:    Substring to search for (case-insensitive).
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of matching :class:`Set` instances, possibly empty.
    """
    term = f"%{name}%"
    statement = (
        select(Set)
        .where(Set.name.ilike(term))  # type: ignore[union-attr]
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())
