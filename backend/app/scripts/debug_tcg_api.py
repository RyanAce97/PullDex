from app.services.api.pokemon_tcg_client import PokemonTCGClient


def main():
    with PokemonTCGClient() as client:
        print("Headers:")
        print(client._client.headers)

        response = client._client.get(
            "cards",
            params={"pageSize": 1},
        )

        print()
        print("Status:", response.status_code)
        print(response.text[:500])


if __name__ == "__main__":
    main()