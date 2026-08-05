"""Build and verify review-only typed fact-normalization candidates."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from engine.archive.capture import load_json, sha256_bytes, write_json

SPEC_SCHEMA = "computerecord.fact-normalization-spec.v1"
NORMALIZATIONS_SCHEMA = "computerecord.fact-normalization-candidates.v1"
REVIEW_SCHEMA = "computerecord.fact-normalization-review-manifest.v1"
NORMALIZER_VERSION = "m2.1-typed-normalizer-v1"
CLASSIFICATION = "staging_fact_normalization_candidates"
REVIEW_CLASSIFICATION = "proposed_normalization_review"
EPISTEMIC_TYPES = {
    "observed", "administrative", "reported", "estimated", "modeled",
    "forecast", "derived",
}
VERIFICATION_STATES = {
    "source_asserted", "corroborated", "verified", "disputed",
}
CAPACITY_VOCABULARY = {
    "utility_service_mw": "service_limit",
    "gross_generation_nameplate_mw": "gross_nameplate",
    "permitted_generation_mw": "permitted",
    "critical_it_mw": "critical_it",
    "contracted_it_mw": "contracted_it",
    "energized_it_mw": "energized_it",
    "occupied_it_mw": "occupied_it",
    "planned_it_mw": "planned_it",
}
QUALIFIERS = {"exact", "approximate", "at_least", "at_most", "range"}
POLICY = {
    "database_writes_allowed": False,
    "fact_creation_allowed": False,
    "promotion_allowed": False,
    "review_required": True,
}
REVIEW_POLICY = {
    "database_writes": False,
    "facts_created": False,
    "merge_requests_review_decision": True,
    "promotion_allowed": False,
    "typed_normalizations_only": True,
}


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _stable_id(kind: str, source_sha256: str, key: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"https://computerecord.com/id/{kind}/{source_sha256}/{key}",
        )
    )


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO 8601 date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO 8601 date") from error
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must use canonical YYYY-MM-DD form")
    return parsed


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp")
    return parsed


def _validate_temporal_semantics(candidate: dict[str, Any]) -> None:
    epistemic_type = candidate.get("epistemic_type")
    if epistemic_type not in EPISTEMIC_TYPES:
        raise ValueError(
            "every normalization requires an explicit epistemic_type"
        )
    required_fields = {
        "epistemic_type",
        "period_start",
        "period_end",
        "issued_at",
        "forecast_horizon",
        "scenario",
    }
    if not required_fields <= set(candidate):
        raise ValueError(
            "measurement semantics must be explicit, including nulls"
        )
    if epistemic_type == "derived":
        raise ValueError(
            "source-claim normalizer cannot create derived fact candidates"
        )
    start_value = candidate.get("period_start")
    end_value = candidate.get("period_end")
    start = _parse_date(start_value, "period_start") if start_value else None
    end = _parse_date(end_value, "period_end") if end_value else None
    if end and (not start or end < start):
        raise ValueError(
            "period_end requires period_start and cannot precede it"
        )
    issued_value = candidate.get("issued_at")
    issued = _parse_timestamp(issued_value, "issued_at") if issued_value else None
    horizon_value = candidate.get("forecast_horizon")
    scenario = candidate.get("scenario")
    if epistemic_type == "forecast":
        if not issued or not horizon_value:
            raise ValueError("forecast requires issued_at and forecast_horizon")
        horizon = _parse_date(horizon_value, "forecast_horizon")
        if horizon < issued.date():
            raise ValueError("forecast_horizon cannot precede issued_at")
        if scenario is not None:
            valid_shape = isinstance(scenario, dict) and set(scenario) == {
                "scenario_key", "version",
            }
            valid_key = valid_shape and re.fullmatch(
                r"[a-z0-9]+([_-][a-z0-9]+)*",
                scenario.get("scenario_key") or "",
            )
            valid_version = (
                valid_shape
                and isinstance(scenario.get("version"), int)
                and scenario["version"] > 0
            )
            if not valid_key or not valid_version:
                raise ValueError("scenario reference is invalid")
    elif horizon_value is not None or scenario is not None:
        raise ValueError(
            "only forecast normalizations may set horizon or scenario"
        )


def _validate_capacity_payload(
    candidate: dict[str, Any],
    claims_by_key: dict[str, dict[str, Any]],
    entity_keys: set[str],
) -> None:
    if candidate.get("fact_kind") != "capacity":
        raise ValueError("typed normalizer v1 supports capacity facts only")
    payload = candidate.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("capacity normalization requires a typed payload")
    required = {
        "capacity_type", "capacity_basis", "qualifier", "scope_candidate_key",
    }
    if not required <= set(payload):
        raise ValueError("capacity payload is incomplete")
    if (
        CAPACITY_VOCABULARY.get(payload["capacity_type"])
        != payload["capacity_basis"]
    ):
        raise ValueError("capacity type and basis are incompatible")
    if payload["scope_candidate_key"] not in entity_keys:
        raise ValueError("capacity scope references an unknown entity candidate")
    qualifier = payload["qualifier"]
    if qualifier not in QUALIFIERS:
        raise ValueError("capacity qualifier is invalid")
    if qualifier == "range":
        if set(payload) != required | {"lower_mw", "upper_mw"}:
            raise ValueError("range capacity requires only lower_mw and upper_mw")
        lower, upper = payload["lower_mw"], payload["upper_mw"]
        if (
            type(lower) not in (int, float)
            or type(upper) not in (int, float)
            or lower < 0
            or upper < lower
        ):
            raise ValueError("capacity range is invalid")
        expected_numbers = {lower, upper}
    else:
        if set(payload) != required | {"value_mw"}:
            raise ValueError("non-range capacity requires only value_mw")
        value = payload["value_mw"]
        if type(value) not in (int, float) or value < 0:
            raise ValueError("capacity value must be nonnegative and numeric")
        expected_numbers = {value}
    supported_numbers = {
        claim["value"]["number"]
        for key in candidate["support_claim_keys"]
        for claim in [claims_by_key[key]]
        if claim.get("value", {}).get("type") == "number"
        and claim["value"].get("unit") == "MW"
    }
    if not expected_numbers <= supported_numbers:
        raise ValueError("capacity value is not present in MW source claims")


def _validate_inputs(
    spec: dict[str, Any], claims: dict[str, Any], seeds: dict[str, Any]
) -> None:
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("unknown fact normalization specification schema")
    if claims.get("schema") != "computerecord.anchored-source-assertions.v1":
        raise ValueError("unknown anchored claims schema")
    if seeds.get("schema") != "computerecord.entity-seed-candidates.v1":
        raise ValueError("unknown entity seeds schema")
    if claims.get("classification") != "validated_source_assertions":
        raise ValueError("normalizer requires validated source assertions")
    if seeds.get("classification") != "staging_entity_seed_candidates":
        raise ValueError("normalizer requires staging entity candidates")
    expected_seed_policy = {
        "database_writes_allowed": False,
        "fact_creation_allowed": False,
        "promotion_allowed": False,
    }
    if seeds.get("policy") != expected_seed_policy:
        raise ValueError("normalizer input escaped entity-seed staging")
    expected_inputs = {
        "claims_sha256": sha256_json(claims),
        "entity_seeds_sha256": sha256_json(seeds),
    }
    if spec.get("inputs") != expected_inputs:
        raise ValueError("normalization inputs do not match pinned artifacts")
    claims_by_key = {
        claim["claim_key"]: claim for claim in claims.get("claims") or []
    }
    entities_by_key = {
        candidate["candidate_key"]: candidate
        for candidate in seeds.get("candidates") or []
    }
    candidates = spec.get("candidates") or []
    keys = [candidate.get("normalization_key") for candidate in candidates]
    if not keys or len(keys) != len(set(keys)) or any(not key for key in keys):
        raise ValueError("normalization keys must be present and unique")
    for candidate in candidates:
        if candidate.get("subject_candidate_key") not in entities_by_key:
            raise ValueError(
                "normalization subject references an unknown entity candidate"
            )
        support_keys = candidate.get("support_claim_keys") or []
        if not support_keys or not set(support_keys) <= set(claims_by_key):
            raise ValueError("normalization requires known supporting claims")
        if candidate.get("verification_state") not in VERIFICATION_STATES:
            raise ValueError(
                "normalization requires an explicit verification_state"
            )
        if not candidate.get("rationale"):
            raise ValueError("normalization requires a rationale")
        _validate_temporal_semantics(candidate)
        _validate_capacity_payload(
            candidate, claims_by_key, set(entities_by_key)
        )


def build_packet(
    spec: dict[str, Any], claims: dict[str, Any], seeds: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(spec, claims, seeds)
    source_sha256 = claims["document"]["source_sha256"]
    claim_ids = {
        claim["claim_key"]: claim["claim_id"] for claim in claims["claims"]
    }
    entity_ids = {
        candidate["candidate_key"]: candidate["candidate_id"]
        for candidate in seeds["candidates"]
    }
    rows = []
    for candidate in spec["candidates"]:
        payload = dict(candidate["payload"])
        scope_key = payload.pop("scope_candidate_key")
        payload["scope_candidate_id"] = entity_ids[scope_key]
        rows.append(
            {
                "normalization_id": _stable_id(
                    "fact-normalization",
                    source_sha256,
                    candidate["normalization_key"],
                ),
                "normalization_key": candidate["normalization_key"],
                "review_state": "proposed",
                "subject_candidate_id": entity_ids[
                    candidate["subject_candidate_key"]
                ],
                "fact_kind": candidate["fact_kind"],
                "epistemic_type": candidate["epistemic_type"],
                "verification_state": candidate["verification_state"],
                "period_start": candidate.get("period_start"),
                "period_end": candidate.get("period_end"),
                "issued_at": candidate.get("issued_at"),
                "forecast_horizon": candidate.get("forecast_horizon"),
                "scenario": candidate.get("scenario"),
                "support_claim_ids": [
                    claim_ids[key] for key in candidate["support_claim_keys"]
                ],
                "payload": payload,
                "rationale": candidate["rationale"],
            }
        )
    normalizations = {
        "schema": NORMALIZATIONS_SCHEMA,
        "classification": CLASSIFICATION,
        "normalizer_version": NORMALIZER_VERSION,
        "candidates": rows,
        "policy": POLICY,
    }
    review = {
        "schema": REVIEW_SCHEMA,
        "classification": REVIEW_CLASSIFICATION,
        "review_id": _stable_id(
            "fact-normalization-review", source_sha256, spec["packet_key"]
        ),
        "review_state": "proposed",
        "packet_key": spec["packet_key"],
        "inputs": {
            **spec["inputs"],
            "spec_sha256": sha256_json(spec),
            "source_sha256": source_sha256,
        },
        "outputs": {
            "normalization_ids": sorted(
                row["normalization_id"] for row in rows
            ),
            "normalizations_sha256": sha256_json(normalizations),
        },
        "policy": REVIEW_POLICY,
    }
    return normalizations, review


def verify_packet(
    packet_dir: Path, spec_path: Path, claims_path: Path, seeds_path: Path
) -> dict[str, int]:
    expected = build_packet(
        load_json(spec_path), load_json(claims_path), load_json(seeds_path)
    )
    normalizations = load_json(packet_dir / "fact-normalizations.json")
    review = load_json(packet_dir / "normalization-review-manifest.json")
    if normalizations != expected[0]:
        raise ValueError("fact normalizations do not reproduce from pinned inputs")
    if review != expected[1]:
        raise ValueError("normalization review manifest does not reproduce")
    return {"normalization_candidates": len(normalizations["candidates"])}


def build_command(args: argparse.Namespace) -> None:
    normalizations, review = build_packet(
        load_json(Path(args.spec)),
        load_json(Path(args.claims)),
        load_json(Path(args.entity_seeds)),
    )
    output_dir = Path(args.output_dir)
    write_json(output_dir / "fact-normalizations.json", normalizations)
    write_json(output_dir / "normalization-review-manifest.json", review)


def verify_command(args: argparse.Namespace) -> None:
    result = verify_packet(
        Path(args.packet_dir),
        Path(args.spec),
        Path(args.claims),
        Path(args.entity_seeds),
    )
    print(
        "fact normalization verification: "
        f"{result['normalization_candidates']} candidates"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    verify = subparsers.add_parser("verify")
    for child in (build, verify):
        child.add_argument("--spec", required=True)
        child.add_argument("--claims", required=True)
        child.add_argument("--entity-seeds", required=True)
    build.add_argument("--output-dir", required=True)
    verify.add_argument("--packet-dir", required=True)
    build.set_defaults(func=build_command)
    verify.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
