"""Offline validation of the reviewed Manijero source catalog.

The source catalog is the admission gate for the MVP corpus: a document may
only become eligible for ingestion when its provenance is on the approved
official-domain allowlist and its identity, freshness, integrity, and
human-review metadata are complete.

This module validates *catalog policy and metadata* only. It reads local JSON,
never performs network access, and never claims that a document is authentic,
currently in force, or legally applicable. The durable contract lives in
``knowledge/source_catalog.schema.json`` and ``knowledge/README.md``.
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

SCHEMA_VERSION = "source-catalog-v1"

TOP_LEVEL_KEYS = frozenset({"schema_version", "sources"})

SOURCE_REQUIRED_KEYS = frozenset(
    {
        "id",
        "title",
        "issuing_body",
        "original_url",
        "published_on",
        "downloaded_on",
        "verified_on",
        "content_sha256",
        "review_status",
        "reviewed_by",
        "reviewed_on",
        "lifecycle_status",
    }
)

SOURCE_OPTIONAL_KEYS = frozenset(
    {
        "consolidated_url",
        "valid_until",
        "campaign",
        "critical",
        "applicability",
    }
)

APPLICABILITY_KEYS = frozenset({"crop", "water_regime", "production_method"})

REVIEW_STATUSES = ("approved",)
LIFECYCLE_STATUSES = ("current",)
WATER_REGIMES = ("dryland", "irrigated", "mixed")
PRODUCTION_METHODS = ("conventional", "organic", "mixed")

# Approved official-domain allowlist. Matching is exact on the host, including
# the ``www.`` alias of each domain, so lookalike suffixes and subdomains are
# rejected. State legislation is published in the BOE even when the issuing
# ministry is MAPA or FEGA, so the BOE hosts are approved for those issuers.
_BOE_HOSTS = ("boe.es", "www.boe.es")

ISSUER_ALLOWED_HOSTS: Dict[str, Tuple[str, ...]] = {
    "BOE": _BOE_HOSTS,
    "Junta de Andalucía": ("juntadeandalucia.es", "www.juntadeandalucia.es"),
    "FEGA": ("fega.gob.es", "www.fega.gob.es") + _BOE_HOSTS,
    "MAPA": ("mapa.gob.es", "www.mapa.gob.es") + _BOE_HOSTS,
}

APPROVED_HOSTS = frozenset(host for hosts in ISSUER_ALLOWED_HOSTS.values() for host in hosts)

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CAMPAIGN_PATTERN = re.compile(r"^\d{4}$")
ROOT_PATHS = ("", "/")


class CatalogReadError(Exception):
    """Raised when the catalog file cannot be read or parsed as JSON."""


@dataclass(frozen=True)
class ValidationIssue:
    """One catalog-policy violation, located by its JSON path.

    Diagnostics deliberately contain no catalog field values: only the path and
    the violated rule. That keeps validator output free of document text.
    """

    location: str
    rule: str

    def __str__(self) -> str:
        return "{}: {}".format(self.location, self.rule)


@dataclass(frozen=True)
class ValidationReport:
    """Result of validating one catalog document against the policy."""

    schema_version: Optional[str]
    checked_sources: int
    issues: Tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def format_issues(self) -> str:
        return "\n".join(str(issue) for issue in self.issues)


def validate_catalog(document: Any, as_of: date) -> ValidationReport:
    """Validate a parsed catalog document as of ``as_of``.

    ``as_of`` is the validation date used for expiry checks; callers make
    validation deterministic by supplying it explicitly.
    """

    return _CatalogValidator(as_of).validate(document)


def load_catalog(path: Path) -> Any:
    """Read and parse a catalog file, raising ``CatalogReadError`` on failure."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise CatalogReadError("cannot read catalog file: {}".format(error)) from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise CatalogReadError("catalog file is not valid JSON: {}".format(error)) from error


class _CatalogValidator:
    """Accumulates every policy violation instead of failing on the first one."""

    def __init__(self, as_of: date) -> None:
        self._as_of = as_of
        self._issues: List[ValidationIssue] = []

    def validate(self, document: Any) -> ValidationReport:
        if not isinstance(document, dict):
            self._fail("$", "catalog document must be a JSON object")
            return self._report(None, 0)

        self.check_keys(document, TOP_LEVEL_KEYS, TOP_LEVEL_KEYS, "$")

        schema_version = document.get("schema_version")
        if "schema_version" in document and schema_version != SCHEMA_VERSION:
            self._fail("$.schema_version", "must equal '{}'".format(SCHEMA_VERSION))

        sources = document.get("sources")
        if not isinstance(sources, list):
            if "sources" in document:
                self._fail("$.sources", "must be a JSON array of source objects")
            return self._report(_as_text(schema_version), 0)

        seen_ids: Dict[str, str] = {}
        for index, source in enumerate(sources):
            location = "$.sources[{}]".format(index)
            if not isinstance(source, dict):
                self._fail(location, "each source must be a JSON object")
                continue
            _SourceValidator(self, location, self._as_of, seen_ids).validate(source)

        return self._report(_as_text(schema_version), len(sources))

    def fail(self, location: str, rule: str) -> None:
        self._fail(location, rule)

    def check_keys(
        self,
        payload: Dict[str, Any],
        required: frozenset,
        allowed: frozenset,
        location: str,
    ) -> None:
        for key in sorted(payload):
            if key not in allowed:
                self._fail(join_path(location, key), "unknown key is not allowed")
        for key in sorted(required):
            if key not in payload:
                self._fail(join_path(location, key), "required key is missing")

    def _fail(self, location: str, rule: str) -> None:
        self._issues.append(ValidationIssue(location, rule))

    def _report(self, schema_version: Optional[str], checked_sources: int) -> ValidationReport:
        return ValidationReport(
            schema_version=schema_version,
            checked_sources=checked_sources,
            issues=tuple(self._issues),
        )


class _SourceValidator:
    """Validates one source entry using only values already present."""

    def __init__(
        self,
        catalog: _CatalogValidator,
        location: str,
        as_of: date,
        seen_ids: Dict[str, str],
    ) -> None:
        self._catalog = catalog
        self._location = location
        self._as_of = as_of
        self._seen_ids = seen_ids

    def validate(self, source: Dict[str, Any]) -> None:
        self._catalog.check_keys(
            source,
            SOURCE_REQUIRED_KEYS,
            SOURCE_REQUIRED_KEYS | SOURCE_OPTIONAL_KEYS,
            self._location,
        )

        self._check_identifier(source)
        self._check_text(source, "title")
        issuer = self._check_issuer(source)
        self._check_urls(source, issuer)
        self._check_digest(source)
        self._check_review(source)
        self._check_lifecycle(source)
        self._check_retrieval_metadata(source)
        self._check_dates(source)

    def _fail(self, key: str, rule: str) -> None:
        self._catalog.fail(join_path(self._location, key), rule)

    def _check_identifier(self, source: Dict[str, Any]) -> None:
        if "id" not in source:
            return
        value = source["id"]
        if not is_non_blank_string(value):
            self._fail("id", "must be a non-blank string")
            return
        if not ID_PATTERN.match(value):
            self._fail("id", "must be a stable lowercase slug such as 'rd_1048_2022'")
            return
        if value in self._seen_ids:
            self._fail("id", "duplicate id; already used by {}".format(self._seen_ids[value]))
            return
        self._seen_ids[value] = self._location

    def _check_text(self, source: Dict[str, Any], key: str) -> None:
        if key in source and not is_non_blank_string(source[key]):
            self._fail(key, "must be a non-blank string")

    def _check_issuer(self, source: Dict[str, Any]) -> Optional[str]:
        if "issuing_body" not in source:
            return None
        value = source["issuing_body"]
        if not is_non_blank_string(value):
            self._fail("issuing_body", "must be a non-blank string")
            return None
        if value not in ISSUER_ALLOWED_HOSTS:
            self._fail(
                "issuing_body",
                "must be an approved issuer: {}".format(", ".join(sorted(ISSUER_ALLOWED_HOSTS))),
            )
            return None
        return value

    def _check_urls(self, source: Dict[str, Any], issuer: Optional[str]) -> None:
        self._check_url(source, "original_url", issuer)
        if "consolidated_url" not in source:
            return
        self._check_url(source, "consolidated_url", issuer)
        if (
            is_non_blank_string(source.get("consolidated_url"))
            and source.get("consolidated_url") == source.get("original_url")
        ):
            self._fail(
                "consolidated_url",
                "must not replace original_url; keep the original publication link",
            )

    def _check_url(self, source: Dict[str, Any], key: str, issuer: Optional[str]) -> None:
        if key not in source:
            return
        value = source[key]
        if not is_non_blank_string(value):
            self._fail(key, "must be a non-blank HTTPS URL")
            return
        try:
            parts = urlsplit(value)
            host = parts.hostname
            credentials = parts.username or parts.password
        except ValueError:
            self._fail(key, "must be a valid URL")
            return
        if parts.scheme != "https":
            self._fail(key, "must use https://")
            return
        if credentials:
            self._fail(key, "must not embed credentials")
            return
        if not host:
            self._fail(key, "must include a host")
            return
        if (parts.path or "") in ROOT_PATHS:
            self._fail(key, "must link to a specific document, not a site root")
            return
        if host not in APPROVED_HOSTS:
            self._fail(key, "host is not on the approved official-domain allowlist")
            return
        if issuer is not None and host not in ISSUER_ALLOWED_HOSTS[issuer]:
            self._fail(key, "host does not belong to the declared issuing_body")

    def _check_digest(self, source: Dict[str, Any]) -> None:
        if "content_sha256" not in source:
            return
        value = source["content_sha256"]
        if not isinstance(value, str) or not SHA256_PATTERN.match(value):
            self._fail("content_sha256", "must be a lowercase 64-character SHA-256 hex digest")

    def _check_review(self, source: Dict[str, Any]) -> None:
        if "review_status" in source and source["review_status"] not in REVIEW_STATUSES:
            self._fail(
                "review_status",
                "must be 'approved'; only human-approved documents enter the corpus",
            )
        self._check_text(source, "reviewed_by")

    def _check_lifecycle(self, source: Dict[str, Any]) -> None:
        if "lifecycle_status" in source and source["lifecycle_status"] not in LIFECYCLE_STATUSES:
            self._fail("lifecycle_status", "must be 'current'; non-current documents are ineligible")

    def _check_retrieval_metadata(self, source: Dict[str, Any]) -> None:
        if "campaign" in source and (
            not isinstance(source["campaign"], str) or not CAMPAIGN_PATTERN.fullmatch(source["campaign"])
        ):
            self._fail("campaign", "must be a four-digit year")
        if "campaign" in source and "valid_until" not in source:
            self._fail("valid_until", "is required for campaign-specific sources")
        if "critical" in source and not isinstance(source["critical"], bool):
            self._fail("critical", "must be true or false")
        self._check_applicability(source)

    def _check_applicability(self, source: Dict[str, Any]) -> None:
        if "applicability" not in source:
            return
        value = source["applicability"]
        location = join_path(self._location, "applicability")
        if not isinstance(value, dict):
            self._catalog.fail(location, "must be an object")
            return
        self._catalog.check_keys(value, frozenset(), APPLICABILITY_KEYS, location)
        if not value:
            self._catalog.fail(
                location, "must not be empty; leave applicability absent when nothing is known"
            )
            return
        if "crop" in value and not is_non_blank_string(value["crop"]):
            self._catalog.fail(join_path(location, "crop"), "must be a non-blank string")
        if "water_regime" in value and value["water_regime"] not in WATER_REGIMES:
            self._catalog.fail(
                join_path(location, "water_regime"),
                "must be one of: {}; leave unknown absent".format(", ".join(WATER_REGIMES)),
            )
        if "production_method" in value and value["production_method"] not in PRODUCTION_METHODS:
            self._catalog.fail(
                join_path(location, "production_method"),
                "must be one of: {}; leave unknown absent".format(", ".join(PRODUCTION_METHODS)),
            )

    def _check_dates(self, source: Dict[str, Any]) -> None:
        published_on = self._check_date(source, "published_on")
        downloaded_on = self._check_date(source, "downloaded_on")
        verified_on = self._check_date(source, "verified_on")
        reviewed_on = self._check_date(source, "reviewed_on")
        valid_until = self._check_date(source, "valid_until")

        if published_on and downloaded_on and published_on > downloaded_on:
            self._fail("published_on", "must be on or before downloaded_on")
        if downloaded_on and verified_on and downloaded_on > verified_on:
            self._fail("verified_on", "must be on or after downloaded_on")
        if downloaded_on and reviewed_on and reviewed_on < downloaded_on:
            self._fail("reviewed_on", "must be on or after downloaded_on")
        if valid_until and valid_until < self._as_of:
            self._fail(
                "valid_until",
                "is before the validation date; the document is expired and ineligible",
            )

    def _check_date(self, source: Dict[str, Any], key: str) -> Optional[date]:
        if key not in source:
            return None
        value = source[key]
        if not isinstance(value, str) or not ISO_DATE_PATTERN.match(value):
            self._fail(key, "must be an ISO date formatted as YYYY-MM-DD")
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            self._fail(key, "must be a real calendar date in YYYY-MM-DD format")
            return None


def join_path(location: str, key: str) -> str:
    """Return a JSON path such as ``$.sources[0].id``."""

    return "{}.{}".format(location, key)


def is_non_blank_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _as_text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() != "" else None
