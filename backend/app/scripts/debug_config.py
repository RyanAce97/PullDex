from app.config import settings

print("API key exists:", bool(settings.pokemon_tcg_api_key))
print("API key length:", len(settings.pokemon_tcg_api_key or ""))