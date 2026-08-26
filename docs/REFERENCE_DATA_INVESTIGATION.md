# PullDex Reference Data Investigation Report

**Date:** 2026-08-26  
**Status:** Investigation complete — no code changes made  
**Scope:** Promo card coverage, species mapping accuracy, source strategy

---

## 1. Current Local Database State

| Metric | Count |
|--------|-------|
| Total cards | 20,479 |
| Total sets | 174 |
| Total species | 1,025 |
| Cards with species mapping | 17,279 (84.4%) |
| Cards without species mapping | 3,200 (15.6%) |

**Promo sets in local DB:**

| api_set_id | Name | Series | Cards |
|------------|------|--------|-------|
| svp | Scarlet & Violet Black Star Promos | Scarlet & Violet | 200 |
| swshp | SWSH Black Star Promos | Sword & Shield | — |
| smp | SM Black Star Promos | Sun & Moon | — |
| xyp | XY Black Star Promos | XY | — |
| bwp | BW Black Star Promos | Black & White | — |
| hsp | HGSS Black Star Promos | HeartGold & SoulSilver | — |
| dpp | DP Black Star Promos | Diamond & Pearl | — |
| np | Nintendo Black Star Promos | NP | — |
| basep | Wizards Black Star Promos | Base | — |

**Missing from local DB:**
- No "First Partner Illustration Collection" set
- No "MEP Black Star Promos" set
- No "Promos-A" set

---

## 2. Promo Card Coverage — First Partner Illustration Collection

### What It Is

The "First Partner Illustration Collection" is a Pokémon 30th Anniversary (2026) promotional product series containing 27 illustration-rare-style cards depicting first partner Pokémon from all 9 generations. Released internationally as:
- Series 1 (March 2026): Gen 1 + Gen 4 + Gen 7 starters
- Series 2 (June 2026): Gen 2 + Gen 5 + Gen 8 starters
- Series 3 (August 2026): Gen 3 + Gen 6 + Gen 9 starters

### Card List (27 cards)

In TCGdex, these are cards **mep-037 through mep-063** in the "MEP Black Star Promos" set:

| TCGdex ID | Card # | Pokémon | Dex # | Series |
|-----------|--------|---------|-------|--------|
| mep-037 | 037 | Bulbasaur | 1 | 1 |
| mep-038 | 038 | Charmander | 4 | 1 |
| mep-039 | 039 | Squirtle | 7 | 1 |
| mep-040 | 040 | Turtwig | 387 | 1 |
| mep-041 | 041 | Chimchar | 390 | 1 |
| mep-042 | 042 | Piplup | 393 | 1 |
| mep-043 | 043 | Rowlet | 722 | 1 |
| mep-044 | 044 | Litten | 725 | 1 |
| mep-045 | 045 | Popplio | 728 | 1 |
| mep-046 | 046 | Chikorita | 152 | 2 |
| mep-047 | 047 | Cyndaquil | 155 | 2 |
| mep-048 | 048 | Totodile | 158 | 2 |
| mep-049 | 049 | Snivy | 495 | 2 |
| mep-050 | 050 | Tepig | 498 | 2 |
| mep-051 | 051 | Oshawott | 501 | 2 |
| mep-052 | 052 | Grookey | 810 | 2 |
| mep-053 | 053 | Scorbunny | 813 | 2 |
| mep-054 | 054 | Sobble | 816 | 2 |
| mep-055 | 055 | Treecko | 252 | 3 |
| mep-056 | 056 | Torchic | 255 | 3 |
| mep-057 | 057 | Mudkip | 258 | 3 |
| mep-058 | 058 | Chespin | 650 | 3 |
| mep-059 | 059 | Fennekin | 653 | 3 |
| mep-060 | 060 | Froakie | 656 | 3 |
| mep-061 | 061 | Sprigatito | 906 | 3 |
| mep-062 | 062 | Fuecoco | 909 | 3 |
| mep-063 | 063 | Quaxly | 912 | 3 |

### Root Cause Analysis

| Question | Answer |
|----------|--------|
| Does the Pokémon TCG API contain these cards? | **NO** — The API does not have the MEP set or any equivalent. The API returns 0 sets matching "first partner" or "illustration". |
| Is our importer filtering them out? | **NO** — The set importer imports ALL sets from the API; the card importer imports ALL cards. There is no filtering. |
| Is our set import missing the relevant promo set? | **YES** — The "MEP Black Star Promos" set does not exist in the Pokémon TCG API. It exists only in TCGdex. |
| What other cards are we missing? | The MEP set has 89 total cards. TCGdex also has a "Promos-A" set (100 cards) and 26 additional SVP cards (svp-208 through svp-225 + svp-500) that we don't have. |

### Conclusion

The Pokémon TCG API does **not** contain the First Partner Illustration Collection cards. These cards are only available from TCGdex. This is a primary API coverage gap, not a bug in our importer.

---

## 3. Incorrect Species Mapping — Azumarill ex

### The Bug

| Field | Expected | Actual |
|-------|----------|--------|
| Card | me2pt5-84 "Azumarill ex" | — |
| Species should be | Azumarill (dex 184) | — |
| Species mapped to | — | Marill (dex 183) ❌ |

### Root Cause

The **Pokémon TCG API** returns incorrect data for this card:

```json
{
  "id": "me2pt5-84",
  "name": "Azumarill ex",
  "nationalPokedexNumbers": [183],  // ← WRONG: 183 = Marill, should be 184 = Azumarill
  "evolvesFrom": "Marill",
  "subtypes": ["Stage 1", "ex"]
}
```

TCGdex correctly returns `dexId: [184]` for the same card.

Our importer blindly trusts `nationalPokedexNumbers[0]`:

```python
# card_importer.py line ~145
dex_numbers: list[int] = data.get("nationalPokedexNumbers") or []
national_dex_number: int | None = dex_numbers[0] if dex_numbers else None
species_id = _resolve_species_id(session, national_dex_number)
```

### Scope Assessment

**Is this a systemic issue?** Spot-checking other Stage 1/2 ex cards in the same set:

| Card | Name | API dex | Correct? |
|------|------|---------|----------|
| me2pt5-22 | Mega Charizard Y ex | [6] | ✅ (Charizard = 6) |
| me2pt5-43 | Mega Feraligatr ex | [160] | ✅ (Feraligatr = 160) |
| me2pt5-84 | Azumarill ex | [183] | ❌ (should be 184) |

This appears to be a **specific data error** for this card in the Pokémon TCG API, not a universal bug in how Stage 1/2 cards are handled. However, we cannot be confident there aren't other similar one-off errors across 20,000+ cards without cross-referencing every card against TCGdex.

### Current Repair Mechanism Limitations

The `_repair_card_species_mapping()` function in `database.py`:
- Only fixes cards where `pokemon_species_id IS NULL`
- Does NOT detect or fix **incorrectly** mapped cards (non-NULL but wrong)
- Cannot catch this class of bug because the card has a species assigned — it's just the wrong one

---

## 4. Source Comparison

### Pokémon TCG API (api.pokemontcg.io/v2)

| Attribute | Status |
|-----------|--------|
| Coverage (standard sets) | Excellent — all 174 English sets, ~20,500 cards |
| Coverage (promos) | Incomplete — missing MEP (89 cards), Promos-A (100 cards), some SVP cards |
| Species data accuracy | Good overall, with known isolated errors (Azumarill ex) |
| Reliability | Poor recently — intermittent 500 errors, empty responses, 403 without auth |
| Authentication | Required (was previously optional) |
| Rate limiting | Present; retry logic handles this |
| Image URLs | Available (small + large) |
| Update frequency | Unclear; new sets appear but some are delayed |

### TCGdex (api.tcgdex.net/v2)

| Attribute | Status |
|-----------|--------|
| Coverage (standard sets) | Comprehensive — same 174+ sets, uses different set IDs |
| Coverage (promos) | Superior — includes MEP (89 cards), Promos-A (100 cards), full SVP |
| Species data accuracy | Correct for Azumarill ex (dexId: [184]) |
| Reliability | Consistently available during testing |
| Authentication | Not required |
| Rate limiting | None observed |
| Image URLs | Available |
| Update frequency | Active — updated as recently as 2026-08-25 |
| Card data richness | Excellent — stage, suffix, evolveFrom, variants, pricing |

### Key Differences

| Aspect | Pokémon TCG API | TCGdex |
|--------|-----------------|--------|
| Set ID format | `me2pt5` | `me02.5` |
| Card ID format | `me2pt5-84` | `me02.5-084` |
| Dex field | `nationalPokedexNumbers` | `dexId` |
| Evolution field | `evolvesFrom` (name) | `evolveFrom` (name) |
| Stage info | In `subtypes` array | `stage` field |
| Total sets | 174 | ~176+ (has MEP, P-A, miscp) |
| Total SVP cards | 200 (up to #207) | 226 (up to #500) |

---

## 5. Missing Cards Summary

### From TCGdex that we don't have:

| Set | ID | Cards Missing | Notes |
|-----|----|---------------|-------|
| MEP Black Star Promos | mep | 89 | Includes 27 First Partner cards + Mega ex promos |
| Promos-A | P-A | 100 | Pocket game promos? |
| SVP gaps | svp | 26 | Cards #208-225 + #500 |

**Total missing cards: ~215**

### First Partner Illustration Collection (27 cards — all missing):

All 27 are in MEP set, cards #037-#063. Every first partner Pokémon from Gen 1-9.

---

## 6. Incorrectly Mapped Cards

### Confirmed:

| Card ID | Card Name | Mapped To | Should Be |
|---------|-----------|-----------|-----------|
| me2pt5-84 | Azumarill ex | Marill (183) | Azumarill (184) |

### Suspected (unconfirmable without cross-referencing all 20,479 cards against TCGdex):

The Pokémon TCG API could have other isolated `nationalPokedexNumbers` errors. The only way to detect these systematically is to cross-reference the card name against the dex number for all Pokémon cards.

---

## 7. Recommendations

### 7.1 Source Architecture

**Recommendation: Dual-source with Pokémon TCG API as primary, TCGdex as supplementary**

| Role | Source | Purpose |
|------|--------|---------|
| Primary | Pokémon TCG API | Bulk card/set data (existing infrastructure) |
| Supplementary | TCGdex | Gap-fill (MEP, SVP), species validation, missing sets |
| Validation | TCGdex | Cross-reference dex numbers to catch API data errors |

**Rationale:**
- The Pokémon TCG API covers 99% of English TCG cards and our entire import pipeline is built on it
- TCGdex fills specific gaps (promo sets the primary API is missing)
- TCGdex provides superior dex number accuracy for validation
- Both APIs are free and well-maintained

### 7.2 Importer/Mapping Changes

#### A. Species Validation (fix Azumarill-class bugs)

**Do not add a card-specific hardcoded exception.** Instead:

1. **Cross-reference dex numbers during import**: For every Pokémon card with `nationalPokedexNumbers`, validate the dex number against the card name using the existing `normalize_card_name()` logic. If the card name resolves to a different species than what `nationalPokedexNumbers[0]` indicates, flag it or prefer the name-based resolution.

2. **Post-import validation pass**: After import, run a validation query that compares the species name against the card's `normalize_card_name()` output. Any mismatch is a potential data error.

3. **Repair mapping enhancement**: Extend `_repair_card_species_mapping()` to also fix cards where `pokemon_species_id IS NOT NULL` but is demonstrably wrong based on the card name.

#### B. Supplementary Import from TCGdex

Add a secondary import pathway:

1. **Set import**: For sets that exist in TCGdex but not the primary API (mep, P-A, new SVP cards), import set metadata from TCGdex.

2. **Card import**: For cards in supplementary sets, import from TCGdex using its data format. Map `dexId` → `pokemon_species_id`, `localId` → `card_number`.

3. **ID mapping**: Since TCGdex uses different IDs (e.g., `me02.5-084` vs `me2pt5-84`), we need to decide: use the Pokémon TCG API ID format where possible, fall back to TCGdex format for cards that only exist there.

#### C. SVP Gap Fill

Import SVP cards #208-225 and #500 from TCGdex to complete the Scarlet & Violet promo coverage.

### 7.3 Implementation Priority

| Priority | Task | Impact | Risk |
|----------|------|--------|------|
| 1 | Fix Azumarill ex mapping (and detect others) | Correct species tracking | Low — only updates wrong mappings |
| 2 | Import MEP set + First Partner cards from TCGdex | 89 new cards including all 27 First Partner promos | Low — purely additive |
| 3 | Import missing SVP cards from TCGdex | 26 new cards | Low — purely additive |
| 4 | Add species validation cross-reference | Prevent future mapping errors | Low — read-only check |
| 5 | Evaluate Promos-A import | 100 new cards | Medium — need to confirm these are English TCG cards |

### 7.4 Risks to Existing Collection Data

| Change | Risk | Mitigation |
|--------|------|------------|
| Fixing Azumarill ex species_id | If user has this card in collection, species ownership doesn't change (they'd still own an Azumarill card) | No user-facing impact for collection completeness since Marill also has other cards |
| Adding new sets/cards from TCGdex | None — purely additive, no existing data modified | — |
| Changing import source for dex numbers | Could theoretically change species mappings for other cards | Run as validation first, only fix confirmed errors |
| Re-running imports | Existing cards updated in place via upsert | species_id would be overwritten — need to validate before bulk update |

---

## 8. Open Questions

1. **Are Promos-A cards English TCG cards?** The "P-A" set in TCGdex contains 100 cards (Pikachu, Mewtwo, Lapras ex, etc.) — these may be Pokémon TCG Pocket promos or another regional release. Need to confirm before importing.

2. **How many other dex number errors exist in the Pokémon TCG API?** Without a full cross-reference of all 17,279 mapped cards against TCGdex, we can't know. The validation pass (recommendation 7.2.A.2) would answer this.

3. **Should we store the source API for each card?** If we're importing from two sources, tracking provenance could help with future debugging. This would require a schema change.

4. **What about reliability?** The Pokémon TCG API returned multiple 500 errors and empty set data during this investigation. If this instability continues, we may need to consider TCGdex as the primary source rather than secondary.

---

## Appendix: API Responses

### Pokémon TCG API — me2pt5-84

```json
{
  "id": "me2pt5-84",
  "name": "Azumarill ex",
  "supertype": "Pokémon",
  "subtypes": ["Stage 1", "ex"],
  "hp": "270",
  "types": ["Psychic"],
  "evolvesFrom": "Marill",
  "nationalPokedexNumbers": [183],
  "number": "84",
  "rarity": "Double Rare",
  "set": {"id": "me2pt5", "name": "Ascended Heroes", "series": "Mega Evolution"}
}
```

### TCGdex — me02.5-084

```json
{
  "id": "me02.5-084",
  "name": "Azumarill ex",
  "category": "Pokemon",
  "dexId": [184],
  "hp": 270,
  "types": ["Psychic"],
  "evolveFrom": "Marill",
  "stage": "Stage1",
  "suffix": "ex",
  "rarity": "Double rare",
  "set": {"id": "me02.5", "name": "Ascended Heroes"}
}
```
