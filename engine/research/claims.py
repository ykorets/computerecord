"""Build and verify anchored source assertions and entity-seed candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from engine.archive.capture import load_json, sha256_bytes, verify_receipt, write_json

SPEC_SCHEMA = "computerecord.anchored-claim-spec.v1"
CLAIMS_SCHEMA = "computerecord.anchored-source-assertions.v1"
SEEDS_SCHEMA = "computerecord.entity-seed-candidates.v1"
REVIEW_SCHEMA = "computerecord.claim-review-manifest.v1"
CLAIMS_CLASSIFICATION = "validated_source_assertions"
SEEDS_CLASSIFICATION = "staging_entity_seed_candidates"
REVIEW_CLASSIFICATION = "proposed_review"
EXTRACTOR_VERSION = "m3-anchored-claims-v1"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() in {"script", "style"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


class XbrlFactParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active: list[dict[str, Any]] = []
        self.facts: list[dict[str, str]] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        if tag not in {"ix:nonnumeric", "ix:nonfraction"}:
            return
        attrs = {key.lower(): value for key, value in attributes}
        if attrs.get("name"):
            self.active.append(
                {"tag": tag, "concept": attrs["name"], "parts": []}
            )

    def handle_data(self, data: str) -> None:
        for fact in self.active:
            fact["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag not in {"ix:nonnumeric", "ix:nonfraction"} or not self.active:
            return
        fact = self.active.pop()
        self.facts.append(
            {
                "concept": fact["concept"],
                "value": normalize_whitespace(" ".join(fact["parts"])),
            }
        )


def extract_document(payload: bytes) -> tuple[str, list[dict[str, str]]]:
    html = payload.decode("utf-8")
    visible_parser = VisibleTextParser()
    visible_parser.feed(html)
    xbrl_parser = XbrlFactParser()
    xbrl_parser.feed(html)
    return (
        normalize_whitespace(" ".join(visible_parser.parts)),
        xbrl_parser.facts,
    )


def _stable_id(kind: str, source_sha256: str, key: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"https://computerecord.com/id/{kind}/{source_sha256}/{key}",
        )
    )


def _validate_spec(spec: dict[str, Any], receipt: dict[str, Any]) -> None:
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("unknown anchored claim specification schema")
    if spec.get("document_sha256") != receipt["retrieval"]["sha256"]:
        raise ValueError("claim specification does not match capture receipt")
    anchor_keys = [anchor["anchor_key"] for anchor in spec.get("anchors") or []]
    claim_keys = [claim["claim_key"] for claim in spec.get("claims") or []]
    candidate_keys = [
        candidate["candidate_key"]
        for candidate in spec.get("entity_candidates") or []
    ]
    for label, keys in (
        ("anchor", anchor_keys),
        ("claim", claim_keys),
        ("entity candidate", candidate_keys),
    ):
        if len(keys) != len(set(keys)):
            raise ValueError(f"{label} keys must be unique")
    known_anchors = set(anchor_keys)
    for claim in spec.get("claims") or []:
        if not claim.get("anchor_keys") or not set(claim["anchor_keys"]) <= known_anchors:
            raise ValueError("every source assertion needs known anchors")
    known_claims = set(claim_keys)
    known_candidates = set(candidate_keys)
    for candidate in spec.get("entity_candidates") or []:
        if not candidate.get("support_claim_keys") or not set(
            candidate["support_claim_keys"]
        ) <= known_claims:
            raise ValueError("every entity seed needs known supporting claims")
        if (
            candidate.get("place_candidate_key")
            and candidate["place_candidate_key"] not in known_candidates
        ):
            raise ValueError("entity seed references an unknown place candidate")


def _resolve_anchors(
    spec: dict[str, Any], text: str, xbrl_facts: list[dict[str, str]]
) -> list[dict[str, Any]]:
    resolved = []
    for anchor in spec["anchors"]:
        anchor_key = anchor["anchor_key"]
        if anchor["kind"] == "quote":
            quote = normalize_whitespace(anchor["quote"])
            occurrences = text.count(quote)
            if occurrences != 1:
                raise ValueError(
                    f"quote anchor {anchor_key} must occur exactly once, "
                    f"found {occurrences}"
                )
            start = text.index(quote)
            resolved.append(
                {
                    "anchor_id": anchor_key,
                    "kind": "quote",
                    "normalized_text_end": start + len(quote),
                    "normalized_text_start": start,
                    "quote": quote,
                    "quote_sha256": sha256_bytes(quote.encode("utf-8")),
                }
            )
        elif anchor["kind"] == "xbrl_fact":
            matches = [
                fact
                for fact in xbrl_facts
                if fact["concept"] == anchor["concept"]
                and fact["value"] == anchor["value"]
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"XBRL anchor {anchor_key} must occur exactly once, "
                    f"found {len(matches)}"
                )
            resolved.append(
                {
                    "anchor_id": anchor_key,
                    "concept": anchor["concept"],
                    "kind": "xbrl_fact",
                    "value": anchor["value"],
                }
            )
        else:
            raise ValueError(f"unsupported anchor kind: {anchor.get('kind')}")
    return resolved


def build_packet(
    spec: dict[str, Any],
    receipt: dict[str, Any],
    source_payload: bytes,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    verify_receipt(receipt, object_payload=source_payload)
    _validate_spec(spec, receipt)
    source_sha256 = receipt["retrieval"]["sha256"]
    text, xbrl_facts = extract_document(source_payload)
    anchors = _resolve_anchors(spec, text, xbrl_facts)
    known_anchor_ids = {anchor["anchor_id"] for anchor in anchors}
    anchor_values = {
        anchor["anchor_id"]: (
            anchor["quote"] if anchor["kind"] == "quote" else anchor["value"]
        )
        for anchor in anchors
    }

    claims = []
    claim_ids: dict[str, str] = {}
    for claim in spec["claims"]:
        if not set(claim["anchor_keys"]) <= known_anchor_ids:
            raise ValueError("claim references an unresolved anchor")
        anchored_text = " ".join(
            anchor_values[key] for key in claim["anchor_keys"]
        )
        value = claim["value"]
        if value["type"] == "text":
            if value["text"] not in anchored_text:
                raise ValueError(
                    f"claim {claim['claim_key']} text is absent from its anchors"
                )
        elif value["type"] == "number":
            numeric_tokens = {
                token.replace(",", "")
                for token in re.findall(r"\d[\d,]*(?:\.\d+)?", anchored_text)
            }
            if str(value["number"]) not in numeric_tokens:
                raise ValueError(
                    f"claim {claim['claim_key']} number is absent from its anchors"
                )
        else:
            raise ValueError(f"unsupported claim value type: {value.get('type')}")
        claim_id = _stable_id("claim", source_sha256, claim["claim_key"])
        claim_ids[claim["claim_key"]] = claim_id
        claims.append(
            {
                "anchor_ids": claim["anchor_keys"],
                "claim_id": claim_id,
                "claim_key": claim["claim_key"],
                "predicate": claim["predicate"],
                "qualifier": claim.get("qualifier"),
                "status": "validated",
                "subject_hint": claim["subject_hint"],
                "value": claim["value"],
            }
        )

    claims_document = {
        "schema": CLAIMS_SCHEMA,
        "classification": CLAIMS_CLASSIFICATION,
        "document": {
            "normalized_text_sha256": sha256_bytes(text.encode("utf-8")),
            "receipt_sha256": sha256_bytes(canonical_json_bytes(receipt)),
            "source_sha256": source_sha256,
        },
        "extractor_version": EXTRACTOR_VERSION,
        "validation_scope": (
            "Anchors and source values only. Validation does not make a "
            "source assertion a canonical fact."
        ),
        "anchors": anchors,
        "claims": claims,
    }

    candidate_ids = {
        candidate["candidate_key"]: _stable_id(
            "entity-candidate", source_sha256, candidate["candidate_key"]
        )
        for candidate in spec["entity_candidates"]
    }
    candidates = []
    for candidate in spec["entity_candidates"]:
        candidate_id = candidate_ids[candidate["candidate_key"]]
        row = {
            "candidate_id": candidate_id,
            "candidate_key": candidate["candidate_key"],
            "canonical_name": candidate["canonical_name"],
            "entity_type": candidate["entity_type"],
            "proposed_attributes": candidate.get("proposed_attributes") or {},
            "review_state": "proposed",
            "support_claim_ids": [
                claim_ids[key] for key in candidate["support_claim_keys"]
            ],
        }
        if candidate.get("aliases"):
            row["aliases"] = candidate["aliases"]
        if candidate.get("place_candidate_key"):
            row["place_candidate_id"] = candidate_ids[
                candidate["place_candidate_key"]
            ]
        candidates.append(row)

    blocked = []
    for item in spec.get("blocked_normalizations") or []:
        blocked.append(
            {
                "claim_id": claim_ids[item["claim_key"]],
                "proposed_fact_kind": item["proposed_fact_kind"],
                "reason": item["reason"],
                "state": "blocked_pending_review",
            }
        )
    seeds_document = {
        "schema": SEEDS_SCHEMA,
        "classification": SEEDS_CLASSIFICATION,
        "candidates": candidates,
        "blocked_normalizations": blocked,
        "policy": {
            "database_writes_allowed": False,
            "fact_creation_allowed": False,
            "promotion_allowed": False,
        },
    }
    review_manifest = {
        "schema": REVIEW_SCHEMA,
        "classification": REVIEW_CLASSIFICATION,
        "review_id": _stable_id("review", source_sha256, spec["packet_key"]),
        "review_state": "proposed",
        "packet_key": spec["packet_key"],
        "inputs": {
            "receipt_sha256": sha256_bytes(canonical_json_bytes(receipt)),
            "source_sha256": source_sha256,
            "spec_sha256": sha256_bytes(canonical_json_bytes(spec)),
        },
        "outputs": {
            "claim_ids": sorted(claim_ids.values()),
            "claims_sha256": sha256_bytes(canonical_json_bytes(claims_document)),
            "entity_candidate_ids": sorted(candidate_ids.values()),
            "entity_seeds_sha256": sha256_bytes(
                canonical_json_bytes(seeds_document)
            ),
        },
        "policy": {
            "database_writes": False,
            "facts_created": False,
            "merge_requests_review_decision": True,
            "promotion_allowed": False,
            "source_assertions_only": True,
        },
    }
    return claims_document, seeds_document, review_manifest


def verify_packet(
    packet_dir: Path,
    spec_path: Path,
    receipt_path: Path,
    *,
    object_payload: bytes | None = None,
) -> dict[str, int]:
    claims = load_json(packet_dir / "claims.json")
    seeds = load_json(packet_dir / "entity-seeds.json")
    review = load_json(packet_dir / "review-manifest.json")
    spec = load_json(spec_path)
    receipt = load_json(receipt_path)
    _validate_spec(spec, receipt)
    source_sha256 = receipt["retrieval"]["sha256"]

    if claims.get("schema") != CLAIMS_SCHEMA:
        raise ValueError("unknown claims artifact schema")
    if seeds.get("schema") != SEEDS_SCHEMA:
        raise ValueError("unknown entity seeds artifact schema")
    if review.get("schema") != REVIEW_SCHEMA:
        raise ValueError("unknown claim review manifest schema")
    if claims.get("classification") != CLAIMS_CLASSIFICATION:
        raise ValueError("claims classification drift")
    if seeds.get("classification") != SEEDS_CLASSIFICATION:
        raise ValueError("entity seeds classification drift")
    if review.get("classification") != REVIEW_CLASSIFICATION:
        raise ValueError("review manifest classification drift")
    if review.get("review_state") != "proposed":
        raise ValueError("unmerged review packet cannot be approved")
    if review.get("review_id") != _stable_id(
        "review", source_sha256, spec["packet_key"]
    ):
        raise ValueError("review id is not deterministic")
    if review.get("policy") != {
        "database_writes": False,
        "facts_created": False,
        "merge_requests_review_decision": True,
        "promotion_allowed": False,
        "source_assertions_only": True,
    }:
        raise ValueError("review packet escaped its source-assertion boundary")
    if seeds.get("policy") != {
        "database_writes_allowed": False,
        "fact_creation_allowed": False,
        "promotion_allowed": False,
    }:
        raise ValueError("entity seeds escaped staging")
    if review["inputs"] != {
        "receipt_sha256": sha256_bytes(canonical_json_bytes(receipt)),
        "source_sha256": receipt["retrieval"]["sha256"],
        "spec_sha256": sha256_bytes(canonical_json_bytes(spec)),
    }:
        raise ValueError("review inputs do not match exact source artifacts")
    if review["outputs"]["claims_sha256"] != sha256_bytes(
        canonical_json_bytes(claims)
    ):
        raise ValueError("claims artifact hash mismatch")
    if review["outputs"]["entity_seeds_sha256"] != sha256_bytes(
        canonical_json_bytes(seeds)
    ):
        raise ValueError("entity seeds artifact hash mismatch")
    claim_ids = sorted(claim["claim_id"] for claim in claims["claims"])
    candidate_ids = sorted(
        candidate["candidate_id"] for candidate in seeds["candidates"]
    )
    if review["outputs"]["claim_ids"] != claim_ids:
        raise ValueError("review claim ids do not match claims artifact")
    if review["outputs"]["entity_candidate_ids"] != candidate_ids:
        raise ValueError("review candidate ids do not match seeds artifact")
    if claims.get("extractor_version") != EXTRACTOR_VERSION:
        raise ValueError("claims extractor version drift")
    if claims.get("document", {}).get("source_sha256") != source_sha256:
        raise ValueError("claims source hash does not match receipt")
    if not re.fullmatch(
        r"[0-9a-f]{64}",
        claims.get("document", {}).get("normalized_text_sha256") or "",
    ):
        raise ValueError("claims normalized text hash is invalid")

    spec_anchors = {
        anchor["anchor_key"]: anchor for anchor in spec["anchors"]
    }
    output_anchors = {
        anchor["anchor_id"]: anchor for anchor in claims["anchors"]
    }
    if set(spec_anchors) != set(output_anchors):
        raise ValueError("claims anchors do not match specification")
    for anchor_key, anchor_spec in spec_anchors.items():
        output = output_anchors[anchor_key]
        if output.get("kind") != anchor_spec["kind"]:
            raise ValueError("claim anchor kind drift")
        if anchor_spec["kind"] == "quote":
            quote = normalize_whitespace(anchor_spec["quote"])
            if (
                output.get("quote") != quote
                or output.get("quote_sha256")
                != sha256_bytes(quote.encode("utf-8"))
                or not isinstance(output.get("normalized_text_start"), int)
                or not isinstance(output.get("normalized_text_end"), int)
                or output["normalized_text_end"]
                - output["normalized_text_start"]
                != len(quote)
            ):
                raise ValueError("quote anchor metadata drift")
        elif (
            output.get("concept") != anchor_spec["concept"]
            or output.get("value") != anchor_spec["value"]
        ):
            raise ValueError("XBRL anchor metadata drift")

    spec_claims = {claim["claim_key"]: claim for claim in spec["claims"]}
    output_claims = {claim["claim_key"]: claim for claim in claims["claims"]}
    if set(spec_claims) != set(output_claims):
        raise ValueError("claims do not match specification")
    for claim_key, claim_spec in spec_claims.items():
        output = output_claims[claim_key]
        expected_id = _stable_id("claim", source_sha256, claim_key)
        expected = {
            "anchor_ids": claim_spec["anchor_keys"],
            "claim_id": expected_id,
            "claim_key": claim_key,
            "predicate": claim_spec["predicate"],
            "qualifier": claim_spec.get("qualifier"),
            "status": "validated",
            "subject_hint": claim_spec["subject_hint"],
            "value": claim_spec["value"],
        }
        if output != expected:
            raise ValueError(f"claim {claim_key} metadata drift")

    known_claims = set(claim_ids)
    spec_candidates = {
        candidate["candidate_key"]: candidate
        for candidate in spec["entity_candidates"]
    }
    output_candidates = {
        candidate["candidate_key"]: candidate
        for candidate in seeds["candidates"]
    }
    if set(spec_candidates) != set(output_candidates):
        raise ValueError("entity candidates do not match specification")
    for candidate in seeds["candidates"]:
        if not candidate["support_claim_ids"] or not set(
            candidate["support_claim_ids"]
        ) <= known_claims:
            raise ValueError("entity candidate has invalid claim support")
        candidate_spec = spec_candidates[candidate["candidate_key"]]
        expected = {
            "candidate_id": _stable_id(
                "entity-candidate",
                source_sha256,
                candidate_spec["candidate_key"],
            ),
            "candidate_key": candidate_spec["candidate_key"],
            "canonical_name": candidate_spec["canonical_name"],
            "entity_type": candidate_spec["entity_type"],
            "proposed_attributes": candidate_spec.get("proposed_attributes")
            or {},
            "review_state": "proposed",
            "support_claim_ids": [
                _stable_id("claim", source_sha256, key)
                for key in candidate_spec["support_claim_keys"]
            ],
        }
        if candidate_spec.get("aliases"):
            expected["aliases"] = candidate_spec["aliases"]
        if candidate_spec.get("place_candidate_key"):
            expected["place_candidate_id"] = _stable_id(
                "entity-candidate",
                source_sha256,
                candidate_spec["place_candidate_key"],
            )
        if candidate != expected:
            raise ValueError(
                f"entity candidate {candidate['candidate_key']} metadata drift"
            )

    expected_blocked = [
        {
            "claim_id": _stable_id(
                "claim", source_sha256, item["claim_key"]
            ),
            "proposed_fact_kind": item["proposed_fact_kind"],
            "reason": item["reason"],
            "state": "blocked_pending_review",
        }
        for item in spec.get("blocked_normalizations") or []
    ]
    if seeds["blocked_normalizations"] != expected_blocked:
        raise ValueError("blocked normalizations do not match specification")

    if object_payload is not None:
        expected = build_packet(spec, receipt, object_payload)
        if claims != expected[0] or seeds != expected[1] or review != expected[2]:
            raise ValueError("review packet does not reproduce from archive bytes")
    return {
        "claims": len(claim_ids),
        "entity_candidates": len(candidate_ids),
        "blocked_normalizations": len(seeds["blocked_normalizations"]),
    }


def build_command(args: argparse.Namespace) -> None:
    spec = load_json(Path(args.spec))
    receipt = load_json(Path(args.receipt))
    payload = Path(args.object_file).read_bytes()
    claims, seeds, review = build_packet(spec, receipt, payload)
    output_dir = Path(args.output_dir)
    write_json(output_dir / "claims.json", claims)
    write_json(output_dir / "entity-seeds.json", seeds)
    write_json(output_dir / "review-manifest.json", review)


def verify_command(args: argparse.Namespace) -> None:
    payload = Path(args.object_file).read_bytes() if args.object_file else None
    result = verify_packet(
        Path(args.packet_dir),
        Path(args.spec),
        Path(args.receipt),
        object_payload=payload,
    )
    print(
        "claim review verification: "
        f"{result['claims']} claims, "
        f"{result['entity_candidates']} entity candidates, "
        f"{result['blocked_normalizations']} blocked normalizations"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--spec", required=True)
    build_parser.add_argument("--receipt", required=True)
    build_parser.add_argument("--object-file", required=True)
    build_parser.add_argument("--output-dir", required=True)
    build_parser.set_defaults(func=build_command)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--packet-dir", required=True)
    verify_parser.add_argument("--spec", required=True)
    verify_parser.add_argument("--receipt", required=True)
    verify_parser.add_argument("--object-file")
    verify_parser.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
