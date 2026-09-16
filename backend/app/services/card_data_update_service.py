"""Card-data update service (Stage 1 — read-only manifest check).

Responsible ONLY for retrieving and interpreting the remote card-data
``manifest.json`` published by the public PullDex-Card-Data repository, and
comparing it against the locally-stored card-data version.

Stage 1 scope:
    * fetch the manifest over HTTPS (stdlib urllib — no third-party deps,
      because httpx is excluded from the packaged build)
    * handle network errors / timeouts gracefully
    * parse + validate the manifest structure and schema_version
    * expose remote data_version, set/card counts, and per-set metadata
    * determine whether the remote catalogue is newer than the local one

It does NOT (in Stage 1):
    * download any set file
    * insert/update/delete any card, set, collection, profile, or binder row
    * modify the database in any way (it only READS the local version)

The HTTP fetch is isolated in :func:`fetch_manifest_text` so tests can mock
it without any network access.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from app.config import settings

# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class UpdateStatus(str, Enum):
    """Outcome of a card-data update check."""

    UP_TO_DATE = "UP_TO_DATE"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    REMOTE_UNAVAILABLE = "REMOTE_UNAVAILABLE"
    INVALID_MANIFEST = "INVALID_MANIFEST"
    INCOMPATIBLE_SCHEMA = "INCOMPATIBLE_SCHEMA"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RemoteSetInfo:
    """Per-set metadata carried from the manifest.

    Retained for Stage 2 (which will diff sets by version/sha256) but not
    persisted in Stage 1.
    """

    id: str
    name: str
    file: str
    version: int
    sha256: str
    card_count: int


@dataclass(frozen=True)
class UpdateCheckResult:
    """Structured result of a card-data update check."""

    status: UpdateStatus
    local_data_version: int
    remote_data_version: int | None = None
    remote_schema_version: int | None = None
    remote_set_count: int | None = None
    remote_card_count: int | None = None
    sets: list[RemoteSetInfo] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "local_data_version": self.local_data_version,
            "remote_data_version": self.remote_data_version,
            "remote_schema_version": self.remote_schema_version,
            "remote_set_count": self.remote_set_count,
            "remote_card_count": self.remote_card_count,
            "update_available": self.status is UpdateStatus.UPDATE_AVAILABLE,
            "error": self.error,
            "sets": [
                {
                    "id": s.id,
                    "name": s.name,
                    "file": s.file,
                    "version": s.version,
                    "sha256": s.sha256,
                    "card_count": s.card_count,
                }
                for s in self.sets
            ],
        }


class ManifestValidationError(Exception):
    """Raised when the manifest is structurally invalid."""


# ---------------------------------------------------------------------------
# HTTP fetch (isolated for mockability; stdlib only)
# ---------------------------------------------------------------------------


def fetch_manifest_text(url: str, timeout: float) -> str:
    """Fetch the raw manifest text over HTTP(S) using the standard library.

    Uses ``urllib.request`` rather than httpx because httpx is excluded from
    the packaged (PyInstaller) build. Raises ``urllib.error.URLError`` /
    ``urllib.error.HTTPError`` / ``TimeoutError`` on failure — callers handle
    these and map them to :attr:`UpdateStatus.REMOTE_UNAVAILABLE`.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "PullDex", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted config URL)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset)


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------


def _validate_manifest(data: object) -> dict:
    """Validate the manifest structure. Returns the manifest dict or raises.

    Enforces the minimum contract documented in PullDex-Card-Data/README.md.
    """
    if not isinstance(data, dict):
        raise ManifestValidationError("Manifest must be a JSON object.")

    for key in ("schema_version", "data_version", "set_count", "card_count", "sets"):
        if key not in data:
            raise ManifestValidationError(f"Manifest missing required field '{key}'.")

    if not isinstance(data["schema_version"], int):
        raise ManifestValidationError("schema_version must be an integer.")
    if not isinstance(data["data_version"], int):
        raise ManifestValidationError("data_version must be an integer.")
    if not isinstance(data["set_count"], int):
        raise ManifestValidationError("set_count must be an integer.")
    if not isinstance(data["card_count"], int):
        raise ManifestValidationError("card_count must be an integer.")
    if not isinstance(data["sets"], list):
        raise ManifestValidationError("sets must be an array.")

    seen_ids: set[str] = set()
    for i, s in enumerate(data["sets"]):
        if not isinstance(s, dict):
            raise ManifestValidationError(f"sets[{i}] must be an object.")
        for key in ("id", "name", "file", "version", "sha256", "card_count"):
            if key not in s:
                raise ManifestValidationError(f"sets[{i}] missing required field '{key}'.")
        if not isinstance(s["id"], str) or not s["id"]:
            raise ManifestValidationError(f"sets[{i}].id must be a non-empty string.")
        if not isinstance(s["name"], str) or not s["name"]:
            raise ManifestValidationError(f"sets[{i}].name must be a non-empty string.")
        if not isinstance(s["file"], str) or not s["file"]:
            raise ManifestValidationError(f"sets[{i}].file must be a non-empty string.")
        if not isinstance(s["version"], int):
            raise ManifestValidationError(f"sets[{i}].version must be an integer.")
        if not isinstance(s["card_count"], int):
            raise ManifestValidationError(f"sets[{i}].card_count must be an integer.")
        if not isinstance(s["sha256"], str) or not _SHA256_RE.match(s["sha256"]):
            raise ManifestValidationError(
                f"sets[{i}].sha256 must be a 64-character lowercase hex string."
            )
        if s["id"] in seen_ids:
            raise ManifestValidationError(f"Duplicate set id '{s['id']}'.")
        seen_ids.add(s["id"])

    if data["set_count"] != len(data["sets"]):
        raise ManifestValidationError(
            f"set_count ({data['set_count']}) does not match number of set "
            f"entries ({len(data['sets'])})."
        )

    return data


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CardDataUpdateService:
    """Checks the remote card-data manifest against the local version.

    Read-only with respect to card data. The only local read is the
    card-data version; no writes occur during a check.
    """

    def __init__(
        self,
        local_data_version: int,
        manifest_url: str | None = None,
        supported_schema_version: int | None = None,
        timeout: float | None = None,
        fetcher: Callable[[str, float], str] | None = None,
    ) -> None:
        self.local_data_version = local_data_version
        self.manifest_url = manifest_url or settings.card_data_manifest_url
        self.supported_schema_version = (
            supported_schema_version
            if supported_schema_version is not None
            else settings.card_data_supported_schema_version
        )
        self.timeout = timeout if timeout is not None else settings.card_data_request_timeout
        # Injectable HTTP fetcher (defaults to the stdlib implementation).
        self._fetcher = fetcher or fetch_manifest_text

    def check(self) -> UpdateCheckResult:
        """Perform the read-only update check and return a structured result.

        Never raises for expected failure modes (network down, bad JSON,
        invalid manifest, unsupported schema) — these map to explicit
        statuses so the application keeps working offline.
        """
        # 1. Fetch
        try:
            text = self._fetcher(self.manifest_url, self.timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            return UpdateCheckResult(
                status=UpdateStatus.REMOTE_UNAVAILABLE,
                local_data_version=self.local_data_version,
                error=f"Could not reach card-data manifest: {exc}",
            )
        except Exception as exc:  # defensive: any unexpected fetch error is non-fatal
            return UpdateCheckResult(
                status=UpdateStatus.REMOTE_UNAVAILABLE,
                local_data_version=self.local_data_version,
                error=f"Unexpected error fetching manifest: {exc}",
            )

        # 2. Parse JSON
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            return UpdateCheckResult(
                status=UpdateStatus.INVALID_MANIFEST,
                local_data_version=self.local_data_version,
                error=f"Manifest is not valid JSON: {exc}",
            )

        # 3. Validate structure
        try:
            manifest = _validate_manifest(data)
        except ManifestValidationError as exc:
            return UpdateCheckResult(
                status=UpdateStatus.INVALID_MANIFEST,
                local_data_version=self.local_data_version,
                error=str(exc),
            )

        remote_schema = manifest["schema_version"]
        remote_data_version = manifest["data_version"]

        # 4. Schema compatibility (checked before version comparison)
        if remote_schema > self.supported_schema_version:
            return UpdateCheckResult(
                status=UpdateStatus.INCOMPATIBLE_SCHEMA,
                local_data_version=self.local_data_version,
                remote_data_version=remote_data_version,
                remote_schema_version=remote_schema,
                remote_set_count=manifest["set_count"],
                remote_card_count=manifest["card_count"],
                error=(
                    f"Remote manifest schema_version {remote_schema} is newer than "
                    f"supported {self.supported_schema_version}; a PullDex update is required."
                ),
            )

        sets = [
            RemoteSetInfo(
                id=s["id"],
                name=s["name"],
                file=s["file"],
                version=s["version"],
                sha256=s["sha256"],
                card_count=s["card_count"],
            )
            for s in manifest["sets"]
        ]

        # 5. Version comparison policy:
        #    remote > local  -> UPDATE_AVAILABLE
        #    remote <= local -> UP_TO_DATE  (local same or ahead; never downgrade)
        if remote_data_version > self.local_data_version:
            status = UpdateStatus.UPDATE_AVAILABLE
        else:
            status = UpdateStatus.UP_TO_DATE

        return UpdateCheckResult(
            status=status,
            local_data_version=self.local_data_version,
            remote_data_version=remote_data_version,
            remote_schema_version=remote_schema,
            remote_set_count=manifest["set_count"],
            remote_card_count=manifest["card_count"],
            sets=sets,
        )
