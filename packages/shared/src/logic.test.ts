import {
  buildPokedexBinderPage,
  computeProgress,
  filterCards,
  filterSpecies,
  isConceptCard,
  pokedexPageDexRange,
  pokedexTotalPages,
  rankSpeciesSearch,
  NATIONAL_DEX_COUNT,
} from "./index";
import type { CardWithContext, PokedexSlotInput, PokemonSpecies, SpeciesOwnership } from "./index";

function species(dex: number, name: string): PokemonSpecies {
  return { id: dex, national_dex_number: dex, name, generation: 1 };
}

function ownership(dex: number, name: string, owned: boolean, ownedCardCount = owned ? 1 : 0): SpeciesOwnership {
  return { species: species(dex, name), owned, ownedCardCount };
}

function cardCtx(overrides: Partial<CardWithContext> = {}): CardWithContext {
  return {
    id: 1,
    api_card_id: "sv1-1",
    card_number: "001/198",
    rarity: "Common",
    image_url: "https://img/1.png",
    variant: null,
    pokemon_species_id: 1,
    pokemon_name: "bulbasaur",
    national_dex_number: 1,
    set_id: 1,
    set_name: "Scarlet & Violet",
    set_code: "sv1",
    is_promo: false,
    ...overrides,
  };
}

describe("computeProgress", () => {
  it("computes owned/missing/percentage", () => {
    const p = computeProgress(205);
    expect(p.totalSpecies).toBe(NATIONAL_DEX_COUNT);
    expect(p.ownedSpecies).toBe(205);
    expect(p.missingSpecies).toBe(NATIONAL_DEX_COUNT - 205);
    expect(p.percentage).toBe(20); // 205/1025 = 20.0%
  });

  it("clamps and handles zero total", () => {
    expect(computeProgress(9999).ownedSpecies).toBe(NATIONAL_DEX_COUNT);
    expect(computeProgress(5, 0).percentage).toBe(0);
  });
});

describe("filterSpecies", () => {
  const rows = [
    ownership(1, "bulbasaur", true),
    ownership(4, "charmander", false),
    ownership(25, "pikachu", true),
  ];

  it("filters by name substring (case-insensitive)", () => {
    expect(filterSpecies(rows, "char").map((r) => r.species.name)).toEqual(["charmander"]);
    expect(filterSpecies(rows, "PIKA").map((r) => r.species.name)).toEqual(["pikachu"]);
  });

  it("filters by dex number", () => {
    expect(filterSpecies(rows, "25").map((r) => r.species.name)).toEqual(["pikachu"]);
  });

  it("applies ownership filter", () => {
    expect(filterSpecies(rows, "", "owned").map((r) => r.species.name)).toEqual(["bulbasaur", "pikachu"]);
    expect(filterSpecies(rows, "", "missing").map((r) => r.species.name)).toEqual(["charmander"]);
  });

  it("empty query with 'all' returns everything", () => {
    expect(filterSpecies(rows, "  ", "all")).toHaveLength(3);
  });
});

describe("rankSpeciesSearch", () => {
  const rows = [
    ownership(1, "bulbasaur", false),
    ownership(3, "venusaur", false),
    ownership(25, "pikachu", false),
    ownership(26, "raichu", false),
  ];

  it("returns nothing for empty query", () => {
    expect(rankSpeciesSearch(rows, "")).toEqual([]);
  });

  it("ranks exact match first, then prefix, then substring", () => {
    const res = rankSpeciesSearch(rows, "raichu");
    expect(res[0].species.name).toBe("raichu");
  });

  it("prefix beats substring (\"pi\" -> pikachu before others)", () => {
    const res = rankSpeciesSearch(rows, "pi");
    expect(res[0].species.name).toBe("pikachu");
  });

  it("matches by dex number", () => {
    const res = rankSpeciesSearch(rows, "25");
    expect(res[0].species.national_dex_number).toBe(25);
  });

  it("respects the limit", () => {
    expect(rankSpeciesSearch(rows, "a", 1)).toHaveLength(1);
  });
});

describe("filterCards", () => {
  const cards = [
    cardCtx({ id: 1, pokemon_name: "bulbasaur", set_name: "Scarlet & Violet", set_code: "sv1", card_number: "001" }),
    cardCtx({ id: 2, pokemon_name: "pikachu", set_name: "Base", set_code: "base1", card_number: "058", api_card_id: "base1-58" }),
  ];

  it("empty query returns all", () => {
    expect(filterCards(cards, "")).toHaveLength(2);
  });
  it("matches name, set, code, number, api id", () => {
    expect(filterCards(cards, "pika")).toHaveLength(1);
    expect(filterCards(cards, "base")).toHaveLength(1);
    expect(filterCards(cards, "sv1")).toHaveLength(1);
    expect(filterCards(cards, "058")).toHaveLength(1);
    expect(filterCards(cards, "base1-58")).toHaveLength(1);
  });
});

describe("isConceptCard", () => {
  it("is concept when not in owned set, owned when present", () => {
    const owned = new Set<number>([5, 9]);
    expect(isConceptCard(7, owned)).toBe(true);
    expect(isConceptCard(5, owned)).toBe(false);
  });
});

describe("pokedex pagination", () => {
  it("total pages for 5x4=20 → 52", () => {
    expect(pokedexTotalPages(20)).toBe(52);
  });
  it("total pages for 2x2=4 → 257", () => {
    expect(pokedexTotalPages(4)).toBe(257);
  });
  it("page 1 dex range for pageSize 20", () => {
    expect(pokedexPageDexRange(1, 20)).toEqual({ startDex: 1, endDex: 20 });
  });
  it("last page clamps endDex to total", () => {
    const { startDex, endDex } = pokedexPageDexRange(52, 20);
    expect(startDex).toBe(1021);
    expect(endDex).toBe(NATIONAL_DEX_COUNT);
  });
});

describe("buildPokedexBinderPage", () => {
  function slotInput(dex: number, name: string, owned: boolean, withCard: boolean): PokedexSlotInput {
    return {
      species: species(dex, name),
      owned,
      representativeCard: withCard ? cardCtx({ national_dex_number: dex, pokemon_name: name }) : null,
      totalCards: withCard ? 2 : 0,
    };
  }

  it("builds slots, pads to page size, sets states", () => {
    const inputs = new Map<number, PokedexSlotInput>();
    inputs.set(1, slotInput(1, "bulbasaur", true, true));
    // dex 2 owned, no card; dex 3 not owned (absent from map → empty/unowned)
    inputs.set(2, slotInput(2, "ivysaur", true, false));

    const pageSize = 4;
    const pageData = buildPokedexBinderPage(inputs, 1, pageSize);

    expect(pageData.binder_type).toBe("POKEDEX");
    expect(pageData.page_size).toBe(pageSize);
    expect(pageData.slots).toHaveLength(pageSize);

    const slot1 = pageData.slots[0];
    expect(slot1.dex_number).toBe(1);
    expect(slot1.owned).toBe(true);
    expect(slot1.has_card).toBe(true);
    expect(slot1.card?.pokemon_name).toBe("bulbasaur");
    expect(slot1.total_cards).toBe(2);

    const slot2 = pageData.slots[1];
    expect(slot2.owned).toBe(true);
    expect(slot2.has_card).toBe(false);
    expect(slot2.card).toBeNull();

    // dex 3 present in range but not in map → unowned empty slot (NO concept).
    const slot3 = pageData.slots[2];
    expect(slot3.dex_number).toBe(3);
    expect(slot3.owned).toBe(false);
    expect(slot3.has_card).toBe(false);
    expect(slot3.card).toBeNull();
  });

  it("total pages reflects page size", () => {
    const pageData = buildPokedexBinderPage(new Map(), 1, 20);
    expect(pageData.total_pages).toBe(52);
    expect(pageData.total_species).toBe(NATIONAL_DEX_COUNT);
  });
});
