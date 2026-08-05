import httpx

from app.config import settings


def test_pokemon_tcg_api_connection():
    assert settings.pokemon_tcg_api_key is not None, "API key was not loaded"

    response = httpx.get(
        "https://api.pokemontcg.io/v2/cards",
        headers={
            "X-Api-Key": settings.pokemon_tcg_api_key,
        },
        params={
            "pageSize": 1,
        },
        timeout=10,
    )

    assert response.status_code == 200

    data = response.json()

    assert "data" in data
    assert len(data["data"]) > 0