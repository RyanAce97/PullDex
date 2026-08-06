"""HTTP client for the Pokémon TCG API (https://api.pokemontcg.io/v2).

Responsible only for API communication — no database logic lives here.
"""

import time

import httpx

BASE_URL = "https://api.pokemontcg.io/v2/"

# HTTP status codes that indicate a transient server problem worth retrying.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({500, 502, 503, 504})

# Network/transport exceptions that are safe to retry.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.TimeoutException,
    httpx.NetworkError,
)

# Maximum number of attempts (1 original + 4 retries = 5 total).
_MAX_ATTEMPTS: int = 5

# Base delay in seconds for exponential backoff: 1s, 2s, 4s, 8s, …
_BACKOFF_BASE: float = 1.0


class PokemonTCGClient:
    """Thin wrapper around the Pokémon TCG API.

    Requests are intentionally unauthenticated: authenticated requests
    (X-Api-Key header) currently return server errors from the API.
    The POKEMON_TCG_API_KEY setting is retained in configuration for
    future use once the issue is resolved.

    Transient server errors (500, 502, 503, 504) are automatically retried
    up to 5 attempts with exponential backoff (1s, 2s, 4s, 8s).
    Client errors (4xx) are raised immediately without retrying.

    Usage (synchronous, one-off):
        client = PokemonTCGClient()
        data = client.get_cards(page_size=10)

    Usage (as a context manager to reuse the connection pool):
        with PokemonTCGClient() as client:
            data = client.get_cards(page_size=10)
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

    def __enter__(self) -> "PokemonTCGClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_with_retry(self, path: str, params: dict) -> httpx.Response:
        """Perform a GET request, retrying on transient server errors and network failures.

        Attempts the request up to ``_MAX_ATTEMPTS`` times.  After each
        retryable failure (5xx response or network/timeout exception),
        sleeps for ``_BACKOFF_BASE * 2 ** attempt`` seconds before the
        next try.  Non-retryable responses (4xx) and successful responses
        (2xx) are returned immediately without retry.

        Args:
            path:   Relative URL path, e.g. ``"cards"``.
            params: Query-string parameters dict.

        Returns:
            The successful :class:`httpx.Response`.

        Raises:
            httpx.HTTPStatusError: after all retry attempts are exhausted
                for a 5xx error, or immediately for any non-retryable 4xx error.
            httpx.TimeoutException, httpx.NetworkError: after all retry
                attempts are exhausted for a network or timeout failure.
        """
        last_exception: Exception | None = None

        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.get(path, params=params)

                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    # Success (2xx/3xx) or non-retryable error (4xx) — return immediately.
                    response.raise_for_status()
                    return response

                # Retryable 5xx response — store it and continue to backoff logic.
                last_exception = httpx.HTTPStatusError(
                    message=f"Server error: {response.status_code}",
                    request=response.request,
                    response=response,
                )

            except _RETRYABLE_EXCEPTIONS as exc:
                # Network or timeout failure — store it and continue to backoff logic.
                last_exception = exc

            # If we reach here, the request failed with a retryable condition.
            if attempt < _MAX_ATTEMPTS - 1:
                delay = _BACKOFF_BASE * (2 ** attempt)
                time.sleep(delay)

        # All attempts exhausted — raise the last exception encountered.
        assert last_exception is not None
        raise last_exception

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def get_cards(self, page: int = 1, page_size: int = 10) -> dict:
        """Fetch a page of cards from /cards.

        Args:
            page:      1-based page number.
            page_size: Number of cards to return per page.

        Returns:
            Parsed JSON response dict, e.g.:
            {
                "data": [{"id": "sv1-1", "name": "Bulbasaur", ...}, ...],
                "page": 1,
                "pageSize": 10,
                "count": 10,
                "totalCount": 18256
            }

        Raises:
            httpx.HTTPStatusError: if the API returns a non-retryable error,
                or if all retry attempts for a transient error are exhausted.
            httpx.TimeoutException, httpx.NetworkError: if all retry attempts
                for a network or timeout failure are exhausted.
        """
        response = self._get_with_retry(
            "cards",
            params={"page": page, "pageSize": page_size},
        )
        return response.json()

    def get_sets(self, page: int = 1, page_size: int = 250) -> dict:
        """Fetch a page of sets from /sets.

        Args:
            page:      1-based page number.
            page_size: Number of sets to return per page (max 250).

        Returns:
            Parsed JSON response dict, e.g.:
            {
                "data": [
                    {
                        "id": "sv1",
                        "name": "Scarlet & Violet",
                        "series": "Scarlet & Violet",
                        "releaseDate": "2023/03/31",
                        ...
                    },
                    ...
                ],
                "page": 1,
                "pageSize": 250,
                "count": 163,
                "totalCount": 163
            }

        Raises:
            httpx.HTTPStatusError: if the API returns a non-retryable error,
                or if all retry attempts for a transient error are exhausted.
            httpx.TimeoutException, httpx.NetworkError: if all retry attempts
                for a network or timeout failure are exhausted.
        """
        response = self._get_with_retry(
            "sets",
            params={"page": page, "pageSize": page_size},
        )
        return response.json()
