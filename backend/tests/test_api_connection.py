"""Live connectivity smoke test for the Pokémon TCG API.

Purpose: confirm the API key is loaded and the endpoint is reachable.
This test does NOT validate the external API's correctness.

Transient server errors (500/502/503/504) are accepted with a warning
because the Pokémon TCG API occasionally returns 5xx on authenticated
requests regardless of client behaviour.
"""

import warnings

import httpx
import pytest

from app.config import settings

_SERVER_ERROR_CODES = {500, 502, 503, 504}


def test_pokemon_tcg_api_connection():
    assert settings.pokemon_tcg_api_key is not None, "POKEMON_TCG_API_KEY was not loaded from .env"

    response = httpx.get(
        "https://api.pokemontcg.io/v2/cards",
        headers={"X-Api-Key": settings.pokemon_tcg_api_key},
        params={"pageSize": 1},
        timeout=10,
    )

    if response.status_code in _SERVER_ERROR_CODES:
        warnings.warn(
            f"Pokémon TCG API returned {response.status_code} — "
            "transient server error, skipping response assertions.",
            stacklevel=1,
        )
        return

    assert response.status_code == 200, (
        f"Unexpected status code {response.status_code}: {response.text}"
    )

    data = response.json()
    assert "data" in data
    assert len(data["data"]) > 0
