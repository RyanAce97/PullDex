"""HTTP client for the PokéAPI (https://pokeapi.co).

Responsible only for API communication — no database logic lives here.
"""

import httpx

BASE_URL = "https://pokeapi.co/api/v2/"


class PokeApiClient:
    """Thin wrapper around the PokéAPI REST API.

    Usage (synchronous, one-off):
        client = PokeApiClient()
        data = client.get_pokemon_species_page(limit=100, offset=0)

    Usage (as a context manager to reuse the connection pool):
        with PokeApiClient() as client:
            data = client.get_pokemon_species_page(limit=100, offset=0)
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

    def __enter__(self) -> "PokeApiClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def get_pokemon_species_page(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Fetch a page of Pokémon species from /pokemon-species.

        Args:
            limit:  Number of results to return (max 100 per PokéAPI docs).
            offset: Zero-based index to start from.

        Returns:
            Parsed JSON response dict, e.g.:
            {
                "count": 1025,
                "next": "https://...",
                "previous": null,
                "results": [{"name": "bulbasaur", "url": "..."}, ...]
            }

        Raises:
            httpx.HTTPStatusError: if the API returns a 4xx or 5xx response.
            httpx.TimeoutException:  if the request exceeds the timeout.
        """
        response = self._client.get(
            "pokemon-species",
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return response.json()

    def get_pokemon_species(self, name: str) -> dict:
        """Fetch detail for a single Pokémon species from /pokemon-species/{name}.

        Args:
            name: The species name or national dex number, e.g. 'bulbasaur' or '1'.

        Returns:
            Parsed JSON response dict, e.g.:
            {
                "id": 1,
                "name": "bulbasaur",
                "generation": {"name": "generation-i", "url": "..."},
                ...
            }

        Raises:
            httpx.HTTPStatusError: if the API returns a 4xx or 5xx response.
            httpx.TimeoutException:  if the request exceeds the timeout.
        """
        response = self._client.get(f"pokemon-species/{name}")
        response.raise_for_status()
        return response.json()
