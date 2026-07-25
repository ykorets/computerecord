"""Verify the sealed primary-source watcher registry."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA = "computerecord.source-registry.v1"
CLASSIFICATION = "operational_primary_source_registry"
SOURCE_TYPE = "sec_company_submissions"
ADAPTER = "sec_submissions_v1"
POLICY = {
    "competitor_sources_allowed": False,
    "discovery_creates_facts": False,
    "filing_document_capture_required": True,
    "registry_is_public": True,
}
CIK_PATTERN = re.compile(r"\d{10}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _utc_timestamp(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")


def verify_registry(
    registry: dict[str, Any], *, expected_sources: int | None = None
) -> dict[str, int]:
    if registry.get("schema") != SCHEMA:
        raise ValueError("unknown source registry schema")
    if registry.get("classification") != CLASSIFICATION:
        raise ValueError("source registry classification drift")
    if registry.get("policy") != POLICY:
        raise ValueError("source registry escaped its discovery-only boundary")
    _utc_timestamp(registry.get("sealed_at"), "sealed_at")

    authority = registry.get("authority") or {}
    if authority.get("publisher") != "U.S. Securities and Exchange Commission":
        raise ValueError("source registry authority publisher drift")
    if authority.get("documentation_url") != (
        "https://www.sec.gov/search-filings/"
        "edgar-application-programming-interfaces"
    ):
        raise ValueError("source registry authority documentation drift")
    if authority.get("company_index_url") != (
        "https://www.sec.gov/files/company_tickers_exchange.json"
    ):
        raise ValueError("source registry company index drift")
    if not SHA256_PATTERN.fullmatch(
        authority.get("company_index_sha256") or ""
    ):
        raise ValueError("source registry company index hash is invalid")
    _utc_timestamp(authority.get("company_index_retrieved_at"), "retrieved_at")

    sources = registry.get("sources") or []
    if expected_sources is not None and len(sources) != expected_sources:
        raise ValueError(
            f"expected {expected_sources} sources, found {len(sources)}"
        )
    if not sources:
        raise ValueError("source registry cannot be empty")

    ids: set[str] = set()
    ciks: set[str] = set()
    urls: set[str] = set()
    for source in sources:
        cik = source.get("publisher", {}).get("cik") or ""
        expected_id = f"sec-submissions:cik-{cik}"
        expected_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        if not CIK_PATTERN.fullmatch(cik):
            raise ValueError("SEC source CIK must be ten digits")
        if source.get("source_id") != expected_id:
            raise ValueError("SEC source id does not match its CIK")
        if source.get("url") != expected_url:
            raise ValueError("SEC submissions URL does not match its CIK")
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or parsed.hostname != "data.sec.gov":
            raise ValueError("SEC source URL must use official HTTPS API")
        if source.get("source_type") != SOURCE_TYPE:
            raise ValueError("SEC source type drift")
        if source.get("adapter") != ADAPTER:
            raise ValueError("SEC source adapter drift")
        if source.get("jurisdiction") != "US-federal":
            raise ValueError("SEC source jurisdiction drift")
        if source.get("tier") != 1:
            raise ValueError("SEC submissions must remain Tier 1")
        if source.get("schedule") != {
            "interval_seconds": 600,
            "jitter_seconds": 60,
        }:
            raise ValueError("SEC source schedule drift")
        if source.get("maximum_staleness_seconds") != 900:
            raise ValueError("SEC source freshness SLO drift")
        if (
            not isinstance(source.get("expected_change_interval_seconds"), int)
            or source["expected_change_interval_seconds"] < 3600
        ):
            raise ValueError("source expected change interval is invalid")
        coverage = source.get("coverage_scope") or {}
        if coverage.get("candidate_type") != "filing":
            raise ValueError("SEC source coverage must discover filings")
        if not coverage.get("forms"):
            raise ValueError("SEC source coverage needs at least one form")
        publisher = source.get("publisher") or {}
        if not publisher.get("name") or not publisher.get("tickers"):
            raise ValueError("SEC source publisher identity is incomplete")
        if source["source_id"] in ids or cik in ciks or source["url"] in urls:
            raise ValueError("source registry contains a duplicate watcher")
        ids.add(source["source_id"])
        ciks.add(cik)
        urls.add(source["url"])

    if [source["source_id"] for source in sources] != sorted(ids):
        raise ValueError("source registry must be sorted by source id")
    return {
        "sources": len(sources),
        "tier_1_sources": sum(source["tier"] == 1 for source in sources),
        "publishers": len(ciks),
    }


def verify_command(args: argparse.Namespace) -> None:
    result = verify_registry(
        load_json(Path(args.registry)),
        expected_sources=args.expected_sources,
    )
    print(
        "source registry verification: "
        f"{result['sources']} sources, "
        f"{result['tier_1_sources']} Tier 1, "
        f"{result['publishers']} publishers"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verify", nargs="?")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--expected-sources", type=int)
    parser.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
