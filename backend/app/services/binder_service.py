"""Service layer for the multi-binder system.

A profile owns one or more binders. Two kinds exist:

- ``POKEDEX``: slots are DERIVED from the National Pokédex (#1–#1025) and the
  profile's Collection. ``rows`` × ``columns`` only controls pagination. This
  preserves the original single-binder behaviour. Concept cards are NOT shown
  in POKEDEX binders (a not-owned species shows an empty/unowned slot).

- ``FREE_PLACEMENT``: cards are explicitly placed on a page/slot. A placement
  references a specific card printing only. Ownership ("owned" vs "concept")
  is DERIVED from the active profile's Collection at read time — it is never
  stored on the placement.

All mutating and reading operations are scoped to a single profile. A binder
belonging to another profile is treated as not found, guaranteeing isolation.

Design note — future POKEDEX concept cards:
    Because ownership is always derived at read time (never persisted), the
    "no concept cards in POKEDEX" rule lives entirely in the read path
    (``_build_pokedex_page``). Allowing them later is a small change there,
    not a schema migration.
"""

import math

from sqlalchemy import func
from sqlmodel import Session, select

from app.config import settings
from app.models.binder import (
    MAX_BINDER_DIMENSION,
    MAX_BINDER_NAME_LENGTH,
    MIN_BINDER_DIMENSION,
    VALID_BINDER_SORTS,
    Binder,
    BinderPlacement,
    BinderType,
)
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.profile import Profile
from app.models.set import Set
from app.services.profile_service import get_active_profile, get_active_profile_id

NATIONAL_DEX_COUNT = 1025


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class BinderError(Exception):
    """Base class for binder domain errors."""


class BinderNotFoundError(BinderError):
    """Raised when a binder does not exist or belongs to another profile."""


class BinderValidationError(BinderError):
    """Raised when a binder operation fails validation (bad name/layout/etc.)."""


class BinderLimitError(BinderError):
    """Raised when creating a binder would exceed the per-profile maximum."""


class BinderMinimumError(BinderError):
    """Raised when an operation would leave a profile with zero binders."""


class PlacementConflictError(BinderError):
    """Raised when a placement target slot is occupied or the card is duplicated."""


class PlacementNotFoundError(BinderError):
    """Raised when a placement does not exist within the given binder."""


class PlacementValidationError(BinderError):
    """Raised when placement inputs (card/page/slot) are invalid."""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise BinderValidationError("Binder name cannot be empty.")
    if len(name) > MAX_BINDER_NAME_LENGTH:
        raise BinderValidationError(
            f"Binder name cannot exceed {MAX_BINDER_NAME_LENGTH} characters."
        )
    return name


def _validate_dimension(value: int, label: str) -> int:
    if not (MIN_BINDER_DIMENSION <= value <= MAX_BINDER_DIMENSION):
        raise BinderValidationError(
            f"{label} must be between {MIN_BINDER_DIMENSION} and {MAX_BINDER_DIMENSION}."
        )
    return value


def _validate_sort(sort_order: str) -> str:
    if sort_order not in VALID_BINDER_SORTS:
        raise BinderValidationError(
            f"sort_order must be one of {sorted(VALID_BINDER_SORTS)}."
        )
    return sort_order


def _validate_type(binder_type: str) -> str:
    valid = {t.value for t in BinderType}
    if binder_type not in valid:
        raise BinderValidationError(f"binder_type must be one of {sorted(valid)}.")
    return binder_type


def _capacity(binder: Binder) -> int:
    return binder.rows * binder.columns


# ---------------------------------------------------------------------------
# Lookup / isolation
# ---------------------------------------------------------------------------

def get_binder_for_profile(
    session: Session, binder_id: int, profile_id: int
) -> Binder:
    """Return a binder by id ONLY if it belongs to ``profile_id``.

    Raises:
        BinderNotFoundError: if the binder doesn't exist or is another
            profile's — the two cases are deliberately indistinguishable so
            isolation cannot be probed.
    """
    binder = session.get(Binder, binder_id)
    if binder is None or binder.profile_id != profile_id:
        raise BinderNotFoundError(f"Binder {binder_id} not found.")
    return binder


def list_binders(session: Session, profile_id: int) -> list[Binder]:
    """Return all binders for a profile, oldest first (created_at, then id)."""
    return list(
        session.exec(
            select(Binder)
            .where(Binder.profile_id == profile_id)
            .order_by(Binder.created_at, Binder.id)  # type: ignore[arg-type]
        ).all()
    )


def ensure_default_binder(session: Session, profile_id: int) -> Binder:
    """Guarantee the profile has at least one (default) binder.

    Safety net for first-run databases created via ``create_all`` (tests) or
    legacy profiles that predate the binder tables. Creates a default POKEDEX
    binder copying the profile's ``binder_*`` settings when none exists.
    """
    existing = list_binders(session, profile_id)
    if existing:
        # Make sure exactly one is default.
        if not any(b.is_default for b in existing):
            existing[0].is_default = True
            session.add(existing[0])
            session.commit()
            session.refresh(existing[0])
        return next(b for b in existing if b.is_default)

    from app.models.binder import DEFAULT_POKEDEX_BINDER_NAME

    profile = session.get(Profile, profile_id)
    rows = profile.binder_rows if profile else 5
    columns = profile.binder_columns if profile else 4
    sort_order = profile.binder_sort if profile else "dex_number"
    return create_default_pokedex_binder(
        session,
        profile_id,
        name=DEFAULT_POKEDEX_BINDER_NAME,
        rows=rows,
        columns=columns,
        sort_order=sort_order,
    )


def get_default_binder(session: Session, profile_id: int) -> Binder:
    """Return the profile's default binder.

    If no binder is flagged default (shouldn't happen in normal operation),
    the oldest binder is promoted and returned. Raises BinderMinimumError if
    the profile has no binders at all.
    """
    default = session.exec(
        select(Binder)
        .where(Binder.profile_id == profile_id, Binder.is_default == True)  # noqa: E712
        .order_by(Binder.created_at, Binder.id)  # type: ignore[arg-type]
    ).first()
    if default is not None:
        return default

    # Repair: promote the oldest binder.
    oldest = session.exec(
        select(Binder)
        .where(Binder.profile_id == profile_id)
        .order_by(Binder.created_at, Binder.id)  # type: ignore[arg-type]
    ).first()
    if oldest is None:
        raise BinderMinimumError("Profile has no binders.")
    oldest.is_default = True
    session.add(oldest)
    session.commit()
    session.refresh(oldest)
    return oldest


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_default_pokedex_binder(
    session: Session,
    profile_id: int,
    *,
    name: str,
    rows: int = 5,
    columns: int = 4,
    sort_order: str = "dex_number",
    commit: bool = True,
) -> Binder:
    """Create the profile's initial default POKEDEX binder.

    Used when a new profile is created (eager creation) and as a first-run
    safety net. Does not enforce the max limit (it's the first binder).
    """
    binder = Binder(
        profile_id=profile_id,
        name=name,
        binder_type=BinderType.POKEDEX.value,
        rows=rows,
        columns=columns,
        sort_order=sort_order,
        is_default=True,
    )
    session.add(binder)
    if commit:
        session.commit()
        session.refresh(binder)
    return binder


def create_binder(
    session: Session,
    profile_id: int,
    *,
    name: str,
    binder_type: str,
    rows: int = 5,
    columns: int = 4,
    sort_order: str = "dex_number",
) -> Binder:
    """Create a new binder for a profile.

    Enforces the per-profile maximum. The first binder created for a profile
    automatically becomes the default; subsequent binders do not.

    Raises:
        BinderValidationError, BinderLimitError
    """
    name = _validate_name(name)
    binder_type = _validate_type(binder_type)
    rows = _validate_dimension(rows, "rows")
    columns = _validate_dimension(columns, "columns")
    sort_order = _validate_sort(sort_order)

    existing = list_binders(session, profile_id)
    if len(existing) >= settings.max_binders_per_profile:
        raise BinderLimitError(
            f"Cannot create more than {settings.max_binders_per_profile} binders per profile."
        )

    # A profile may have at most one POKEDEX binder. The Pokédex binder is
    # derived from the profile's Collection (National Dex + is_binder_card), so
    # a second one would merely duplicate the same representation. Additional
    # binders must be FREE_PLACEMENT.
    if binder_type == BinderType.POKEDEX.value and any(
        b.binder_type == BinderType.POKEDEX.value for b in existing
    ):
        raise BinderValidationError("A profile can only have one Pokédex binder.")

    is_default = len(existing) == 0

    binder = Binder(
        profile_id=profile_id,
        name=name,
        binder_type=binder_type,
        rows=rows,
        columns=columns,
        sort_order=sort_order,
        is_default=is_default,
    )
    session.add(binder)
    session.commit()
    session.refresh(binder)
    return binder


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def update_binder(
    session: Session,
    binder_id: int,
    profile_id: int,
    *,
    name: str | None = None,
    rows: int | None = None,
    columns: int | None = None,
    sort_order: str | None = None,
    binder_type: str | None = None,
) -> Binder:
    """Update a binder's name/layout/sort.

    ``binder_type`` is immutable: passing a value different from the current
    type raises BinderValidationError. Passing the same value is a no-op.

    For FREE_PLACEMENT binders, a change to rows/columns triggers a
    deterministic, transactional reflow of placements.

    Raises:
        BinderNotFoundError, BinderValidationError
    """
    binder = get_binder_for_profile(session, binder_id, profile_id)

    if binder_type is not None and binder_type != binder.binder_type:
        raise BinderValidationError("binder_type is immutable and cannot be changed.")

    if name is not None:
        binder.name = _validate_name(name)

    if sort_order is not None:
        binder.sort_order = _validate_sort(sort_order)

    new_rows = _validate_dimension(rows, "rows") if rows is not None else binder.rows
    new_cols = (
        _validate_dimension(columns, "columns") if columns is not None else binder.columns
    )

    layout_changed = new_rows != binder.rows or new_cols != binder.columns

    if layout_changed and binder.binder_type == BinderType.FREE_PLACEMENT.value:
        _reflow_placements(session, binder, new_rows=new_rows, new_cols=new_cols)

    binder.rows = new_rows
    binder.columns = new_cols

    session.add(binder)
    session.commit()
    session.refresh(binder)
    return binder


def set_default_binder(session: Session, binder_id: int, profile_id: int) -> Binder:
    """Make ``binder_id`` the profile's default binder.

    Clears the default flag on all the profile's other binders.

    Raises:
        BinderNotFoundError
    """
    target = get_binder_for_profile(session, binder_id, profile_id)

    others = session.exec(
        select(Binder).where(
            Binder.profile_id == profile_id,
            Binder.is_default == True,  # noqa: E712
        )
    ).all()
    for other in others:
        if other.id != target.id:
            other.is_default = False
            session.add(other)

    target.is_default = True
    session.add(target)
    session.commit()
    session.refresh(target)
    return target


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_binder(session: Session, binder_id: int, profile_id: int) -> None:
    """Delete a binder.

    Rules:
    - A profile must always retain at least one binder — deleting the final
      binder raises BinderMinimumError.
    - Deleting the default binder promotes the oldest remaining binder to
      default (prefer-oldest).
    - Placements belonging to the binder are cascade-deleted; Collection is
      never touched.

    Raises:
        BinderNotFoundError, BinderMinimumError
    """
    binder = get_binder_for_profile(session, binder_id, profile_id)

    all_binders = list_binders(session, profile_id)
    if len(all_binders) <= 1:
        raise BinderMinimumError(
            "Cannot delete the last remaining binder. Create another binder first."
        )

    was_default = binder.is_default

    session.delete(binder)
    session.commit()

    if was_default:
        remaining = list_binders(session, profile_id)  # oldest first
        if remaining:
            new_default = remaining[0]
            new_default.is_default = True
            session.add(new_default)
            session.commit()


# ---------------------------------------------------------------------------
# Reflow (FREE_PLACEMENT layout change)
# ---------------------------------------------------------------------------

def _reflow_placements(
    session: Session, binder: Binder, *, new_rows: int, new_cols: int
) -> None:
    """Reassign placements to a new capacity, preserving linear ordering.

    The stable linear index of each placement is ``(page - 1) * old_cap + slot``.
    Placements are sorted by that index and repacked densely into the new
    capacity: ``new_page = idx // new_cap + 1``, ``new_slot = idx % new_cap``.

    To avoid transient UNIQUE(binder_id, page, slot) violations while
    rewriting, all affected placements are first moved to negative (temporary)
    page values, then written to their final positions. The caller commits.
    """
    old_cap = _capacity(binder)
    new_cap = new_rows * new_cols

    placements = list(
        session.exec(
            select(BinderPlacement)
            .where(BinderPlacement.binder_id == binder.id)
            .order_by(BinderPlacement.page, BinderPlacement.slot)  # type: ignore[arg-type]
        ).all()
    )
    if not placements:
        return

    # Compute stable linear order using the OLD capacity.
    ordered = sorted(
        placements, key=lambda p: (p.page - 1) * old_cap + p.slot
    )

    # Phase 1: move everything out of the way (negative page numbers keep the
    # (page, slot) tuples unique among themselves and clear of final targets).
    for i, p in enumerate(ordered):
        p.page = -(i + 1)
        p.slot = 0
        session.add(p)
    session.flush()

    # Phase 2: write final dense positions using the NEW capacity.
    for idx, p in enumerate(ordered):
        p.page = idx // new_cap + 1
        p.slot = idx % new_cap
        session.add(p)
    session.flush()


# ---------------------------------------------------------------------------
# Placements (FREE_PLACEMENT only)
# ---------------------------------------------------------------------------

def _require_free_placement(binder: Binder) -> None:
    if binder.binder_type != BinderType.FREE_PLACEMENT.value:
        raise PlacementValidationError(
            "Placements are only supported on FREE_PLACEMENT binders."
        )


def _validate_page_slot(binder: Binder, page: int, slot: int) -> None:
    if page < 1:
        raise PlacementValidationError("page must be >= 1.")
    capacity = _capacity(binder)
    if not (0 <= slot < capacity):
        raise PlacementValidationError(
            f"slot must be between 0 and {capacity - 1} for a {binder.rows}x{binder.columns} binder."
        )


def add_placement(
    session: Session,
    binder_id: int,
    profile_id: int,
    *,
    card_id: int,
    page: int,
    slot: int,
) -> BinderPlacement:
    """Place a card on a specific page/slot of a FREE_PLACEMENT binder.

    Rules:
    - The card must exist in the catalogue.
    - page/slot must be within the binder's capacity.
    - The slot must be empty (else PlacementConflictError → 409).
    - The same card may not appear twice in one binder (else 409).

    Raises:
        BinderNotFoundError, PlacementValidationError, PlacementConflictError
    """
    binder = get_binder_for_profile(session, binder_id, profile_id)
    _require_free_placement(binder)
    _validate_page_slot(binder, page, slot)

    card = session.get(Card, card_id)
    if card is None:
        raise PlacementValidationError(f"Card {card_id} does not exist.")

    # Duplicate card in the same binder?
    existing_card = session.exec(
        select(BinderPlacement).where(
            BinderPlacement.binder_id == binder_id,
            BinderPlacement.card_id == card_id,
        )
    ).first()
    if existing_card is not None:
        raise PlacementConflictError("This card is already in this binder.")

    # Slot occupied?
    occupied = session.exec(
        select(BinderPlacement).where(
            BinderPlacement.binder_id == binder_id,
            BinderPlacement.page == page,
            BinderPlacement.slot == slot,
        )
    ).first()
    if occupied is not None:
        raise PlacementConflictError("That slot is already occupied.")

    placement = BinderPlacement(
        binder_id=binder_id,
        card_id=card_id,
        page=page,
        slot=slot,
    )
    session.add(placement)
    session.commit()
    session.refresh(placement)
    return placement


def move_placement(
    session: Session,
    binder_id: int,
    profile_id: int,
    placement_id: int,
    *,
    page: int,
    slot: int,
) -> BinderPlacement:
    """Move an existing placement to a new empty page/slot.

    Moving onto an occupied slot raises PlacementConflictError (→ 409); cards
    are never swapped automatically. Moving to the placement's own current
    slot is a no-op.

    Raises:
        BinderNotFoundError, PlacementNotFoundError, PlacementValidationError,
        PlacementConflictError
    """
    binder = get_binder_for_profile(session, binder_id, profile_id)
    _require_free_placement(binder)
    _validate_page_slot(binder, page, slot)

    placement = session.get(BinderPlacement, placement_id)
    if placement is None or placement.binder_id != binder_id:
        raise PlacementNotFoundError(f"Placement {placement_id} not found.")

    if placement.page == page and placement.slot == slot:
        return placement  # No-op.

    occupied = session.exec(
        select(BinderPlacement).where(
            BinderPlacement.binder_id == binder_id,
            BinderPlacement.page == page,
            BinderPlacement.slot == slot,
        )
    ).first()
    if occupied is not None and occupied.id != placement_id:
        raise PlacementConflictError("That slot is already occupied.")

    placement.page = page
    placement.slot = slot
    session.add(placement)
    session.commit()
    session.refresh(placement)
    return placement


def remove_placement(
    session: Session, binder_id: int, profile_id: int, placement_id: int
) -> None:
    """Remove a placement from a binder.

    This ONLY removes the placement — it never modifies the Collection.

    Raises:
        BinderNotFoundError, PlacementNotFoundError
    """
    binder = get_binder_for_profile(session, binder_id, profile_id)

    placement = session.get(BinderPlacement, placement_id)
    if placement is None or placement.binder_id != binder_id:
        raise PlacementNotFoundError(f"Placement {placement_id} not found.")

    session.delete(placement)
    session.commit()


# ---------------------------------------------------------------------------
# Ownership derivation
# ---------------------------------------------------------------------------

def _owned_card_ids(session: Session, profile_id: int, card_ids: list[int]) -> set[int]:
    """Return the subset of ``card_ids`` the profile owns at CARD level.

    A card is "owned" if the profile has a card-level Collection entry for it.
    Ownership/concept status is derived here and never stored on placements.
    """
    if not card_ids:
        return set()
    rows = session.exec(
        select(Collection.card_id).where(
            Collection.profile_id == profile_id,
            Collection.card_id.in_(card_ids),  # type: ignore[union-attr]
        )
    ).all()
    return {cid for cid in rows if cid is not None}


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

def get_binder_page_for(
    session: Session,
    binder: Binder,
    *,
    profile_id: int,
    page: int = 1,
    page_size: int | None = None,
) -> dict:
    """Return a page of a specific binder, branching on its type."""
    if binder.binder_type == BinderType.FREE_PLACEMENT.value:
        return _build_free_placement_page(
            session, binder, profile_id=profile_id, page=page
        )
    return _build_pokedex_page(
        session, binder, profile_id=profile_id, page=page, page_size=page_size
    )


def _build_pokedex_page(
    session: Session,
    binder: Binder,
    *,
    profile_id: int,
    page: int = 1,
    page_size: int | None = None,
) -> dict:
    """Derive a National Dex page for a POKEDEX binder.

    This preserves the original single-binder behaviour: slots come from
    National Dex #1–#1025, ownership and the representative (binder) card come
    from the Collection, and NO concept cards are shown for unowned species.
    """
    if page_size is None:
        page_size = binder.rows * binder.columns

    total_pages = math.ceil(NATIONAL_DEX_COUNT / page_size)

    start_dex = (page - 1) * page_size + 1
    end_dex = min(start_dex + page_size - 1, NATIONAL_DEX_COUNT)

    species_list = list(
        session.exec(
            select(PokemonSpecies)
            .where(
                PokemonSpecies.national_dex_number >= start_dex,
                PokemonSpecies.national_dex_number <= end_dex,
            )
            .order_by(PokemonSpecies.national_dex_number)  # type: ignore[arg-type]
        ).all()
    )

    species_by_dex: dict[int, PokemonSpecies] = {}
    species_ids: list[int] = []
    for s in species_list:
        species_by_dex[s.national_dex_number] = s
        if s.id is not None:
            species_ids.append(s.id)

    owned_via_species: set[int] = set()
    if species_ids:
        owned_via_species = set(
            session.exec(
                select(Collection.pokemon_species_id).where(
                    Collection.profile_id == profile_id,
                    Collection.pokemon_species_id.in_(species_ids),  # type: ignore[union-attr]
                    Collection.card_id.is_(None),  # type: ignore[union-attr]
                )
            ).all()
        )

    owned_via_cards: set[int] = set()
    if species_ids:
        owned_via_cards = set(
            session.exec(
                select(Card.pokemon_species_id)
                .join(Collection, Collection.card_id == Card.id)
                .where(
                    Collection.profile_id == profile_id,
                    Card.pokemon_species_id.in_(species_ids),  # type: ignore[union-attr]
                )
                .distinct()
            ).all()
        )

    owned_species_ids = owned_via_species | owned_via_cards
    species_with_cards = owned_via_cards

    binder_card_by_species: dict[int, dict] = {}
    if species_with_cards:
        owned_cards_stmt = (
            select(
                Card.id,
                Card.api_card_id,
                Card.card_number,
                Card.rarity,
                Card.image_url,
                Card.pokemon_species_id,
                Set.name.label("set_name"),  # type: ignore[attr-defined]
                Set.api_set_id.label("set_code"),  # type: ignore[attr-defined]
                Collection.is_binder_card,
                Collection.quantity,
            )
            .join(Collection, Collection.card_id == Card.id)
            .join(Set, Card.set_id == Set.id, isouter=True)
            .where(
                Collection.profile_id == profile_id,
                Card.pokemon_species_id.in_(species_with_cards),  # type: ignore[union-attr]
            )
            .order_by(
                Collection.is_binder_card.desc(),  # type: ignore[union-attr]
                Card.card_number,
                Card.id,
            )
        )
        for row in session.exec(owned_cards_stmt).all():  # type: ignore[call-overload]
            sp_id = row.pokemon_species_id
            if sp_id not in binder_card_by_species:
                binder_card_by_species[sp_id] = {
                    "id": row.id,
                    "api_card_id": row.api_card_id,
                    "card_number": row.card_number,
                    "rarity": row.rarity,
                    "image_url": row.image_url,
                    "set_name": row.set_name,
                    "set_code": row.set_code,
                    "quantity": row.quantity,
                }

    quantity_by_species: dict[int, int] = {}
    if species_with_cards:
        qty_stmt = (
            select(
                Card.pokemon_species_id,
                func.sum(Collection.quantity).label("total_qty"),
            )
            .join(Collection, Collection.card_id == Card.id)
            .where(
                Collection.profile_id == profile_id,
                Card.pokemon_species_id.in_(species_with_cards),  # type: ignore[union-attr]
            )
            .group_by(Card.pokemon_species_id)
        )
        for row in session.exec(qty_stmt).all():  # type: ignore[call-overload]
            quantity_by_species[row.pokemon_species_id] = row.total_qty

    slots = []
    for dex_num in range(start_dex, end_dex + 1):
        species = species_by_dex.get(dex_num)
        if species is None:
            slots.append(_empty_pokedex_slot(dex_num))
            continue

        is_owned = species.id in owned_species_ids
        has_card = species.id in species_with_cards
        card = binder_card_by_species.get(species.id) if has_card else None  # type: ignore
        total_cards = quantity_by_species.get(species.id, 0) if has_card else 0  # type: ignore

        slots.append(
            {
                "dex_number": dex_num,
                "species_name": species.name,
                "species_id": species.id,
                "owned": is_owned,
                "has_card": has_card,
                "card": card,
                "total_cards": total_cards,
            }
        )

    while len(slots) < page_size:
        slots.append(_empty_pokedex_slot(None))

    return {
        "page": page,
        "page_size": page_size,
        "total_species": NATIONAL_DEX_COUNT,
        "total_pages": total_pages,
        "slots": slots,
    }


def _empty_pokedex_slot(dex_number: int | None) -> dict:
    return {
        "dex_number": dex_number,
        "species_name": None,
        "species_id": None,
        "owned": False,
        "has_card": False,
        "card": None,
        "total_cards": 0,
    }


def _build_free_placement_page(
    session: Session,
    binder: Binder,
    *,
    profile_id: int,
    page: int = 1,
) -> dict:
    """Build a page of a FREE_PLACEMENT binder.

    Slots are explicit placements. Each occupied slot exposes the card and a
    derived ``is_concept`` flag (True when the active profile does not own that
    specific card). Empty slots have ``card=None``.
    """
    capacity = binder.rows * binder.columns

    # Total pages: at least 1, or enough to hold the highest occupied page.
    max_page_row = session.exec(
        select(func.max(BinderPlacement.page)).where(
            BinderPlacement.binder_id == binder.id
        )
    ).first()
    max_page = max_page_row if isinstance(max_page_row, int) else (max_page_row or 1)
    total_pages = max(1, max_page or 1)

    placements = list(
        session.exec(
            select(
                BinderPlacement.id,
                BinderPlacement.slot,
                Card.id.label("card_id"),  # type: ignore[attr-defined]
                Card.api_card_id,
                Card.card_number,
                Card.rarity,
                Card.image_url,
                Card.pokemon_species_id,
                PokemonSpecies.name.label("pokemon_name"),  # type: ignore[attr-defined]
                PokemonSpecies.national_dex_number,
                Set.name.label("set_name"),  # type: ignore[attr-defined]
                Set.api_set_id.label("set_code"),  # type: ignore[attr-defined]
            )
            .join(Card, BinderPlacement.card_id == Card.id)
            .join(PokemonSpecies, Card.pokemon_species_id == PokemonSpecies.id, isouter=True)
            .join(Set, Card.set_id == Set.id, isouter=True)
            .where(
                BinderPlacement.binder_id == binder.id,
                BinderPlacement.page == page,
            )
            .order_by(BinderPlacement.slot)  # type: ignore[arg-type]
        ).all()  # type: ignore[call-overload]
    )

    card_ids = [row.card_id for row in placements]
    owned_ids = _owned_card_ids(session, profile_id, card_ids)

    placement_by_slot: dict[int, dict] = {}
    for row in placements:
        placement_by_slot[row.slot] = {
            "placement_id": row.id,
            "card_id": row.card_id,
            "api_card_id": row.api_card_id,
            "card_number": row.card_number,
            "rarity": row.rarity,
            "image_url": row.image_url,
            "species_id": row.pokemon_species_id,
            "pokemon_name": row.pokemon_name,
            "national_dex_number": row.national_dex_number,
            "set_name": row.set_name,
            "set_code": row.set_code,
            "is_concept": row.card_id not in owned_ids,
        }

    slots = []
    for slot_index in range(capacity):
        placement = placement_by_slot.get(slot_index)
        if placement is None:
            slots.append(
                {
                    "slot": slot_index,
                    "placement_id": None,
                    "card": None,
                    "is_concept": False,
                }
            )
        else:
            slots.append(
                {
                    "slot": slot_index,
                    "placement_id": placement["placement_id"],
                    "card": {
                        "card_id": placement["card_id"],
                        "api_card_id": placement["api_card_id"],
                        "card_number": placement["card_number"],
                        "rarity": placement["rarity"],
                        "image_url": placement["image_url"],
                        "species_id": placement["species_id"],
                        "pokemon_name": placement["pokemon_name"],
                        "national_dex_number": placement["national_dex_number"],
                        "set_name": placement["set_name"],
                        "set_code": placement["set_code"],
                    },
                    "is_concept": placement["is_concept"],
                }
            )

    return {
        "page": page,
        "page_size": capacity,
        "total_pages": total_pages,
        "rows": binder.rows,
        "columns": binder.columns,
        "slots": slots,
    }


# ===========================================================================
# Compatibility layer — original single-binder API operating on the active
# profile's DEFAULT POKEDEX binder.
# ===========================================================================

def get_binder_page(
    session: Session,
    *,
    page: int = 1,
    page_size: int | None = None,
) -> dict:
    """Return a page of the active profile's default POKEDEX binder.

    Backwards-compatible entry point used by the legacy ``/binder/page`` route.
    Falls back to the profile's ``binder_*`` settings if (unexpectedly) no
    binder exists yet, preserving the original behaviour.
    """
    profile = get_active_profile(session)
    profile_id = profile.id
    assert profile_id is not None

    binder = session.exec(
        select(Binder)
        .where(
            Binder.profile_id == profile_id,
            Binder.binder_type == BinderType.POKEDEX.value,
        )
        .order_by(Binder.is_default.desc(), Binder.created_at, Binder.id)  # type: ignore[union-attr]
    ).first()

    if binder is None:
        # Legacy fallback: derive directly from the profile's settings.
        if page_size is None:
            page_size = profile.binder_rows * profile.binder_columns
        pseudo = Binder(
            profile_id=profile_id,
            name="Pokédex Binder",
            binder_type=BinderType.POKEDEX.value,
            rows=profile.binder_rows,
            columns=profile.binder_columns,
            sort_order=profile.binder_sort,
            is_default=True,
        )
        return _build_pokedex_page(
            session, pseudo, profile_id=profile_id, page=page, page_size=page_size
        )

    return _build_pokedex_page(
        session, binder, profile_id=profile_id, page=page, page_size=page_size
    )


# ---------------------------------------------------------------------------
# Binder card selection (unchanged behaviour — representative card per species)
# ---------------------------------------------------------------------------

def set_binder_card(session: Session, collection_entry_id: int) -> bool:
    """Select a card-level collection entry as the binder card for its species.

    Deselects any other binder card for the same species+profile.

    Returns True if successful, False if entry not found or not a card entry.
    """
    entry = session.get(Collection, collection_entry_id)
    if entry is None or entry.card_id is None:
        return False

    profile_id = entry.profile_id

    card = session.get(Card, entry.card_id)
    if card is None or card.pokemon_species_id is None:
        return False

    species_id = card.pokemon_species_id

    other_entries = session.exec(
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(
            Collection.profile_id == profile_id,
            Card.pokemon_species_id == species_id,
            Collection.is_binder_card == True,  # noqa: E712
        )
    ).all()
    for other in other_entries:
        other.is_binder_card = False
        session.add(other)

    entry.is_binder_card = True
    session.add(entry)
    session.commit()
    return True


def unset_binder_card(session: Session, collection_entry_id: int) -> bool:
    """Remove binder card selection from a collection entry.

    Returns True if successful.
    """
    entry = session.get(Collection, collection_entry_id)
    if entry is None:
        return False

    entry.is_binder_card = False
    session.add(entry)
    session.commit()
    return True


def auto_select_binder_card_for_species(
    session: Session, profile_id: int, species_id: int
) -> None:
    """Auto-select a binder card if only one card entry exists for the species.

    Called after a card removal to maintain a valid binder state.
    """
    remaining = session.exec(
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(
            Collection.profile_id == profile_id,
            Card.pokemon_species_id == species_id,
            Collection.card_id.is_not(None),  # type: ignore[union-attr]
        )
    ).all()

    if len(remaining) == 1:
        remaining[0].is_binder_card = True
        session.add(remaining[0])
        session.commit()
    elif len(remaining) == 0:
        pass
    else:
        has_selected = any(e.is_binder_card for e in remaining)
        if not has_selected:
            remaining[0].is_binder_card = True
            session.add(remaining[0])
            session.commit()
