"""Build and verify immutable GitHub-backed review decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.archive.capture import load_json, write_json

SPEC_SCHEMA = "computerecord.review-decision-spec.v1"
DECISION_SCHEMA = "computerecord.review-decision.v1"
REVIEW_SCHEMA = "computerecord.claim-review-manifest.v1"
SEEDS_SCHEMA = "computerecord.entity-seed-candidates.v1"
CLASSIFICATION = "immutable_review_decision"
DECISION = "approved_for_entity_seed_staging"
POLICY = {
    "database_writes_allowed": False,
    "fact_creation_allowed": False,
    "promotion_allowed": False,
    "staging_allowed": True,
}
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError("decision timestamp must be ISO 8601") from error
    if parsed.tzinfo is None or not value.endswith("Z"):
        raise ValueError("decision timestamp must be UTC")


def _validate_inputs(
    spec: dict[str, Any],
    review: dict[str, Any],
    seeds: dict[str, Any],
) -> None:
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("unknown review decision specification schema")
    if review.get("schema") != REVIEW_SCHEMA:
        raise ValueError("unknown claim review manifest schema")
    if seeds.get("schema") != SEEDS_SCHEMA:
        raise ValueError("unknown entity seeds schema")
    if review.get("review_state") != "proposed":
        raise ValueError("decision input must be a proposed review manifest")
    if review.get("classification") != "proposed_review":
        raise ValueError("decision input review classification drift")
    if review.get("policy") != {
        "database_writes": False,
        "facts_created": False,
        "merge_requests_review_decision": True,
        "promotion_allowed": False,
        "source_assertions_only": True,
    }:
        raise ValueError("review manifest escaped its review boundary")
    if seeds.get("classification") != "staging_entity_seed_candidates":
        raise ValueError("entity seed classification drift")
    if seeds.get("policy") != {
        "database_writes_allowed": False,
        "fact_creation_allowed": False,
        "promotion_allowed": False,
    }:
        raise ValueError("entity seeds escaped staging")
    if review["outputs"]["entity_seeds_sha256"] != sha256_json(seeds):
        raise ValueError("review manifest does not pin the entity seeds")
    expected_input = spec.get("input") or {}
    if expected_input != {
        "review_manifest_sha256": sha256_json(review),
        "entity_seeds_sha256": sha256_json(seeds),
    }:
        raise ValueError("decision inputs do not match their pinned hashes")
    if spec.get("review_id") != review.get("review_id"):
        raise ValueError("decision specification review id mismatch")
    if spec.get("decision") != DECISION:
        raise ValueError("unsupported review decision")
    if spec.get("policy") != POLICY:
        raise ValueError("decision escaped entity-seed staging")

    approved = spec.get("approved_entity_candidate_ids") or []
    expected_approved = sorted(
        candidate["candidate_id"] for candidate in seeds.get("candidates") or []
    )
    if approved != expected_approved:
        raise ValueError("decision must approve the exact entity candidate set")
    blocked = spec.get("blocked_normalization_claim_ids") or []
    expected_blocked = sorted(
        item["claim_id"] for item in seeds.get("blocked_normalizations") or []
    )
    if blocked != expected_blocked:
        raise ValueError("decision must preserve every blocked normalization")
    if set(approved) & set(blocked):
        raise ValueError("a blocked claim cannot be approved as an entity seed")

    provenance = spec.get("github_review") or {}
    if provenance.get("repository") != "ykorets/computerecord":
        raise ValueError("review decision repository mismatch")
    pull_number = provenance.get("pull_request_number")
    expected_url = (
        f"https://github.com/ykorets/computerecord/pull/{pull_number}"
    )
    if (
        not isinstance(pull_number, int)
        or pull_number < 1
        or provenance.get("pull_request_url") != expected_url
    ):
        raise ValueError("review decision pull request provenance is invalid")
    for field in ("approved_head_commit", "merge_commit"):
        if not COMMIT_PATTERN.fullmatch(provenance.get(field) or ""):
            raise ValueError(f"review decision {field} is invalid")
    if provenance["approved_head_commit"] == provenance["merge_commit"]:
        raise ValueError("review head and merge commits must be distinct")
    _validate_timestamp(provenance.get("merged_at"))
    reviewer = spec.get("reviewer") or {}
    if (
        reviewer.get("github_login") != provenance.get("merged_by")
        or not reviewer.get("display_name")
        or not reviewer.get("github_node_id")
    ):
        raise ValueError("reviewer identity does not match GitHub merge")


def build_decision(
    spec: dict[str, Any],
    review: dict[str, Any],
    seeds: dict[str, Any],
) -> dict[str, Any]:
    _validate_inputs(spec, review, seeds)
    provenance = spec["github_review"]
    decision_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            (
                "https://computerecord.com/id/review-decision/"
                f"{review['review_id']}/{provenance['merge_commit']}"
            ),
        )
    )
    return {
        "schema": DECISION_SCHEMA,
        "classification": CLASSIFICATION,
        "decision_id": decision_id,
        "decision": DECISION,
        "decided_at": provenance["merged_at"],
        "reviewer": spec["reviewer"],
        "github_review": provenance,
        "input": {
            "review_id": review["review_id"],
            **spec["input"],
        },
        "approved_entity_candidate_ids": spec[
            "approved_entity_candidate_ids"
        ],
        "blocked_normalization_claim_ids": spec[
            "blocked_normalization_claim_ids"
        ],
        "rationale": spec["rationale"],
        "policy": POLICY,
    }


def verify_decision(
    decision: dict[str, Any],
    spec: dict[str, Any],
    review: dict[str, Any],
    seeds: dict[str, Any],
) -> dict[str, int]:
    expected = build_decision(spec, review, seeds)
    if decision != expected:
        raise ValueError("review decision does not reproduce from pinned inputs")
    return {
        "approved_entity_candidates": len(
            decision["approved_entity_candidate_ids"]
        ),
        "blocked_normalizations": len(
            decision["blocked_normalization_claim_ids"]
        ),
    }


def build_command(args: argparse.Namespace) -> None:
    decision = build_decision(
        load_json(Path(args.spec)),
        load_json(Path(args.review_manifest)),
        load_json(Path(args.entity_seeds)),
    )
    write_json(Path(args.output), decision)


def verify_command(args: argparse.Namespace) -> None:
    result = verify_decision(
        load_json(Path(args.decision)),
        load_json(Path(args.spec)),
        load_json(Path(args.review_manifest)),
        load_json(Path(args.entity_seeds)),
    )
    print(
        "review decision verification: "
        f"{result['approved_entity_candidates']} entity candidates approved "
        "for staging, "
        f"{result['blocked_normalizations']} normalizations remain blocked"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("--spec", required=True)
        child.add_argument("--review-manifest", required=True)
        child.add_argument("--entity-seeds", required=True)
        if command == "build":
            child.add_argument("--output", required=True)
            child.set_defaults(func=build_command)
        else:
            child.add_argument("--decision", required=True)
            child.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
