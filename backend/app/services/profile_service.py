"""Service layer for Profile management.

Provides CRUD operations for local profiles and an active profile helper
used by other services to scope queries to the current user's collection.
"""

from sqlmodel import Session, select

from app.models.collection import Collection
from app.models.profile import Profile


# ---------------------------------------------------------------------------
# Active profile
# ---------------------------------------------------------------------------

def get_active_profile(session: Session) -> Profile:
    """Return the currently active profile.

    If no profile is marked active (shouldn't happen in normal operation),
    activates and returns the first profile found.

    Raises:
        RuntimeError: If no profiles exist at all (database corruption).
    """
    profile = session.exec(
        select(Profile).where(Profile.is_active == True)  # noqa: E712
    ).first()
    if profile:
        return profile

    # Fallback: activate the first profile found
    first = session.exec(select(Profile)).first()
    if first is None:
        raise RuntimeError("No profiles exist in the database.")
    first.is_active = True
    session.add(first)
    session.commit()
    session.refresh(first)
    return first


def get_active_profile_id(session: Session) -> int:
    """Return the active profile's ID. Convenience wrapper."""
    profile = get_active_profile(session)
    assert profile.id is not None
    return profile.id


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_profiles(session: Session) -> list[Profile]:
    """Return all profiles ordered by creation date."""
    return list(session.exec(
        select(Profile).order_by(Profile.created_at)
    ).all())


def get_profile_by_id(session: Session, profile_id: int) -> Profile | None:
    """Return a profile by ID, or None."""
    return session.get(Profile, profile_id)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_profile(session: Session, name: str) -> Profile:
    """Create a new profile.

    The new profile is NOT automatically activated.

    Args:
        name: Display name for the profile.

    Returns:
        The newly created Profile.

    Raises:
        ValueError: If the name is empty or already taken.
    """
    name = name.strip()
    if not name:
        raise ValueError("Profile name cannot be empty.")

    existing = session.exec(
        select(Profile).where(Profile.name == name)
    ).first()
    if existing:
        raise ValueError(f"A profile named '{name}' already exists.")

    profile = Profile(name=name, is_active=False)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def rename_profile(session: Session, profile_id: int, new_name: str) -> Profile:
    """Rename an existing profile.

    Args:
        profile_id: The profile's primary key.
        new_name: The new display name.

    Returns:
        The updated Profile.

    Raises:
        ValueError: If profile not found, name empty, or name already taken.
    """
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Profile name cannot be empty.")

    profile = session.get(Profile, profile_id)
    if profile is None:
        raise ValueError(f"Profile {profile_id} not found.")

    # Check uniqueness (but allow renaming to the same name)
    if profile.name != new_name:
        existing = session.exec(
            select(Profile).where(Profile.name == new_name)
        ).first()
        if existing:
            raise ValueError(f"A profile named '{new_name}' already exists.")

    profile.name = new_name
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile_settings(
    session: Session,
    profile_id: int,
    *,
    binder_rows: int | None = None,
    binder_columns: int | None = None,
    binder_sort: str | None = None,
) -> Profile:
    """Update a profile's binder/display settings.

    Only provided fields are updated.

    Raises:
        ValueError: If profile not found or values out of range.
    """
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise ValueError(f"Profile {profile_id} not found.")

    if binder_rows is not None:
        if not (2 <= binder_rows <= 5):
            raise ValueError("binder_rows must be between 2 and 5.")
        profile.binder_rows = binder_rows

    if binder_columns is not None:
        if not (2 <= binder_columns <= 5):
            raise ValueError("binder_columns must be between 2 and 5.")
        profile.binder_columns = binder_columns

    if binder_sort is not None:
        valid_sorts = {"dex_number", "set", "card_number", "recent"}
        if binder_sort not in valid_sorts:
            raise ValueError(f"binder_sort must be one of {valid_sorts}.")
        profile.binder_sort = binder_sort

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Switch active
# ---------------------------------------------------------------------------

def switch_active_profile(session: Session, profile_id: int) -> Profile:
    """Make the given profile the active one.

    Deactivates all other profiles first.

    Raises:
        ValueError: If the profile doesn't exist.
    """
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise ValueError(f"Profile {profile_id} not found.")

    # Deactivate all profiles
    all_profiles = session.exec(select(Profile)).all()
    for p in all_profiles:
        p.is_active = (p.id == profile_id)
        session.add(p)

    session.commit()
    session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_profile(session: Session, profile_id: int) -> bool:
    """Delete a profile and all its collection entries.

    Cannot delete the last remaining profile.

    Args:
        profile_id: The profile's primary key.

    Returns:
        True if deleted.

    Raises:
        ValueError: If profile not found or is the last profile.
    """
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise ValueError(f"Profile {profile_id} not found.")

    # Check it's not the last profile
    count = len(session.exec(select(Profile)).all())
    if count <= 1:
        raise ValueError("Cannot delete the last remaining profile.")

    # Delete all collection entries for this profile
    entries = session.exec(
        select(Collection).where(Collection.profile_id == profile_id)
    ).all()
    for entry in entries:
        session.delete(entry)

    # If this was the active profile, activate another one
    was_active = profile.is_active
    session.delete(profile)
    session.commit()

    if was_active:
        # Activate the first remaining profile
        remaining = session.exec(select(Profile)).first()
        if remaining:
            remaining.is_active = True
            session.add(remaining)
            session.commit()

    return True
