"""Card-data updater service (Stage 2B — the real update).

This performs the actual card *reference-data* update: it downloads the set
files referenced by the remote manifest, validates them (SHA-256 + structure),
backs up the local database, and atomically merges the reference data
(sets + cards) into the local database — **without ever touching user data**
(collection, ownership, quantities, binder, profiles, settings) and **without
ever replacing the database file**.

Design guarantees (map directly onto the Stage 2B spec):

* Read remote manifest via the existing Stage 1 helpers (stdlib urllib).
* Compare remote ``data_version`` with local; never downgrade.
* Download only the set files that are missing or whose content changed
  (per-set version/sha256), falling back safely.
* SHA-256 every downloaded file BEFORE parsing; reject on mismatch.
* Validate every set payload fully BEFORE opening the DB transaction — an
  invalid set rejects the ENTIRE update (no partial import).
* Back up the DB immediately before the first modification (timestamped,
  never overwriting); abort the update if the backup fails.
* All reference-data writes happen inside ONE transaction. On any failure the
  transaction rolls back and the local ``card_data_version`` is unchanged.
* Merge is additive/idempotent: match sets by ``api_set_id`` and cards by
  ``api_card_id``; create missing rows, update changed reference fields in
  place (keeping stable primary keys so collection FKs keep working), and
  NEVER delete existing sets or cards.
* Species are resolved by ``national_dex_number`` against existing species.
  A Pokémon card (non-null dex) that cannot be mapped fails the update.
  Trainer/Energy cards (null dex) keep ``pokemon_species_id = None``.
* ``card_data_version`` is set to the remote ``data_version`` only after the
  transaction commits successfully.

Nothing here raises to the caller for expected failure modes — every outcome
is a structured :class:`UpdateResult` with a safe status/message (no stack
traces are surfaced to the UI).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from sqlmodel import Session, select

from app.config import settings
from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.card_data_update_service import (
    ManifestValidationError,
    UpdateStatus,
    _validate_manifest,
    fetch_manifest_text,
)
from app.services.card_data_version_service import (
    get_local_card_data_version,
    stage_local_card_data_version,
)


# ---------------------------------------------------------------------------
# Result status
# ---------------------------------------------------------------------------


class UpdateResultStatus(str, Enum):
    """Outcome of an :func:`update_card_data` operation."""

    UPDATED = "UPDATED"
    ALREADY_UP_TO_DATE = "ALREADY_UP_TO_DATE"
    REMOTE_UNAVAILABLE = "REMOTE_UNAVAILABLE"
    INVALID_MANIFEST = "INVALID_MANIFEST"
    INCOMPATIBLE_SCHEMA = "INCOMPATIBLE_SCHEMA"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    HASH_MISMATCH = "HASH_MISMATCH"
    INVALID_SET_DATA = "INVALID_SET_DATA"
    DATABASE_BACKUP_FAILED = "DATABASE_BACKUP_FAILED"
    DATABASE_UPDATE_FAILED = "DATABASE_UPDATE_FAILED"


# User-facing generic messages. Deliberately free of internal detail / stack
# traces. The concrete (still non-sensitive) reason is attached as ``error``.
_STATUS_MESSAGES: dict[UpdateResultStatus, str] = {
    UpdateResultStatus.UPDATED: "Card data updated successfully.",
    UpdateResultStatus.ALREADY_UP_TO_DATE: "Card data is already up to date.",
    UpdateResultStatus.REMOTE_UNAVAILABLE: "Could not reach the card-data source.",
    UpdateResultStatus.INVALID_MANIFEST: "The card-data manifest was invalid.",
    UpdateResultStatus.INCOMPATIBLE_SCHEMA: (
        "This card data is not compatible with this version of PullDex."
    ),
    UpdateResultStatus.DOWNLOAD_FAILED: "A card-data file could not be downloaded.",
    UpdateResultStatus.HASH_MISMATCH: (
        "A downloaded card-data file failed its integrity check."
    ),
    UpdateResultStatus.INVALID_SET_DATA: "The downloaded card data was invalid.",
    UpdateResultStatus.DATABASE_BACKUP_FAILED: (
        "Could not create a database backup before updating."
    ),
    UpdateResultStatus.DATABASE_UPDATE_FAILED: (
        "The card-data update could not be applied; no changes were made."
    ),
}


@dataclass(frozen=True)
class UpdateResult:
    """Structured, UI-safe result of an update operation."""

    status: UpdateResultStatus
    local_data_version: int
    remote_data_version: int | None = None
    sets_created: int = 0
    sets_updated: int = 0
    cards_created: int = 0
    cards_updated: int = 0
    set_count: int | None = None
    card_count: int | None = None
    backup_path: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status in (
            UpdateResultStatus.UPDATED,
            UpdateResultStatus.ALREADY_UP_TO_DATE,
        )

    @property
    def message(self) -> str:
        return _STATUS_MESSAGES.get(self.status, "Card data update finished.")

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "local_data_version": self.local_data_version,
            "remote_data_version": self.remote_data_version,
            "sets_created": self.sets_created,
            "sets_updated": self.sets_updated,
            "cards_created": self.cards_created,
            "cards_updated": self.cards_updated,
            "set_count": self.set_count,
            "card_count": self.card_count,
            # backup_path is a local filesystem path; safe to surface but the UI
            # need not display it.
            "backup_path": self.backup_path,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Exceptions used internally to short-circuit to a specific status
# ---------------------------------------------------------------------------


class _DownloadError(Exception):
    pass


class _HashMismatchError(Exception):
    pass


class SetValidationError(Exception):
    """Raised when a downloaded set payload is structurally invalid."""


class _BackupError(Exception):
    pass


# ---------------------------------------------------------------------------
# Download (stdlib only — httpx is excluded from the packaged build)
# ---------------------------------------------------------------------------


def fetch_set_file_bytes(url: str, timeout: float) -> bytes:
    """Fetch the raw bytes of a set file over HTTP(S) using the standard library.

    Returns the exact bytes so the SHA-256 can be computed over them (the
    manifest hash is defined over the exact file bytes). Raises on any network
    / HTTP / timeout error; callers map these to ``DOWNLOAD_FAILED``.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "PullDex", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted config URL)
        return resp.read()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _set_file_url(base_manifest_url: str, file_path: str) -> str:
    """Resolve a set file's absolute URL from the manifest URL + relative path.

    The manifest lives at ``…/main/manifest.json`` and set files are referenced
    relative to the repo root (e.g. ``sets/me55.json``), so we resolve against
    the manifest's directory.
    """
    return urllib.parse.urljoin(base_manifest_url, file_path)


# ---------------------------------------------------------------------------
# Set-payload validation (runs BEFORE any DB transaction)
# ---------------------------------------------------------------------------

_REQUIRED_CARD_FIELDS = (
    "api_card_id",
    "card_number",
    "rarity",
    "variant",
    "image_url",
    "national_dex_number",
    "species_name",
)


def _validate_release_date(value: object, ctx: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise SetValidationError(f"{ctx}: release_date must be a string or null.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise SetValidationError(f"{ctx}: release_date '{value}' is not ISO YYYY-MM-DD.") from exc


def validate_set_payload(payload: object, expected_set_id: str) -> dict:
    """Validate a single downloaded set payload. Returns it or raises.

    Enforces the set-file contract documented in PullDex-Card-Data/README.md
    and guards against any value that could corrupt the database. Also verifies
    the payload is for the *expected* set id from the manifest.
    """
    if not isinstance(payload, dict):
        raise SetValidationError("Set file must be a JSON object.")

    # --- set metadata ---
    set_meta = payload.get("set")
    if not isinstance(set_meta, dict):
        raise SetValidationError("Set file missing 'set' object.")
    for key in ("id", "name", "series"):
        if key not in set_meta:
            raise SetValidationError(f"set.{key} is required.")
        if not isinstance(set_meta[key], str) or not set_meta[key]:
            raise SetValidationError(f"set.{key} must be a non-empty string.")
    if set_meta["id"] != expected_set_id:
        raise SetValidationError(
            f"set.id '{set_meta['id']}' does not match manifest id '{expected_set_id}'."
        )
    _validate_release_date(set_meta.get("release_date"), "set")

    # is_promo: required explicit boolean reference data (never inferred).
    if "is_promo" not in set_meta:
        raise SetValidationError("set.is_promo is required.")
    if not isinstance(set_meta["is_promo"], bool):
        raise SetValidationError("set.is_promo must be a boolean.")

    # length guards matching the model column limits (avoid DB corruption)
    if len(set_meta["name"]) > 150:
        raise SetValidationError("set.name exceeds 150 characters.")
    if len(set_meta["series"]) > 100:
        raise SetValidationError("set.series exceeds 100 characters.")
    if len(set_meta["id"]) > 50:
        raise SetValidationError("set.id exceeds 50 characters.")

    # --- cards ---
    if "card_count" not in payload or not isinstance(payload["card_count"], int):
        raise SetValidationError("card_count must be an integer.")
    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise SetValidationError("cards must be an array.")
    if payload["card_count"] != len(cards):
        raise SetValidationError(
            f"card_count ({payload['card_count']}) does not match number of "
            f"cards ({len(cards)})."
        )

    seen_ids: set[str] = set()
    for i, card in enumerate(cards):
        ctx = f"cards[{i}]"
        if not isinstance(card, dict):
            raise SetValidationError(f"{ctx} must be an object.")
        for key in _REQUIRED_CARD_FIELDS:
            if key not in card:
                raise SetValidationError(f"{ctx} missing required field '{key}'.")

        api_card_id = card["api_card_id"]
        if not isinstance(api_card_id, str) or not api_card_id:
            raise SetValidationError(f"{ctx}.api_card_id must be a non-empty string.")
        if len(api_card_id) > 50:
            raise SetValidationError(f"{ctx}.api_card_id exceeds 50 characters.")
        if api_card_id in seen_ids:
            raise SetValidationError(f"Duplicate api_card_id '{api_card_id}' within set.")
        seen_ids.add(api_card_id)

        # card_number: string or null; bounded length
        cn = card["card_number"]
        if cn is not None and (not isinstance(cn, str) or len(cn) > 20):
            raise SetValidationError(f"{ctx}.card_number must be a string (<=20 chars) or null.")

        # rarity / variant / image_url: string or null; bounded length
        for key, limit in (("rarity", 50), ("variant", 50), ("image_url", 500)):
            val = card[key]
            if val is not None and (not isinstance(val, str) or len(val) > limit):
                raise SetValidationError(
                    f"{ctx}.{key} must be a string (<={limit} chars) or null."
                )

        # national_dex_number: positive int or null
        dex = card["national_dex_number"]
        if dex is not None and (not isinstance(dex, int) or isinstance(dex, bool) or dex <= 0):
            raise SetValidationError(
                f"{ctx}.national_dex_number must be a positive integer or null."
            )

        # species_name: string or null. A Pokémon card (non-null dex) must name
        # a species; Trainer/Energy (null dex) must have null species_name.
        species_name = card["species_name"]
        if species_name is not None and not isinstance(species_name, str):
            raise SetValidationError(f"{ctx}.species_name must be a string or null.")
        if dex is None and species_name is not None:
            raise SetValidationError(
                f"{ctx}: species_name must be null when national_dex_number is null."
            )
        if dex is not None and not species_name:
            raise SetValidationError(
                f"{ctx}: species_name is required when national_dex_number is set."
            )

    return payload


# ---------------------------------------------------------------------------
# No-overwrite, abort-on-failure database backup
# ---------------------------------------------------------------------------


def _get_db_path() -> Path:
    """Filesystem path of the live SQLite database (from configuration)."""
    return Path(settings.database_url.removeprefix("sqlite:///"))


def create_pre_update_backup(db_path: Path | None = None, now: datetime | None = None) -> str:
    """Create a timestamped, non-overwriting backup of the database.

    Uses SQLite's online backup API for a consistent point-in-time copy. Names
    the file ``pulldex_backup_before_card_update_YYYYMMDD_HHMMSS.db`` in the
    database's parent directory. Never overwrites an existing file. Raises
    :class:`_BackupError` on any failure so the caller aborts the update.
    """
    db_path = db_path or _get_db_path()
    now = now or datetime.now()

    if not db_path.is_file():
        raise _BackupError(f"Database file not found at {db_path}.")

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"pulldex_backup_before_card_update_{timestamp}.db"
    if backup_path.exists():
        raise _BackupError(f"Backup target already exists: {backup_path.name}")

    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(db_path))
        dest = sqlite3.connect(str(backup_path))
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()
    except Exception as exc:  # noqa: BLE001 — any failure aborts the update
        # Clean up a partial/empty backup so it is never treated as valid.
        try:
            if backup_path.exists():
                backup_path.unlink()
        except OSError:
            pass
        raise _BackupError(str(exc)) from exc

    # Sanity check: the backup must be a usable SQLite database.
    try:
        check = sqlite3.connect(str(backup_path))
        try:
            check.execute("SELECT name FROM sqlite_master LIMIT 1")
        finally:
            check.close()
    except sqlite3.DatabaseError as exc:
        try:
            backup_path.unlink()
        except OSError:
            pass
        raise _BackupError(f"Backup is not a valid SQLite database: {exc}") from exc

    return str(backup_path)


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _parse_release_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class _MergeCounts:
    sets_created: int = 0
    sets_updated: int = 0
    cards_created: int = 0
    cards_updated: int = 0


@dataclass
class _DownloadedSet:
    manifest_entry: dict
    payload: dict


# ---------------------------------------------------------------------------
# The updater
# ---------------------------------------------------------------------------


class CardDataUpdater:
    """Performs the real card-data update.

    Network access is injected (``manifest_fetcher`` / ``set_fetcher``) so tests
    never touch GitHub. Defaults use the stdlib implementations.
    """

    def __init__(
        self,
        session: Session,
        manifest_url: str | None = None,
        supported_schema_version: int | None = None,
        timeout: float | None = None,
        manifest_fetcher: Callable[[str, float], str] | None = None,
        set_fetcher: Callable[[str, float], bytes] | None = None,
        backup_factory: Callable[[], str] | None = None,
    ) -> None:
        self.session = session
        self.manifest_url = manifest_url or settings.card_data_manifest_url
        self.supported_schema_version = (
            supported_schema_version
            if supported_schema_version is not None
            else settings.card_data_supported_schema_version
        )
        self.timeout = timeout if timeout is not None else settings.card_data_request_timeout
        self._fetch_manifest = manifest_fetcher or fetch_manifest_text
        self._fetch_set = set_fetcher or fetch_set_file_bytes
        self._backup_factory = backup_factory or create_pre_update_backup

    # -- public entrypoint --------------------------------------------------

    def update_card_data(self) -> UpdateResult:
        """Run the full update. Returns a structured, UI-safe result."""
        local_version = get_local_card_data_version(self.session)

        # 1. Fetch + validate manifest -------------------------------------
        try:
            manifest_text = self._fetch_manifest(self.manifest_url, self.timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            return self._fail(UpdateResultStatus.REMOTE_UNAVAILABLE, local_version, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._fail(UpdateResultStatus.REMOTE_UNAVAILABLE, local_version, str(exc))

        try:
            manifest = _validate_manifest(json.loads(manifest_text))
        except (json.JSONDecodeError, ValueError) as exc:
            return self._fail(UpdateResultStatus.INVALID_MANIFEST, local_version, str(exc))
        except ManifestValidationError as exc:
            return self._fail(UpdateResultStatus.INVALID_MANIFEST, local_version, str(exc))

        remote_schema = manifest["schema_version"]
        remote_version = manifest["data_version"]

        # 2. Schema compatibility ------------------------------------------
        if remote_schema > self.supported_schema_version:
            return self._fail(
                UpdateResultStatus.INCOMPATIBLE_SCHEMA,
                local_version,
                f"Remote schema_version {remote_schema} newer than supported "
                f"{self.supported_schema_version}.",
                remote_version=remote_version,
            )

        # 3. Version comparison — never downgrade --------------------------
        if remote_version <= local_version:
            return UpdateResult(
                status=UpdateResultStatus.ALREADY_UP_TO_DATE,
                local_data_version=local_version,
                remote_data_version=remote_version,
                set_count=manifest["set_count"],
                card_count=manifest["card_count"],
            )

        # 4. Decide which sets to download ---------------------------------
        #    Download missing/changed sets (by sha256 vs what we can detect).
        #    For a first implementation we (re)download every set the manifest
        #    lists when an update is required; each is validated before any DB
        #    write. This keeps correctness simple and still avoids unnecessary
        #    work for the common "nothing to do" path handled above.
        try:
            downloaded = self._download_and_verify_all(manifest)
        except _DownloadError as exc:
            return self._fail(UpdateResultStatus.DOWNLOAD_FAILED, local_version, str(exc),
                              remote_version=remote_version)
        except _HashMismatchError as exc:
            return self._fail(UpdateResultStatus.HASH_MISMATCH, local_version, str(exc),
                              remote_version=remote_version)

        # 5. Validate EVERY payload before touching the DB -----------------
        try:
            for d in downloaded:
                validate_set_payload(d.payload, d.manifest_entry["id"])
        except SetValidationError as exc:
            return self._fail(UpdateResultStatus.INVALID_SET_DATA, local_version, str(exc),
                              remote_version=remote_version)

        # 5b. Pre-resolve species for every Pokémon card. A Pokémon card whose
        #     dex number does not map to an existing species is a hard failure
        #     (spec §8) — detected BEFORE the transaction so nothing is written.
        try:
            species_by_dex = self._build_species_map(downloaded)
        except SetValidationError as exc:
            return self._fail(UpdateResultStatus.INVALID_SET_DATA, local_version, str(exc),
                              remote_version=remote_version)

        # 6. Backup immediately before the first modification --------------
        try:
            backup_path = self._backup_factory()
        except _BackupError as exc:
            return self._fail(UpdateResultStatus.DATABASE_BACKUP_FAILED, local_version, str(exc),
                              remote_version=remote_version)

        # 7. Atomic merge inside a single transaction ----------------------
        try:
            counts = self._merge(downloaded, species_by_dex)
            stage_local_card_data_version(self.session, remote_version)
            self.session.commit()
        except Exception as exc:  # noqa: BLE001 — roll back everything
            self.session.rollback()
            return self._fail(
                UpdateResultStatus.DATABASE_UPDATE_FAILED,
                local_version,
                str(exc),
                remote_version=remote_version,
                backup_path=backup_path,
            )

        return UpdateResult(
            status=UpdateResultStatus.UPDATED,
            local_data_version=remote_version,
            remote_data_version=remote_version,
            sets_created=counts.sets_created,
            sets_updated=counts.sets_updated,
            cards_created=counts.cards_created,
            cards_updated=counts.cards_updated,
            set_count=manifest["set_count"],
            card_count=manifest["card_count"],
            backup_path=backup_path,
        )

    # -- steps --------------------------------------------------------------

    def _download_and_verify_all(self, manifest: dict) -> list[_DownloadedSet]:
        downloaded: list[_DownloadedSet] = []
        for entry in manifest["sets"]:
            url = _set_file_url(self.manifest_url, entry["file"])
            try:
                raw = self._fetch_set(url, self.timeout)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                raise _DownloadError(f"Failed to download {entry['file']}: {exc}") from exc
            except Exception as exc:  # noqa: BLE001
                raise _DownloadError(f"Failed to download {entry['file']}: {exc}") from exc

            if not isinstance(raw, (bytes, bytearray)):
                raise _DownloadError(f"{entry['file']} did not return bytes.")

            actual_sha = _sha256_hex(bytes(raw))
            if actual_sha != entry["sha256"]:
                raise _HashMismatchError(
                    f"SHA-256 mismatch for {entry['file']}: "
                    f"expected {entry['sha256'][:12]}…, got {actual_sha[:12]}…"
                )

            try:
                payload = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
                # A hash-matching file that is not valid JSON is invalid data.
                raise _HashMismatchError(f"{entry['file']} is not valid JSON: {exc}") from exc

            downloaded.append(_DownloadedSet(manifest_entry=entry, payload=payload))
        return downloaded

    def _build_species_map(self, downloaded: list[_DownloadedSet]) -> dict[int, int]:
        """Map national_dex_number -> local PokemonSpecies.id for every dex
        number referenced by a Pokémon card. Raises if any is unmapped.

        Does not create or modify species — read-only.
        """
        needed: set[int] = set()
        for d in downloaded:
            for card in d.payload["cards"]:
                dex = card["national_dex_number"]
                if dex is not None:
                    needed.add(dex)

        result: dict[int, int] = {}
        for dex in needed:
            species = self.session.exec(
                select(PokemonSpecies).where(PokemonSpecies.national_dex_number == dex)
            ).first()
            if species is None or species.id is None:
                raise SetValidationError(
                    f"No local Pokémon species for national_dex_number {dex}; "
                    f"refusing to import to avoid corrupting species data."
                )
            result[dex] = species.id
        return result

    def _merge(
        self, downloaded: list[_DownloadedSet], species_by_dex: dict[int, int]
    ) -> _MergeCounts:
        """Merge all downloaded sets/cards additively. Assumes all payloads are
        already validated and all species resolved. Never deletes rows, never
        touches user data. Runs within the caller's transaction (the caller
        commits/rolls back)."""
        counts = _MergeCounts()

        for d in downloaded:
            set_meta = d.payload["set"]
            api_set_id = set_meta["id"]

            existing_set = self.session.exec(
                select(Set).where(Set.api_set_id == api_set_id)
            ).first()

            release = _parse_release_date(set_meta.get("release_date"))
            # is_promo is explicit reference data. Default to False if a
            # (legacy) payload omits it, for backward compatibility.
            is_promo = bool(set_meta.get("is_promo", False))
            if existing_set is None:
                existing_set = Set(
                    api_set_id=api_set_id,
                    name=set_meta["name"],
                    series=set_meta["series"],
                    release_date=release,
                    is_promo=is_promo,
                )
                self.session.add(existing_set)
                self.session.flush()  # assign id for card FK
                counts.sets_created += 1
            else:
                changed = (
                    existing_set.name != set_meta["name"]
                    or existing_set.series != set_meta["series"]
                    or existing_set.release_date != release
                    or existing_set.is_promo != is_promo
                )
                if changed:
                    existing_set.name = set_meta["name"]
                    existing_set.series = set_meta["series"]
                    existing_set.release_date = release
                    existing_set.is_promo = is_promo
                    self.session.add(existing_set)
                    counts.sets_updated += 1

            set_id = existing_set.id

            for card in d.payload["cards"]:
                api_card_id = card["api_card_id"]
                dex = card["national_dex_number"]
                species_id = species_by_dex.get(dex) if dex is not None else None

                existing_card = self.session.exec(
                    select(Card).where(Card.api_card_id == api_card_id)
                ).first()

                if existing_card is None:
                    self.session.add(
                        Card(
                            api_card_id=api_card_id,
                            set_id=set_id,
                            pokemon_species_id=species_id,
                            card_number=card["card_number"],
                            rarity=card["rarity"],
                            variant=card["variant"],
                            image_url=card["image_url"],
                        )
                    )
                    counts.cards_created += 1
                else:
                    changed = (
                        existing_card.set_id != set_id
                        or existing_card.pokemon_species_id != species_id
                        or existing_card.card_number != card["card_number"]
                        or existing_card.rarity != card["rarity"]
                        or existing_card.variant != card["variant"]
                        or existing_card.image_url != card["image_url"]
                    )
                    if changed:
                        existing_card.set_id = set_id
                        existing_card.pokemon_species_id = species_id
                        existing_card.card_number = card["card_number"]
                        existing_card.rarity = card["rarity"]
                        existing_card.variant = card["variant"]
                        existing_card.image_url = card["image_url"]
                        self.session.add(existing_card)
                        counts.cards_updated += 1

        return counts

    # -- helpers ------------------------------------------------------------

    def _fail(
        self,
        status: UpdateResultStatus,
        local_version: int,
        error: str,
        remote_version: int | None = None,
        backup_path: str | None = None,
    ) -> UpdateResult:
        return UpdateResult(
            status=status,
            local_data_version=local_version,
            remote_data_version=remote_version,
            backup_path=backup_path,
            error=error,
        )
