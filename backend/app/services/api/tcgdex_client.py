"""HTTP client for the TCGdex API (https://api.tcgdex.net/v2).

Used as a supplementary data source to fill gaps in the Pokémon TCG API.
TCGdex provides better promo card coverage (MEP, Promos-A, missing SVP cards)
and accurate species dex IDs for validation.

Does NOT replace the Pokémon TCG API — used only for gap-filling and validation.
"""

import time

import httpx

BASE_URL = "https://api.tcgdex.net/v2/en/"

# HTTP status codes that indicate a transient server problem worth retrying.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({500, 502, 503, 504})

# Network/transport exceptions that are safe to retry.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.TimeoutException,
    httpx.NetworkError,
)

# Maximum number of attempts (1 original + 2 retries = 3 total).
_MAX_ATTEMPTS: int = 3

# Base delay in seconds for exponential backoff.
_BACKOFF_BASE: float = 1.0


class TCGdexClient:
    """Thin wrapper around the TCGdex REST API (English).

    TCGdex does not require authentication and has no known rate limits.
    Transient server errors are retried with exponential backoff.

    Usage (as a context manager):
        with TCGdexClient() as client:
            sets = client.get_sets()
            card = client.get_card("me02.5-084")
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "TCGdexClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_with_retry(self, path: str) -> httpx.Response:
        """Perform a GET request, retrying on transient server errors.

        Attempts the request up to ``_MAX_ATTEMPTS`` times. After each
        retryable failure, sleeps with exponential backoff.

        Args:
            path: Relative URL path, e.g. ``"sets/mep"``.

        Returns:
            The successful :class:`httpx.Response`.

        Raises:
            httpx.HTTPStatusError: after all retry attempts are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.get(path)

                if response.status_code == 404:
                    # Not found is not retryable — raise immediately.
                    response.raise_for_status()
                    return response

                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response

                last_exception = httpx.HTTPStatusError(
                    message=f"Server error: {response.status_code}",
                    request=response.request,
                    response=response,
                )

            except _RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc

            if attempt < _MAX_ATTEMPTS - 1:
                delay = _BACKOFF_BASE * (2**attempt)
                time.sleep(delay)

        assert last_exception is not None
        raise last_exception

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def get_sets(self) -> list[dict]:
        """Fetch all sets from /sets.

        Returns:
            List of set summary dicts, e.g.:
            [{"id": "me02.5", "name": "Ascended Heroes"}, ...]
        """
        response = self._get_with_retry("sets")
        return response.json()

    def get_set(self, set_id: str) -> dict:
        """Fetch a single set with its card list from /sets/{id}.

        Args:
            set_id: TCGdex set ID, e.g. "mep", "me02.5".

        Returns:
            Full set dict including ``cards`` list.
        """
        response = self._get_with_retry(f"sets/{set_id}")
        return response.json()

    def get_card(self, card_id: str) -> dict:
        """Fetch a single card from /cards/{id}.

        Args:
            card_id: TCGdex card ID, e.g. "me02.5-084".

        Returns:
            Full card dict with dexId, stage, evolveFrom, etc.
        """
        response = self._get_with_retry(f"cards/{card_id}")
        return response.json()

    def get_set_cards(self, set_id: str) -> list[dict]:
        """Convenience: fetch a set and return just its cards list.

        Args:
            set_id: TCGdex set ID.

        Returns:
            List of card summary dicts from the set.
        """
        set_data = self.get_set(set_id)
        return set_data.get("cards", [])
