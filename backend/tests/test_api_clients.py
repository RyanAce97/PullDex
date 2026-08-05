"""Integration tests for external API clients.

These tests make real HTTP requests — they require an active internet
connection and will count against any rate limits.

Run with:
    pytest tests/test_api_clients.py -v
"""

import pytest

from app.services.api.pokeapi_client import PokeApiClient
from app.services.api.pokemon_tcg_client import PokemonTCGClient


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


class TestPokemonTCGClient:
    def test_get_cards_returns_data(self):
        with PokemonTCGClient() as client:
            data = client.get_cards(page_size=1)

        assert "data" in data

    def test_get_cards_returns_at_least_one_card(self):
        with PokemonTCGClient() as client:
            data = client.get_cards(page_size=1)

        assert len(data["data"]) >= 1

    def test_get_cards_first_card_has_name(self):
        with PokemonTCGClient() as client:
            data = client.get_cards(page_size=1)

        assert "name" in data["data"][0]
