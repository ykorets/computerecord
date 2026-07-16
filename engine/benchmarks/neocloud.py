"""Capture and compare the Neocloud Buildout Registry as a coverage benchmark.

This module never promotes competitor assertions into Compute Record facts.
It stores target identity, discovery leads, and field-presence metadata under
an explicit benchmark_only classification. Raw third-party payloads are
hashed but are not redistributed by this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

LANDING_URL = "https://neocloudgroup.com/buildout-registry"
CLASSIFICATION = "benchmark_only"
CAPTURE_SCHEMA = "computerecord.coverage-benchmark-targets.v1"
RESOLUTION_SCHEMA = "computerecord.coverage-benchmark-resolution.v1"
ALGORITHM_VERSION = "m3-entity-resolution-v1"
MAX_LANDING_BYTES = 5 * 1024 * 1024
MAX_REGISTRY_BYTES = 20 * 1024 * 1024
FORBIDDEN_TARGET_FIELDS = {
    "gross_current_mw",
    "gross_planned_mw",
    "critical_current_mw",
    "critical_planned_mw",
    "site_total_mw",
}

PUBLIC_COLUMNS = [
    "id",
    "name",
    "operator",
    "city",
    "county",
    "state",
    "region",
    "lat",
    "lng",
    "coords_approximate",
    "gross_current_mw",
    "gross_planned_mw",
    "critical_current_mw",
    "critical_planned_mw",
    "site_total_mw",
    "capacity_note",
    "stage",
    "buildings_energized",
    "buildings_building",
    "buildings_planned",
    "participants(layer,name,role,confidence)",
    "site_dates(key,value,confidence)",
    "sources(id,label,url,type)",
]

REQUIRED_COVERAGE_FIELDS = [
    "identity",
    "location",
    "operator",
    "capacity",
    "status",
    "milestones",
    "source_evidence",
    "campus_phase",
    "compute_relationships",
]

STOPWORDS = {
    "a",
    "ai",
    "and",
    "campus",
    "campuses",
    "center",
    "centers",
    "data",
    "datacenter",
    "datacenters",
    "factory",
    "project",
    "the",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> str:
    payload = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def _lower_headers(headers: dict[str, str] | None) -> dict[str, str]:
    return {key.lower(): value for key, value in (headers or {}).items()}


def _read_curl_headers(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    headers: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("HTTP/"):
            headers = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def _read_limited(response: Any, limit: int) -> bytes:
    payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError(f"response exceeds {limit} bytes")
    return payload


def _validate_supabase_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname.endswith(".supabase.co")
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("registry endpoint must be an HTTPS supabase.co origin")
    return value.rstrip("/")


def _extract_public_endpoint(landing: str) -> tuple[str, str]:
    url_match = re.search(r"const SUPA_URL = '([^']+)'", landing)
    key_match = re.search(r"const REGISTRY_KEY = '([^']+)'", landing)
    if not url_match or not key_match:
        raise ValueError("public registry endpoint was not found in landing page")
    return _validate_supabase_url(url_match.group(1)), key_match.group(1)


def fetch_live() -> tuple[bytes, bytes, dict[str, str], dict[str, str], str]:
    landing_request = urllib.request.Request(
        LANDING_URL,
        headers={"User-Agent": "ComputeRecordBenchmark/1.0"},
    )
    with urllib.request.urlopen(landing_request, timeout=30) as response:
        landing_bytes = _read_limited(response, MAX_LANDING_BYTES)
        landing_headers = dict(response.headers.items())

    supabase_url, publishable_key = _extract_public_endpoint(
        landing_bytes.decode("utf-8")
    )
    query = urllib.parse.urlencode(
        {"select": ",".join(PUBLIC_COLUMNS), "order": "name.asc"}
    )
    api_url = f"{supabase_url}/rest/v1/sites?{query}"
    sites_request = urllib.request.Request(
        api_url,
        headers={
            "apikey": publishable_key,
            "Authorization": f"Bearer {publishable_key}",
            "User-Agent": "ComputeRecordBenchmark/1.0",
        },
    )
    with urllib.request.urlopen(sites_request, timeout=30) as response:
        sites_bytes = _read_limited(response, MAX_REGISTRY_BYTES)
        sites_headers = dict(response.headers.items())
    return landing_bytes, sites_bytes, landing_headers, sites_headers, api_url


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _target_from_row(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("every registry row must be an object")
    for field in ("id", "name", "state"):
        if not row.get(field):
            raise ValueError(f"registry row is missing {field}")
    source_id = str(row["id"])
    sources = []
    for source in row.get("sources") or []:
        url = source.get("url")
        if not url:
            continue
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            continue
        sources.append(
            {
                "classification": "benchmark_discovery_lead",
                "label": source.get("label"),
                "reported_type": source.get("type"),
                "url": url,
            }
        )
    sources.sort(key=lambda item: (item["url"], item.get("label") or ""))

    capacity_fields = [
        "gross_current_mw",
        "gross_planned_mw",
        "critical_current_mw",
        "critical_planned_mw",
        "site_total_mw",
    ]
    building_fields = [
        "buildings_energized",
        "buildings_building",
        "buildings_planned",
    ]
    county = row.get("county")
    if isinstance(county, str):
        counties = [county]
    else:
        counties = sorted(str(value) for value in (county or []))

    return {
        "benchmark_id": f"neocloud-buildout-registry:{source_id}",
        "classification": CLASSIFICATION,
        "identity": {
            "name": row.get("name"),
            "operator": row.get("operator"),
        },
        "public_url": f"{LANDING_URL}?site={urllib.parse.quote(source_id, safe='')}",
        "reported_stage": row.get("stage"),
        "source_field_presence": {
            "building_counts": any(row.get(field) is not None for field in building_fields),
            "capacity_disclosed": any(
                _positive_number(row.get(field)) for field in capacity_fields
            ),
            "coordinates": row.get("lat") is not None and row.get("lng") is not None,
            "dates": bool(row.get("site_dates")),
            "participants": bool(row.get("participants")),
            "source_leads": bool(sources),
        },
        "source_leads": sources,
        "source_location": {
            "city": row.get("city"),
            "counties": counties,
            "state": row.get("state"),
        },
        "source_record_id": source_id,
    }


def build_capture(
    landing_bytes: bytes,
    sites_bytes: bytes,
    *,
    captured_at: str,
    landing_headers: dict[str, str] | None = None,
    sites_headers: dict[str, str] | None = None,
    api_url: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = json.loads(sites_bytes)
    if not isinstance(rows, list):
        raise ValueError("registry response must be a JSON array")
    targets = sorted(
        (_target_from_row(row) for row in rows),
        key=lambda target: target["source_record_id"],
    )
    source_ids = [target["source_record_id"] for target in targets]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("registry response contains duplicate site ids")
    if any(target["classification"] != CLASSIFICATION for target in targets):
        raise ValueError("benchmark classification must be explicit")

    landing_text = landing_bytes.decode("utf-8", errors="replace")
    landing_headers = _lower_headers(landing_headers)
    sites_headers = _lower_headers(sites_headers)
    canonical_match = re.search(
        r'<link rel="canonical" href="([^"]+)"', landing_text
    )
    target_document = {
        "schema": CAPTURE_SCHEMA,
        "classification": CLASSIFICATION,
        "source": {
            "name": "Neocloud Group Buildout Registry",
            "url": LANDING_URL,
        },
        "targets": targets,
    }
    manifest = {
        "schema": "computerecord.coverage-benchmark-capture.v1",
        "classification": CLASSIFICATION,
        "captured_at": captured_at,
        "landing_page": {
            "requested_url": LANDING_URL,
            "canonical_url": (
                canonical_match.group(1) if canonical_match else LANDING_URL
            ),
            "http_date": landing_headers.get("date"),
            "sha256": sha256_bytes(landing_bytes),
        },
        "registry_response": {
            "content_range": sites_headers.get("content-range"),
            "http_date": sites_headers.get("date"),
            "request_url": api_url,
            "row_count": len(targets),
            "sha256": sha256_bytes(sites_bytes),
        },
        "rights": {
            "raw_payloads_preserved_in_repository": False,
            "repository_copy": (
                "Normalized factual target identities, field presence, and "
                "discovery leads only."
            ),
        },
    }
    return target_document, manifest


def normalize_text(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.findall(r"[a-z0-9]+", ascii_text)
    return " ".join(token for token in tokens if token not in STOPWORDS)


def _tokens(value: Any) -> set[str]:
    return set(normalize_text(value).split())


def text_similarity(left: Any, right: Any) -> tuple[float, list[str]]:
    left_normalized = normalize_text(left)
    right_normalized = normalize_text(right)
    if not left_normalized or not right_normalized:
        return 0.0, []
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    shared = sorted(left_tokens & right_tokens)
    union = left_tokens | right_tokens
    jaccard = len(shared) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return round((0.65 * sequence) + (0.35 * jaccard), 6), shared


def _operator_similarity(target: dict[str, Any], facility: dict[str, Any]) -> float:
    target_tokens = _tokens(target["identity"].get("operator"))
    facility_tokens = _tokens(
        " ".join(
            [
                str(facility.get("developer") or ""),
                str(facility.get("offtaker") or ""),
            ]
        )
    )
    if not target_tokens or not facility_tokens:
        return 0.0
    return len(target_tokens & facility_tokens) / len(target_tokens)


def facility_candidates(
    target: dict[str, Any], facilities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates = []
    for facility in facilities:
        if facility.get("state") != target["source_location"].get("state"):
            continue
        labels = [facility.get("name"), *(facility.get("aliases") or [])]
        best_score = 0.0
        best_label = None
        best_shared: list[str] = []
        for label in labels:
            score, shared = text_similarity(target["identity"].get("name"), label)
            if score > best_score:
                best_score, best_label, best_shared = score, label, shared
        operator_score = _operator_similarity(target, facility)
        score = round((0.82 * best_score) + (0.18 * operator_score), 6)
        if score < 0.45:
            continue
        candidates.append(
            {
                "btw_facility_slug": facility["slug"],
                "matched_label": best_label,
                "operator_score": round(operator_score, 6),
                "score": score,
                "shared_name_tokens": best_shared,
            }
        )
    return sorted(candidates, key=lambda item: (-item["score"], item["btw_facility_slug"]))


def announcement_candidates(
    target: dict[str, Any], announcements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    target_text = " ".join(
        [
            str(target["identity"].get("name") or ""),
            str(target["identity"].get("operator") or ""),
            str(target["source_location"].get("city") or ""),
        ]
    )
    candidates = []
    for announcement in announcements:
        if announcement.get("state") != target["source_location"].get("state"):
            continue
        candidate_text = " ".join(
            [
                str(announcement.get("name") or ""),
                str(announcement.get("county") or ""),
            ]
        )
        score, shared = text_similarity(target_text, candidate_text)
        if score < 0.38 or not shared:
            continue
        candidates.append(
            {
                "name": announcement.get("name"),
                "score": score,
                "shared_tokens": shared,
                "source_url": (announcement.get("source") or {}).get("url"),
            }
        )
    return sorted(candidates, key=lambda item: (-item["score"], item["name"] or ""))[:3]


def _facility_coverage(facility: dict[str, Any] | None) -> dict[str, bool]:
    if facility is None:
        return {field: False for field in REQUIRED_COVERAGE_FIELDS}
    return {
        "identity": True,
        "location": bool(facility.get("geo")),
        "operator": bool(facility.get("developer")),
        "capacity": bool(facility.get("unit")),
        "status": bool(facility.get("status")),
        "milestones": bool(
            facility.get("first_permit_filed") or facility.get("first_power")
        ),
        "source_evidence": bool(facility.get("sources")),
        "campus_phase": False,
        "compute_relationships": False,
    }


def resolve_targets(
    target_document: dict[str, Any],
    facilities_document: dict[str, Any],
    announcements_document: dict[str, Any],
    *,
    btw_mirror_commit: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    facilities = facilities_document.get("facilities") or []
    announcements = announcements_document.get("announcements") or []
    facilities_by_slug = {facility["slug"]: facility for facility in facilities}
    resolutions = []

    for target in target_document["targets"]:
        facility_matches = facility_candidates(target, facilities)
        top = facility_matches[0] if facility_matches else None
        runner_up = facility_matches[1] if len(facility_matches) > 1 else None
        margin = top["score"] - runner_up["score"] if top and runner_up else 1.0
        auto_resolved = bool(
            top
            and top["score"] >= 0.76
            and len(top["shared_name_tokens"]) >= 2
            and margin >= 0.12
        )
        facility = facilities_by_slug[top["btw_facility_slug"]] if auto_resolved else None
        coverage = _facility_coverage(facility)
        resolutions.append(
            {
                "benchmark_id": target["benchmark_id"],
                "classification": CLASSIFICATION,
                "resolution_state": (
                    "resolved_btw_facility" if auto_resolved else "unresolved"
                ),
                "resolved_entity": (
                    {
                        "entity_type": "btw_facility",
                        "slug": top["btw_facility_slug"],
                    }
                    if auto_resolved
                    else None
                ),
                "facility_candidates": facility_matches[:3],
                "announcement_leads": announcement_candidates(target, announcements),
                "canonical_coverage": coverage,
                "missing_fields": sorted(
                    field for field, present in coverage.items() if not present
                ),
            }
        )

    resolution_document = {
        "schema": RESOLUTION_SCHEMA,
        "classification": CLASSIFICATION,
        "algorithm_version": ALGORITHM_VERSION,
        "btw_mirror_commit": btw_mirror_commit,
        "resolutions": resolutions,
    }
    gap_report = build_gap_report(target_document, resolution_document)
    return resolution_document, gap_report


def build_gap_report(
    target_document: dict[str, Any], resolution_document: dict[str, Any]
) -> dict[str, Any]:
    target_by_id = {
        target["benchmark_id"]: target for target in target_document["targets"]
    }
    state_counts: dict[str, Counter[str]] = defaultdict(Counter)
    missing_counts: Counter[str] = Counter()
    source_class_targets: dict[str, set[str]] = defaultdict(set)
    source_class_leads: Counter[str] = Counter()
    campus_rows = []
    resolution_counts: Counter[str] = Counter()

    for resolution in resolution_document["resolutions"]:
        target = target_by_id[resolution["benchmark_id"]]
        state = target["source_location"].get("state") or "unknown"
        resolution_state = resolution["resolution_state"]
        resolution_counts[resolution_state] += 1
        state_counts[state]["targets"] += 1
        state_counts[state][resolution_state] += 1
        missing_counts.update(resolution["missing_fields"])
        for lead in target["source_leads"]:
            source_class = lead.get("reported_type") or "unclassified"
            source_class_targets[source_class].add(target["benchmark_id"])
            source_class_leads[source_class] += 1
        campus_rows.append(
            {
                "benchmark_id": target["benchmark_id"],
                "name": target["identity"].get("name"),
                "state": state,
                "resolution_state": resolution_state,
                "resolved_entity": resolution["resolved_entity"],
                "missing_fields": resolution["missing_fields"],
                "announcement_lead_count": len(resolution["announcement_leads"]),
            }
        )

    total = len(resolution_document["resolutions"])
    return {
        "schema": "computerecord.coverage-gap-report.v1",
        "classification": CLASSIFICATION,
        "algorithm_version": resolution_document["algorithm_version"],
        "btw_mirror_commit": resolution_document["btw_mirror_commit"],
        "summary": {
            "targets": total,
            "resolved_btw_facility": resolution_counts["resolved_btw_facility"],
            "unresolved": resolution_counts["unresolved"],
            "out_of_scope": resolution_counts["out_of_scope"],
        },
        "by_state": [
            {"state": state, **dict(sorted(counts.items()))}
            for state, counts in sorted(state_counts.items())
        ],
        "by_source_class": [
            {
                "source_class": source_class,
                "lead_count": source_class_leads[source_class],
                "target_count": len(target_ids),
            }
            for source_class, target_ids in sorted(source_class_targets.items())
        ],
        "by_missing_field": [
            {"field": field, "target_count": count}
            for field, count in sorted(missing_counts.items())
        ],
        "campuses": sorted(campus_rows, key=lambda row: row["benchmark_id"]),
    }


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_all_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_all_keys(child))
        return keys
    return set()


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("captured_at must include a timezone")
    return parsed


def verify_artifacts(
    artifact_dir: Path, *, expected_count: int | None = None
) -> dict[str, int]:
    manifest = _load_json(artifact_dir / "manifest.json")
    targets = _load_json(artifact_dir / "targets.json")
    resolution = _load_json(artifact_dir / "resolution.json")
    gap_report = _load_json(artifact_dir / "gap-report.json")

    for document in (manifest, targets, resolution, gap_report):
        if document.get("classification") != CLASSIFICATION:
            raise ValueError("every benchmark artifact must be benchmark_only")
    _parse_timestamp(manifest["captured_at"])

    target_payload = (artifact_dir / "targets.json").read_bytes()
    if sha256_bytes(target_payload) != manifest["normalized_targets"]["sha256"]:
        raise ValueError("targets.json hash does not match manifest")

    target_rows = targets.get("targets") or []
    if expected_count is not None and len(target_rows) != expected_count:
        raise ValueError(
            f"expected {expected_count} benchmark targets, found {len(target_rows)}"
        )
    if manifest["normalized_targets"]["row_count"] != len(target_rows):
        raise ValueError("target count does not match manifest")
    if manifest["registry_response"]["row_count"] != len(target_rows):
        raise ValueError("target count does not match captured response")

    target_ids = [target["benchmark_id"] for target in target_rows]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("benchmark target ids must be unique")
    if any(target.get("classification") != CLASSIFICATION for target in target_rows):
        raise ValueError("target classification drift")
    if _all_keys(targets) & FORBIDDEN_TARGET_FIELDS:
        raise ValueError("competitor capacity values leaked into normalized targets")
    if "sb_publishable_" in target_payload.decode("utf-8"):
        raise ValueError("publishable key leaked into normalized targets")
    for target in target_rows:
        for lead in target.get("source_leads") or []:
            if lead.get("classification") != "benchmark_discovery_lead":
                raise ValueError("source lead classification drift")

    resolution_rows = resolution.get("resolutions") or []
    resolution_ids = [row["benchmark_id"] for row in resolution_rows]
    if len(resolution_ids) != len(set(resolution_ids)):
        raise ValueError("resolution ids must be unique")
    if set(resolution_ids) != set(target_ids):
        raise ValueError("every target must have exactly one resolution")
    allowed_states = {"resolved_btw_facility", "unresolved", "out_of_scope"}
    if any(row.get("resolution_state") not in allowed_states for row in resolution_rows):
        raise ValueError("unknown resolution state")
    if any(row.get("classification") != CLASSIFICATION for row in resolution_rows):
        raise ValueError("resolution classification drift")
    for row in resolution_rows:
        is_resolved = row["resolution_state"] == "resolved_btw_facility"
        if is_resolved != bool(row.get("resolved_entity")):
            raise ValueError("resolved entity does not match resolution state")

    expected_gap = build_gap_report(targets, resolution)
    if gap_report != expected_gap:
        raise ValueError("gap report is not reproducible from target resolutions")

    return {
        "targets": len(target_rows),
        "resolved": sum(
            row["resolution_state"] == "resolved_btw_facility"
            for row in resolution_rows
        ),
        "unresolved": sum(
            row["resolution_state"] == "unresolved" for row in resolution_rows
        ),
        "out_of_scope": sum(
            row["resolution_state"] == "out_of_scope" for row in resolution_rows
        ),
    }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def capture_command(args: argparse.Namespace) -> None:
    if args.landing_file and args.sites_file:
        landing_bytes = Path(args.landing_file).read_bytes()
        sites_bytes = Path(args.sites_file).read_bytes()
        landing_headers = _read_curl_headers(args.landing_headers_file)
        sites_headers = _read_curl_headers(args.sites_headers_file)
        if args.api_url:
            api_url = args.api_url
        else:
            supabase_url, _ = _extract_public_endpoint(
                landing_bytes.decode("utf-8")
            )
            query = urllib.parse.urlencode(
                {"select": ",".join(PUBLIC_COLUMNS), "order": "name.asc"}
            )
            api_url = f"{supabase_url}/rest/v1/sites?{query}"
    elif not args.landing_file and not args.sites_file:
        (
            landing_bytes,
            sites_bytes,
            landing_headers,
            sites_headers,
            api_url,
        ) = fetch_live()
    else:
        raise SystemExit("--landing-file and --sites-file must be provided together")

    captured_at = args.captured_at or datetime.now(timezone.utc).isoformat()
    target_document, manifest = build_capture(
        landing_bytes,
        sites_bytes,
        captured_at=captured_at,
        landing_headers=landing_headers,
        sites_headers=sites_headers,
        api_url=api_url,
    )
    output_dir = Path(args.output_dir)
    targets_sha = write_json(output_dir / "targets.json", target_document)
    manifest["normalized_targets"] = {
        "path": "targets.json",
        "row_count": len(target_document["targets"]),
        "sha256": targets_sha,
    }
    write_json(output_dir / "manifest.json", manifest)


def resolve_command(args: argparse.Namespace) -> None:
    target_document = _load_json(Path(args.targets))
    facilities_document = _load_json(Path(args.facilities))
    announcements_document = _load_json(Path(args.announcements))
    resolution_document, gap_report = resolve_targets(
        target_document,
        facilities_document,
        announcements_document,
        btw_mirror_commit=args.btw_mirror_commit,
    )
    output_dir = Path(args.output_dir)
    write_json(output_dir / "resolution.json", resolution_document)
    write_json(output_dir / "gap-report.json", gap_report)


def verify_command(args: argparse.Namespace) -> None:
    summary = verify_artifacts(
        Path(args.artifact_dir), expected_count=args.expected_count
    )
    print(
        "benchmark verification: "
        f"{summary['targets']} targets, "
        f"{summary['resolved']} resolved, "
        f"{summary['unresolved']} unresolved, "
        f"{summary['out_of_scope']} out of scope"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--landing-file")
    capture_parser.add_argument("--sites-file")
    capture_parser.add_argument("--landing-headers-file")
    capture_parser.add_argument("--sites-headers-file")
    capture_parser.add_argument("--captured-at")
    capture_parser.add_argument("--api-url")
    capture_parser.add_argument("--output-dir", required=True)
    capture_parser.set_defaults(func=capture_command)

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--targets", required=True)
    resolve_parser.add_argument("--facilities", required=True)
    resolve_parser.add_argument("--announcements", required=True)
    resolve_parser.add_argument("--btw-mirror-commit", required=True)
    resolve_parser.add_argument("--output-dir", required=True)
    resolve_parser.set_defaults(func=resolve_command)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--artifact-dir", required=True)
    verify_parser.add_argument("--expected-count", type=int)
    verify_parser.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
