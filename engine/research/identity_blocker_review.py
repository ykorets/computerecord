"""Build and verify a review-only assessment of identity staging blockers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from engine.archive.capture import load_json, write_json

SPEC_SCHEMA = "computerecord.identity-blocker-review-spec.v1"
REVIEW_SCHEMA = "computerecord.identity-blocker-review.v1"
PLAN_SCHEMA = "computerecord.identity-staging-plan.v1"
RECEIPT_SCHEMA = "computerecord.identity-staging-production-receipt.v1"
CLASSIFICATION = "proposed_identity_blocker_data_review"
ALLOWED_ROUTES = {
    "controlled_geography_normalization",
    "additional_primary_evidence",
    "schema_vocabulary_decision",
}
POLICY = {
    "canonical_writes_allowed": False,
    "database_writes_allowed": False,
    "fact_creation_allowed": False,
    "promotion_allowed": False,
    "review_decision_required": True,
}


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _blocked_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (row for row in plan["rows"] if row["canonical_blockers"]),
        key=lambda row: row["candidate_id"],
    )


def _validate_receipt(
    receipt: dict[str, Any],
    plan: dict[str, Any],
    load_manifest: dict[str, Any],
    stage_sql_sha256: str,
) -> None:
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unknown production receipt schema")
    if receipt.get("classification") != "production_staging_execution_receipt":
        raise ValueError("production receipt classification drift")
    if receipt.get("batch_id") != plan.get("batch_id"):
        raise ValueError("production receipt batch mismatch")
    if receipt.get("plan_sha256") != sha256_json(plan):
        raise ValueError("production receipt plan mismatch")
    if receipt.get("stage_sql_sha256") != stage_sql_sha256:
        raise ValueError("production receipt SQL mismatch")
    if receipt.get("target_project_ref") != load_manifest.get(
        "target_project_ref"
    ):
        raise ValueError("production receipt target mismatch")
    audit = receipt.get("post_execution_audit") or {}
    expected = plan["summary"]
    if audit != {
        "aliases": sum(len(row.get("aliases") or []) for row in plan["rows"]),
        "authenticated_select": False,
        "blocked": expected["canonical_blocked"],
        "candidates": expected["identity_candidates"],
        "canonical_entities": 0,
        "dependencies": sum(
            len(row.get("dependency_candidate_ids") or [])
            for row in plan["rows"]
        ),
        "facts": 0,
        "inputs": len(plan["inputs"]),
        "ready": expected["canonical_ready"],
        "state": "sealed",
        "support": sum(
            len(row.get("support_claim_ids") or []) for row in plan["rows"]
        ),
        "anon_select": False,
    }:
        raise ValueError("production receipt audit does not match sealed plan")


def build_review(
    spec: dict[str, Any],
    plan: dict[str, Any],
    load_manifest: dict[str, Any],
    receipt: dict[str, Any],
    stage_sql_sha256: str,
) -> dict[str, Any]:
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("unknown blocker review specification schema")
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unknown identity staging plan schema")
    if plan.get("classification") != "sealed_identity_staging_plan":
        raise ValueError("identity staging plan classification drift")
    if any(plan["policy"].get(key) for key in (
        "canonical_writes_allowed", "fact_creation_allowed", "promotion_allowed"
    )):
        raise ValueError("identity staging plan escaped review boundary")
    if (load_manifest.get("plan") or {}).get("sha256") != sha256_json(plan):
        raise ValueError("load manifest does not pin the staging plan")
    _validate_receipt(receipt, plan, load_manifest, stage_sql_sha256)

    expected_inputs = {
        "load_manifest_sha256": sha256_json(load_manifest),
        "plan_sha256": sha256_json(plan),
        "production_receipt_sha256": sha256_json(receipt),
        "stage_sql_sha256": stage_sql_sha256,
    }
    if spec.get("input") != expected_inputs:
        raise ValueError("blocker review inputs do not match pinned artifacts")
    if spec.get("policy") != POLICY:
        raise ValueError("blocker review escaped review-only policy")

    blocked = _blocked_rows(plan)
    assessments = spec.get("assessments") or []
    if [item.get("candidate_id") for item in assessments] != [
        row["candidate_id"] for row in blocked
    ]:
        raise ValueError("review must assess the exact blocked candidate set")

    output = []
    for row, assessment in zip(blocked, assessments, strict=True):
        if assessment.get("candidate_key") != row["candidate_key"]:
            raise ValueError("review candidate key mismatch")
        if assessment.get("current_blockers") != row["canonical_blockers"]:
            raise ValueError("review blocker mismatch")
        if assessment.get("resolution_route") not in ALLOWED_ROUTES:
            raise ValueError("unsupported blocker resolution route")
        evidence_ids = assessment.get("support_claim_ids") or []
        if not evidence_ids or not set(evidence_ids).issubset(row["support_claim_ids"]):
            raise ValueError("review evidence must use staged support claims")
        proposed_patch = assessment.get("proposed_attribute_patch") or {}
        if set(proposed_patch) & set(row["proposed_attributes"]):
            raise ValueError("review patch may only fill absent attributes")
        output.append({
            "candidate_id": row["candidate_id"],
            "candidate_key": row["candidate_key"],
            "canonical_name": row["canonical_name"],
            "entity_type": row["entity_type"],
            "current_attributes": row["proposed_attributes"],
            **assessment,
        })

    routes = {route: 0 for route in sorted(ALLOWED_ROUTES)}
    for assessment in output:
        routes[assessment["resolution_route"]] += 1
    return {
        "schema": REVIEW_SCHEMA,
        "classification": CLASSIFICATION,
        "review_id": spec["review_id"],
        "input": {
            "batch_id": plan["batch_id"],
            **expected_inputs,
        },
        "assessments": output,
        "summary": {
            "blocked_candidates_reviewed": len(output),
            "resolution_routes": routes,
            "blockers_cleared": 0,
        },
        "policy": POLICY,
    }


def _load_inputs(args: argparse.Namespace) -> tuple[Any, ...]:
    return (
        load_json(Path(args.spec)),
        load_json(Path(args.plan)),
        load_json(Path(args.load_manifest)),
        load_json(Path(args.production_receipt)),
        hashlib.sha256(Path(args.stage_sql).read_bytes()).hexdigest(),
    )


def build_command(args: argparse.Namespace) -> None:
    write_json(Path(args.output), build_review(*_load_inputs(args)))


def verify_command(args: argparse.Namespace) -> None:
    expected = build_review(*_load_inputs(args))
    actual = load_json(Path(args.review))
    if actual != expected:
        raise ValueError("identity blocker review does not reproduce")
    print(
        "identity blocker review verification: "
        f"{len(actual['assessments'])} blockers assessed, 0 cleared"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("--spec", required=True)
        child.add_argument("--plan", required=True)
        child.add_argument("--load-manifest", required=True)
        child.add_argument("--production-receipt", required=True)
        child.add_argument("--stage-sql", required=True)
        if command == "build":
            child.add_argument("--output", required=True)
            child.set_defaults(func=build_command)
        else:
            child.add_argument("--review", required=True)
            child.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
