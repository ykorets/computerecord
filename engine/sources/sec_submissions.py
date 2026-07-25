"""Convert SEC submissions API responses into discovery-only filing candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from engine.sources.health import parse_utc
from engine.sources.registry import load_json, verify_registry
from engine.sources.schedule import canonical_json_bytes

SCHEMA = "computerecord.filing-candidate-batch.v1"
CLASSIFICATION = "discovered_filing_candidates"
ADAPTER_VERSION = "sec-submissions-v1"
ACCESSION_PATTERN = re.compile(r"\d{10}-\d{2}-\d{6}")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _recent_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    recent = (document.get("filings") or {}).get("recent") or {}
    required = (
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "form",
        "primaryDocument",
        "primaryDocDescription",
        "items",
    )
    arrays = {field: recent.get(field) for field in required}
    if any(not isinstance(values, list) for values in arrays.values()):
        raise ValueError("SEC submissions response lacks required recent arrays")
    lengths = {len(values) for values in arrays.values()}
    if len(lengths) != 1:
        raise ValueError("SEC submissions recent arrays have unequal lengths")
    return [
        {field: arrays[field][index] for field in required}
        for index in range(lengths.pop())
    ]


def _filing_urls(cik: str, accession: str, primary_document: str) -> tuple[str, str]:
    if (
        not ACCESSION_PATTERN.fullmatch(accession)
        or not primary_document
        or ".." in primary_document
        or primary_document.startswith("/")
    ):
        raise ValueError("SEC filing path metadata is invalid")
    accession_compact = accession.replace("-", "")
    cik_compact = str(int(cik))
    base = (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_compact}/{accession_compact}"
    )
    document_url = f"{base}/{quote(primary_document, safe='/._-')}"
    index_url = f"{base}/{accession}-index.html"
    return document_url, index_url


def discover_candidates(
    source: dict[str, Any],
    response_payload: bytes,
    *,
    discovered_at: str,
    after_accession: str | None = None,
) -> dict[str, Any]:
    parse_utc(discovered_at, "discovered_at")
    try:
        document = json.loads(response_payload)
    except json.JSONDecodeError as error:
        raise ValueError("SEC submissions response is not valid JSON") from error
    cik = source["publisher"]["cik"]
    if str(document.get("cik") or "").zfill(10) != cik:
        raise ValueError("SEC submissions response CIK mismatch")
    rows = _recent_rows(document)
    accessions = [row["accessionNumber"] for row in rows]
    if after_accession is not None:
        if after_accession not in accessions:
            raise ValueError("SEC discovery cursor is absent from recent filings")
        rows_to_scan = rows[: accessions.index(after_accession)]
    else:
        rows_to_scan = rows
    forms = set(source["coverage_scope"]["forms"])
    candidates = []
    for row in rows_to_scan:
        form = row["form"]
        if form.removesuffix("/A") not in forms:
            continue
        accession = row["accessionNumber"]
        document_url, index_url = _filing_urls(
            cik, accession, row["primaryDocument"]
        )
        parse_utc(row["acceptanceDateTime"], "source_published_at")
        candidates.append(
            {
                "candidate_id": str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        (
                            "https://computerecord.com/id/filing-candidate/"
                            f"{source['source_id']}/{accession}"
                        ),
                    )
                ),
                "source_id": source["source_id"],
                "external_id": accession,
                "state": "discovered",
                "discovered_at": discovered_at,
                "source_published_at": row["acceptanceDateTime"],
                "filing_date": row["filingDate"],
                "report_date": row["reportDate"] or None,
                "form": form,
                "items": [
                    item.strip()
                    for item in (row["items"] or "").split(",")
                    if item.strip()
                ],
                "primary_document": row["primaryDocument"],
                "primary_document_url": document_url,
                "filing_index_url": index_url,
            }
        )
    return {
        "schema": SCHEMA,
        "classification": CLASSIFICATION,
        "adapter_version": ADAPTER_VERSION,
        "source_id": source["source_id"],
        "discovered_at": discovered_at,
        "input": {
            "response_sha256": sha256_bytes(response_payload),
            "after_accession": after_accession,
            "next_accession": accessions[0] if accessions else after_accession,
        },
        "policy": {
            "document_capture_required": True,
            "facts_created": False,
            "raw_response_committed": False,
            "source_assertions_created": False,
        },
        "candidates": candidates,
    }


def verify_candidate_batch(
    batch: dict[str, Any],
    source: dict[str, Any],
    response_payload: bytes,
    *,
    discovered_at: str,
    after_accession: str | None = None,
) -> dict[str, int]:
    expected = discover_candidates(
        source,
        response_payload,
        discovered_at=discovered_at,
        after_accession=after_accession,
    )
    if batch != expected:
        raise ValueError("SEC filing candidates do not reproduce from response")
    return {
        "candidates": len(batch["candidates"]),
        "amendments": sum(
            candidate["form"].endswith("/A")
            for candidate in batch["candidates"]
        ),
    }


def _source(registry_path: Path, source_id: str) -> dict[str, Any]:
    registry = load_json(registry_path)
    verify_registry(registry)
    matches = [
        source for source in registry["sources"] if source["source_id"] == source_id
    ]
    if len(matches) != 1:
        raise ValueError("SEC discovery source is absent from registry")
    return matches[0]


def build_command(args: argparse.Namespace) -> None:
    payload = Path(args.response).read_bytes()
    write_json(
        Path(args.output),
        discover_candidates(
            _source(Path(args.registry), args.source_id),
            payload,
            discovered_at=args.discovered_at,
            after_accession=args.after_accession,
        ),
    )


def verify_command(args: argparse.Namespace) -> None:
    result = verify_candidate_batch(
        load_json(Path(args.candidates)),
        _source(Path(args.registry), args.source_id),
        Path(args.response).read_bytes(),
        discovered_at=args.discovered_at,
        after_accession=args.after_accession,
    )
    print(
        "SEC discovery verification: "
        f"{result['candidates']} filing candidates, "
        f"{result['amendments']} amendments"
    )


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--discovered-at", required=True)
    parser.add_argument("--after-accession")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    _common_arguments(build)
    build.add_argument("--output", required=True)
    build.set_defaults(func=build_command)
    verify = subparsers.add_parser("verify")
    _common_arguments(verify)
    verify.add_argument("--candidates", required=True)
    verify.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
