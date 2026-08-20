"""Shared test fixtures for PullDex backend tests.

Provides a default active profile fixture that is automatically used by
any test that has a 'session' fixture — ensuring collection, progress,
and recommendation tests have a valid profile to scope queries to.
"""

import pytest

from app.models.profile import Profile


@pytest.fixture(autouse=True)
def ensure_default_profile(request):
    """Ensure a default active profile exists in any test that uses a session.

    This fixture fires for every test. If the test has a 'session' fixture,
    it creates a default profile. Otherwise it's a no-op.
    """
    # Check if the test has a 'session' fixture
    if "session" not in request.fixturenames:
        return

    session = request.getfixturevalue("session")

    # Check if a profile already exists
    from sqlmodel import select
    existing = session.exec(select(Profile)).first()
    if existing:
        return

    # Create default active profile
    profile = Profile(name="Default", is_active=True, binder_rows=5, binder_columns=4, binder_sort="dex_number")
    session.add(profile)
    session.commit()


@pytest.fixture(name="default_profile")
def default_profile_fixture(session) -> Profile:
    """Return the default active profile (created by ensure_default_profile).

    Use this fixture explicitly when you need the profile_id for
    creating Collection entries directly.
    """
    from sqlmodel import select
    profile = session.exec(select(Profile).where(Profile.is_active == True)).first()  # noqa: E712
    assert profile is not None
    return profile
