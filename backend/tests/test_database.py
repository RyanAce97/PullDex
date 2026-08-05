"""Unit tests for app.database helpers."""

import unittest.mock

from sqlmodel import Session

from app.database import get_session_context


def test_get_session_context_yields_session():
    """get_session_context() should yield a SQLModel Session."""
    with get_session_context() as session:
        assert isinstance(session, Session)


def test_get_session_context_closes_after_block():
    """The session should be closed once the context manager exits."""
    with get_session_context() as session:
        close = unittest.mock.patch.object(session, "close", wraps=session.close).start()

    # close() must have been called exactly once when the block exited.
    close.assert_called_once()
