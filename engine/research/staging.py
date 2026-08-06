"""Build and verify sealed identity-staging plans from approved reviews."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from engine.archive.capture import load_json, write_json
from engine.research.decision import sha256_json, verify_decision

SCHEMA = "computerecord.identity-staging-plan.v1"
CLASSIFICATION = "sealed_identity_staging_plan"
CLAIMS_SCHEMA = "computerecord.anchored-source-assertions.v1"
ALLOWED_ORGANIZATION_TYPES = {
    "operator", "developer", "tenant", "utility", "vendor", "investor",
    "government", "regulator", "other",
}
ALLOWED_GEO_PRECISIONS = {
    "country", "state", "county", "city", "parcel", "building", "exact",
}
POLICY = {
    "canonical_writes_allowed": False,
    "database_writes_allowed": False,
    "fact_creation_allowed": False,
    "promotion_allowed": False,
    "data_review_required": True,
}


def _canonical_blockers(candidate: dict[str, Any]) -> list[str]:
    attributes = candidate.get("proposed_attributes") or {}
    entity_type = candidate.get("entity_type")
    blockers: list[str] = []
    if entity_type == "organization":
        value = attributes.get("organization_type")
        if not value:
            blockers.append("missing_organization_type")
        elif value not in ALLOWED_ORGANIZATION_TYPES:
            blockers.append(f"unsupported_organization_type:{value}")
    elif entity_type == "place":
        if not attributes.get("country_code"):
            blockers.append("missing_country_code")
        precision = attributes.get("geo_precision")
        if not precision:
            blockers.append("missing_geo_precision")
        elif precision not in ALLOWED_GEO_PRECISIONS:
            blockers.append(f"unsupported_geo_precision:{precision}")
    elif entity_type == "campus":
        if not candidate.get("place_candidate_id"):
            blockers.append("missing_place_candidate_id")
        if not attributes.get("canonical_slug"):
            blockers.append("missing_canonical_slug")
    else:
        blockers.append(f"unsupported_entity_type:{entity_type}")
    return blockers


def build_staging_plan(packets: list[dict[str, Any]]) -> dict[str, Any]:
    if not packets:
        raise ValueError("identity staging requires at least one review packet")
    inputs = []
    rows = []
    seen_candidates: set[str] = set()
    for packet in sorted(packets, key=lambda item: item["packet_key"]):
        spec = packet["decision_spec"]
        review = packet["review_manifest"]
        seeds = packet["entity_seeds"]
        decision = packet["review_decision"]
        claims = packet["claims"]
        verify_decision(decision, spec, review, seeds)
        if claims.get("schema") != CLAIMS_SCHEMA or claims.get(
            "classification"
        ) != "validated_source_assertions":
            raise ValueError("staging input requires validated source assertions")
        if review["outputs"].get("claims_sha256") != sha256_json(claims):
            raise ValueError("review manifest does not pin the claims")
        claim_ids = {claim["claim_id"] for claim in claims.get("claims") or []}
        if sorted(claim_ids) != review["outputs"].get("claim_ids"):
            raise ValueError("review manifest claim set drift")
        approved = set(decision["approved_entity_candidate_ids"])
        candidates = seeds.get("candidates") or []
        if approved != {candidate["candidate_id"] for candidate in candidates}:
            raise ValueError("decision and seed candidate sets differ")
        inputs.append({
            "packet_key": packet["packet_key"],
            "review_id": review["review_id"],
            "decision_id": decision["decision_id"],
            "merge_commit": decision["github_review"]["merge_commit"],
            "claims_sha256": sha256_json(claims),
            "entity_seeds_sha256": sha256_json(seeds),
            "review_manifest_sha256": sha256_json(review),
            "review_decision_sha256": sha256_json(decision),
        })
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            if candidate_id in seen_candidates:
                raise ValueError("identity candidate appears in more than one packet")
            seen_candidates.add(candidate_id)
            support = sorted(candidate.get("support_claim_ids") or [])
            if not support or not set(support) <= claim_ids:
                raise ValueError("identity candidate support escaped validated claims")
            rows.append({
                "candidate_id": candidate_id,
                "candidate_key": candidate["candidate_key"],
                "entity_type": candidate["entity_type"],
                "canonical_name": candidate["canonical_name"],
                "proposed_attributes": candidate.get("proposed_attributes") or {},
                "aliases": sorted(candidate.get("aliases") or []),
                "dependency_candidate_ids": sorted(
                    [candidate["place_candidate_id"]]
                    if candidate.get("place_candidate_id") else []
                ),
                "support_claim_ids": support,
                "source_decision_id": decision["decision_id"],
                "canonical_blockers": _canonical_blockers(candidate),
            })
    candidate_ids = {row["candidate_id"] for row in rows}
    for row in rows:
        if not set(row["dependency_candidate_ids"]) <= candidate_ids:
            raise ValueError("identity dependency escaped the reviewed batch")
    rows.sort(key=lambda row: row["candidate_id"])
    input_hash = sha256_json(inputs)
    batch_id = str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://computerecord.com/id/identity-staging/{input_hash}",
    ))
    blocker_count = sum(len(row["canonical_blockers"]) for row in rows)
    return {
        "schema": SCHEMA,
        "classification": CLASSIFICATION,
        "batch_id": batch_id,
        "inputs": inputs,
        "rows": rows,
        "summary": {
            "review_packets": len(inputs),
            "identity_candidates": len(rows),
            "canonical_ready": sum(not row["canonical_blockers"] for row in rows),
            "canonical_blocked": sum(bool(row["canonical_blockers"]) for row in rows),
            "blocker_count": blocker_count,
        },
        "policy": dict(POLICY),
    }


def verify_staging_plan(plan: dict[str, Any], packets: list[dict[str, Any]]) -> dict[str, int]:
    expected = build_staging_plan(packets)
    if plan != expected:
        raise ValueError("identity staging plan does not reproduce from pinned reviews")
    return expected["summary"]


def _load_packet(path: Path) -> dict[str, Any]:
    return {
        "packet_key": path.name,
        "decision_spec": load_json(path / "decision-spec.json"),
        "review_manifest": load_json(path / "review-manifest.json"),
        "entity_seeds": load_json(path / "entity-seeds.json"),
        "review_decision": load_json(path / "review-decision.json"),
        "claims": load_json(path / "claims.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--packet-dir", action="append", required=True)
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    packets = [_load_packet(Path(path)) for path in args.packet_dir]
    if args.command == "build":
        write_json(Path(args.plan), build_staging_plan(packets))
    else:
        result = verify_staging_plan(load_json(Path(args.plan)), packets)
        print(
            "identity staging verification: "
            f"{result['identity_candidates']} candidates, "
            f"{result['canonical_blocked']} blocked from canonical rows"
        )


if __name__ == "__main__":
    main()
