"""Build and verify sealed identity-staging plans from approved reviews."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from engine.archive.capture import load_json, write_json
from engine.research.decision import sha256_json, verify_decision

SCHEMA = "computerecord.identity-staging-plan.v1"
CLASSIFICATION = "sealed_identity_staging_plan"
LOAD_SCHEMA = "computerecord.identity-staging-load.v1"
LOAD_CLASSIFICATION = "identity_staging_load_request"
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
LOAD_POLICY = {
    "canonical_writes_allowed": False,
    "database_writes_allowed": True,
    "fact_creation_allowed": False,
    "merge_to_main_required": True,
    "promotion_allowed": False,
    "staging_tables_only": True,
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


def build_load_manifest(
    plan: dict[str, Any], target_project_ref: str
) -> dict[str, Any]:
    if plan.get("schema") != SCHEMA or plan.get("classification") != CLASSIFICATION:
        raise ValueError("load request requires a sealed identity-staging plan")
    if plan.get("policy") != POLICY:
        raise ValueError("identity-staging plan policy drift")
    if not target_project_ref or not target_project_ref.isalnum():
        raise ValueError("target project ref must be explicit")
    return {
        "schema": LOAD_SCHEMA,
        "classification": LOAD_CLASSIFICATION,
        "target_project_ref": target_project_ref,
        "operation": "stage_and_seal",
        "plan": {
            "batch_id": plan["batch_id"],
            "sha256": sha256_json(plan),
        },
        "expected": dict(plan["summary"]),
        "policy": dict(LOAD_POLICY),
    }


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_uuid(value: str) -> str:
    return f"{_sql_text(str(uuid.UUID(value)))}::uuid"


def _sql_json(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{_sql_text(payload)}::jsonb"


def _sql_text_array(values: list[str]) -> str:
    if not values:
        return "'{}'::text[]"
    return "array[" + ", ".join(_sql_text(value) for value in values) + "]::text[]"


def render_load_sql(plan: dict[str, Any], manifest: dict[str, Any]) -> str:
    expected_manifest = build_load_manifest(plan, manifest.get("target_project_ref", ""))
    if manifest != expected_manifest:
        raise ValueError("identity-staging load manifest does not reproduce")

    batch_id = _sql_uuid(plan["batch_id"])
    plan_sha = _sql_text(manifest["plan"]["sha256"])
    expected = manifest["expected"]
    lines = [
        "-- Generated by engine.research.staging; do not edit.",
        f"-- Plan SHA-256: {manifest['plan']['sha256']}",
        "begin isolation level repeatable read;",
        "set local lock_timeout = '10s';",
        "set local statement_timeout = '180s';",
        "select pg_advisory_xact_lock(",
        "  hashtextextended('computerecord:identity-staging-load', 0)",
        ");",
        "do $identity_load$",
        "declare",
        "  existing_state core.identity_staging_state;",
        "  existing_sha text;",
        "  canonical_entity_count bigint;",
        "  fact_version_count bigint;",
        "begin",
        "  select count(*) into canonical_entity_count from core.entity;",
        "  select count(*) into fact_version_count from core.fact_version;",
        "  select b.state, b.plan_sha256 into existing_state, existing_sha",
        f"  from core.identity_staging_batch b where b.id = {batch_id};",
        "  if found then",
        f"    if existing_state <> 'sealed' or existing_sha <> {plan_sha} then",
        "      raise exception 'identity staging batch exists in a different state';",
        "    end if;",
        f"    perform core.seal_identity_staging_batch({batch_id}, {plan_sha});",
        "    return;",
        "  end if;",
        "  insert into core.identity_staging_batch (",
        "    id, plan_sha256, classification, expected_review_packets,",
        "    expected_identity_candidates, expected_canonical_ready,",
        "    expected_canonical_blocked, expected_blocker_count",
        "  ) values (",
        f"    {batch_id}, {plan_sha}, {_sql_text(CLASSIFICATION)},",
        f"    {expected['review_packets']}, {expected['identity_candidates']},",
        f"    {expected['canonical_ready']}, {expected['canonical_blocked']},",
        f"    {expected['blocker_count']}",
        "  );",
    ]
    for item in plan["inputs"]:
        lines.extend([
            "  insert into core.identity_staging_input (",
            "    batch_id, packet_key, review_id, decision_id, merge_commit,",
            "    claims_sha256, entity_seeds_sha256, review_manifest_sha256,",
            "    review_decision_sha256",
            "  ) values (",
            f"    {batch_id}, {_sql_text(item['packet_key'])},",
            f"    {_sql_uuid(item['review_id'])}, {_sql_uuid(item['decision_id'])},",
            f"    {_sql_text(item['merge_commit'])}, {_sql_text(item['claims_sha256'])},",
            f"    {_sql_text(item['entity_seeds_sha256'])},",
            f"    {_sql_text(item['review_manifest_sha256'])},",
            f"    {_sql_text(item['review_decision_sha256'])}",
            "  );",
        ])
    for row in plan["rows"]:
        lines.extend([
            "  insert into core.identity_staging_candidate (",
            "    batch_id, candidate_id, candidate_key, entity_type, canonical_name,",
            "    proposed_attributes, canonical_blockers, source_decision_id",
            "  ) values (",
            f"    {batch_id}, {_sql_uuid(row['candidate_id'])},",
            f"    {_sql_text(row['candidate_key'])}, {_sql_text(row['entity_type'])},",
            f"    {_sql_text(row['canonical_name'])}, {_sql_json(row['proposed_attributes'])},",
            f"    {_sql_text_array(row['canonical_blockers'])},",
            f"    {_sql_uuid(row['source_decision_id'])}",
            "  );",
        ])
        for alias in row["aliases"]:
            lines.extend([
                "  insert into core.identity_staging_alias",
                "    (batch_id, candidate_id, alias) values (",
                f"    {batch_id}, {_sql_uuid(row['candidate_id'])}, {_sql_text(alias)}",
                "  );",
            ])
        for claim_id in row["support_claim_ids"]:
            lines.extend([
                "  insert into core.identity_staging_support",
                "    (batch_id, candidate_id, claim_id) values (",
                f"    {batch_id}, {_sql_uuid(row['candidate_id'])}, {_sql_uuid(claim_id)}",
                "  );",
            ])
        for dependency_id in row["dependency_candidate_ids"]:
            lines.extend([
                "  insert into core.identity_staging_dependency",
                "    (batch_id, candidate_id, dependency_candidate_id) values (",
                f"    {batch_id}, {_sql_uuid(row['candidate_id'])}, {_sql_uuid(dependency_id)}",
                "  );",
            ])
    lines.extend([
        f"  perform core.seal_identity_staging_batch({batch_id}, {plan_sha});",
        "  if canonical_entity_count <> (select count(*) from core.entity)",
        "     or fact_version_count <> (select count(*) from core.fact_version) then",
        "    raise exception 'identity staging load crossed the canonical boundary';",
        "  end if;",
        "end;",
        "$identity_load$;",
        "commit;",
        "select jsonb_build_object(",
        "  'batch_id', b.id, 'state', b.state, 'plan_sha256', b.plan_sha256,",
        "  'candidates', (select count(*) from core.identity_staging_candidate c where c.batch_id = b.id),",
        "  'ready', (select count(*) from core.identity_staging_candidate c where c.batch_id = b.id and cardinality(c.canonical_blockers) = 0),",
        "  'blocked', (select count(*) from core.identity_staging_candidate c where c.batch_id = b.id and cardinality(c.canonical_blockers) > 0),",
        "  'canonical_entities', (select count(*) from core.entity),",
        "  'facts', (select count(*) from core.fact_version)",
        ") as staging_receipt",
        f"from core.identity_staging_batch b where b.id = {batch_id};",
        "",
    ])
    return "\n".join(lines)


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
    parser.add_argument(
        "command", choices=("build", "verify", "build-load", "verify-load")
    )
    parser.add_argument("--packet-dir", action="append", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--load-manifest")
    parser.add_argument("--sql")
    parser.add_argument("--target-project-ref")
    args = parser.parse_args()
    packets = [_load_packet(Path(path)) for path in args.packet_dir]
    if args.command == "build":
        write_json(Path(args.plan), build_staging_plan(packets))
        return

    plan = load_json(Path(args.plan))
    result = verify_staging_plan(plan, packets)
    if args.command == "verify":
        print(
            "identity staging verification: "
            f"{result['identity_candidates']} candidates, "
            f"{result['canonical_blocked']} blocked from canonical rows"
        )
        return

    if not args.load_manifest or not args.sql or not args.target_project_ref:
        parser.error(
            "build-load and verify-load require --load-manifest, --sql, "
            "and --target-project-ref"
        )
    manifest = build_load_manifest(plan, args.target_project_ref)
    sql = render_load_sql(plan, manifest)
    if args.command == "build-load":
        write_json(Path(args.load_manifest), manifest)
        Path(args.sql).write_text(sql, encoding="utf-8")
    else:
        if load_json(Path(args.load_manifest)) != manifest:
            raise ValueError("identity-staging load manifest does not reproduce")
        if Path(args.sql).read_text(encoding="utf-8") != sql:
            raise ValueError("identity-staging SQL does not reproduce")
        print(
            "identity staging load verification: "
            f"batch {plan['batch_id']}, {result['identity_candidates']} candidates"
        )


if __name__ == "__main__":
    main()
