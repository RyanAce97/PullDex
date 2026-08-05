"""HTTP client for the Pokémon TCG API (https://api.pokemontcg.io/v2).

Responsible only for API communication — no database logic lives here.
"""

import httpx

BASE_URL = "https://api.pokemontcg.io/v2/"


class PokemonTCGClient:
    """Thin wrapper around the Pokémon TCG API.

    Requests are intentionally unauthenticated: authenticated requests
    (X-Api-Key header) currently return server errors from the API.
    The POKEMON_TCG_API_KEY setting is retained in configuration for
    future use once the issue is resolved.

    Usage (synchronous, one-off):
        client = PokemonTCGClient()
        data = client.get_cards(page_size=10)

    Usage (as a context manager to reuse the connection pool):
        with PokemonTCGClient() as client:
            data = client.get_cards(page_size=10)
    """

    def __init__(self, timeout: float = 10.0) -> None:
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
    # Endpoints
    # ------------------------------------------------------------------

    def get_cards(self, page_size: int = 10) -> dict:
        """Fetch a page of cards from /cards.

        Args:
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
            httpx.HTTPStatusError: if the API returns a 4xx or 5xx response.
            httpx.TimeoutException:  if the request exceeds the timeout.
        """
        response = self._client.get(
            "cards",
            params={"pageSize": page_size},
        )
        response.raise_for_status()
        return response.json()
