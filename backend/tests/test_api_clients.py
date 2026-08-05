"""Tests for external API clients.

PokeApiClient — live integration tests (require internet).
PokemonTCGClient — unit tests with mocked httpx transport (deterministic).

Run all:
    pytest tests/test_api_clients.py -v

Run only unit tests (no network):
    pytest tests/test_api_clients.py -v -k "not PokeApi"
"""

import json

import httpx
import pytest

from app.services.api.pokeapi_client import PokeApiClient
from app.services.api.pokemon_tcg_client import PokemonTCGClient


# ---------------------------------------------------------------------------
# PokeApiClient — live integration tests
# ---------------------------------------------------------------------------

class TestPokeApiClient:
    def test_get_pokemon_species_page_returns_results(self):
        with PokeApiClient() as client:
            data = client.get_pokemon_species_page(limit=1)

        assert "results" in data

    def test_get_pokemon_species_page_returns_at_least_one_result(self):
        with PokeApiClient() as client:
            data = client.get_pokemon_species_page(limit=1)

        assert len(data["results"]) >= 1

    def test_get_pokemon_species_page_first_result_has_name(self):
        with PokeApiClient() as client:
            data = client.get_pokemon_species_page(limit=1)

        assert "name" in data["results"][0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_CARD = {
    "id": "sv1-1",
    "name": "Bulbasaur",
    "supertype": "Pokémon",
    "rarity": "Common",
}

_MOCK_CARDS_RESPONSE = {
    "data": [_MOCK_CARD],
    "page": 1,
    "pageSize": 1,
    "count": 1,
    "totalCount": 18256,
}


def _make_mock_transport(response_body: dict, status_code: int = 200) -> httpx.MockTransport:
    """Return a MockTransport that always responds with the given body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            headers={"Content-Type": "application/json"},
            content=json.dumps(response_body).encode(),
        )

    return httpx.MockTransport(handler)


def _client_with_mock(response_body: dict) -> PokemonTCGClient:
    """Return a PokemonTCGClient whose HTTP transport is fully mocked."""
    client = PokemonTCGClient()
    client._client = httpx.Client(
        base_url="https://api.pokemontcg.io/v2/",
        transport=_make_mock_transport(response_body),
    )
    return client


# ---------------------------------------------------------------------------
# PokemonTCGClient — unit tests (no network)
# ---------------------------------------------------------------------------

class TestPokemonTCGClient:
    def test_get_cards_sends_correct_endpoint_and_params(self):
        """get_cards() must request /cards with the correct pageSize param."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                content=json.dumps(_MOCK_CARDS_RESPONSE).encode(),
            )

        client = PokemonTCGClient()
        client._client = httpx.Client(
            base_url="https://api.pokemontcg.io/v2/",
            transport=httpx.MockTransport(handler),
        )

        with client:
            client.get_cards(page_size=5)

        assert len(captured) == 1
        req = captured[0]
        assert req.url.path.endswith("/cards")
        assert req.url.params["pageSize"] == "5"

    def test_get_cards_returns_parsed_json(self):
        """get_cards() should return a dict parsed from the JSON response."""
        with _client_with_mock(_MOCK_CARDS_RESPONSE) as client:
            data = client.get_cards(page_size=1)

        assert isinstance(data, dict)
        assert "data" in data

    def test_get_cards_mocked_card_has_name(self):
        """get_cards() result should include cards with a name field."""
        with _client_with_mock(_MOCK_CARDS_RESPONSE) as client:
            data = client.get_cards(page_size=1)

        assert len(data["data"]) >= 1
        assert "name" in data["data"][0]
        assert data["data"][0]["name"] == "Bulbasaur"
