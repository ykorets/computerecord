import copy
import json
import tempfile
import unittest
from pathlib import Path

from engine.archive.capture import build_receipt, sha256_bytes, write_json
from engine.research.claims import build_packet, verify_packet


class AnchoredClaimsTest(unittest.TestCase):
    def setUp(self):
        self.payload = b"""<html><body>
        <ix:nonNumeric name="dei:EntityRegistrantName">IREN Limited</ix:nonNumeric>
        <p>We have seven data center sites.</p>
        <p>three in Texas, United States, namely Childress (750MW)</p>
        </body></html>""" + (b" " * 1024)
        source_sha = sha256_bytes(self.payload)
        retrieval = {
            "schema": "computerecord.source-retrieval.v1",
            "allowed_host": "sec.gov",
            "archive_key": f"docs/{source_sha}.html",
            "captured_at": "2026-07-25T00:54:07Z",
            "content_type": "text/html",
            "final_url": "https://www.sec.gov/Archives/example.htm",
            "http_date": "Sat, 25 Jul 2026 00:54:07 GMT",
            "http_status": 200,
            "requested_url": "https://www.sec.gov/Archives/example.htm",
            "sha256": source_sha,
            "size_bytes": len(self.payload),
        }
        self.receipt = build_receipt(
            retrieval,
            self.payload,
            bucket="btw-docs",
            target_id="benchmark:childress",
            task_id="task:childress",
            publisher="SEC",
            source_class="federal_filing",
            discovery_method="independent_sec_edgar_search",
            verified_at="2026-07-25T00:55:00Z",
        )
        self.spec = {
            "schema": "computerecord.anchored-claim-spec.v1",
            "packet_key": "childress",
            "document_sha256": source_sha,
            "anchors": [
                {
                    "anchor_key": "registrant",
                    "kind": "xbrl_fact",
                    "concept": "dei:EntityRegistrantName",
                    "value": "IREN Limited",
                },
                {
                    "anchor_key": "location",
                    "kind": "quote",
                    "quote": (
                        "three in Texas, United States, namely "
                        "Childress (750MW)"
                    ),
                },
            ],
            "claims": [
                {
                    "claim_key": "legal_name",
                    "subject_hint": "IREN",
                    "predicate": "legal_name",
                    "value": {"type": "text", "text": "IREN Limited"},
                    "anchor_keys": ["registrant"],
                },
                {
                    "claim_key": "city",
                    "subject_hint": "Childress",
                    "predicate": "place_city",
                    "value": {"type": "text", "text": "Childress"},
                    "anchor_keys": ["location"],
                },
            ],
            "entity_candidates": [
                {
                    "candidate_key": "organization-iren",
                    "entity_type": "organization",
                    "canonical_name": "IREN Limited",
                    "support_claim_keys": ["legal_name"],
                },
                {
                    "candidate_key": "place-childress",
                    "entity_type": "place",
                    "canonical_name": "Childress, Texas, United States",
                    "support_claim_keys": ["city"],
                },
                {
                    "candidate_key": "campus-childress",
                    "entity_type": "campus",
                    "canonical_name": "IREN Childress",
                    "place_candidate_key": "place-childress",
                    "support_claim_keys": ["city"],
                },
            ],
            "blocked_normalizations": [],
        }

    def test_packet_reproduces_from_exact_archive_bytes(self):
        claims, seeds, review = build_packet(
            self.spec, self.receipt, self.payload
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "claims.json", claims)
            write_json(root / "entity-seeds.json", seeds)
            write_json(root / "review-manifest.json", review)
            spec_path = root / "spec.json"
            receipt_path = root / "receipt.json"
            write_json(spec_path, self.spec)
            write_json(receipt_path, self.receipt)
            result = verify_packet(
                root,
                spec_path,
                receipt_path,
                object_payload=self.payload,
            )
            self.assertEqual(result["claims"], 2)
            self.assertEqual(result["entity_candidates"], 3)

    def test_quote_must_be_unique(self):
        spec = copy.deepcopy(self.spec)
        spec["anchors"][1]["quote"] = "Childress"
        duplicate = self.payload.replace(
            b"</body>", b"<p>Childress</p></body>"
        )
        retrieval = copy.deepcopy(self.receipt["retrieval"])
        retrieval["sha256"] = sha256_bytes(duplicate)
        retrieval["size_bytes"] = len(duplicate)
        retrieval["archive_key"] = f"docs/{retrieval['sha256']}.html"
        receipt = build_receipt(
            retrieval,
            duplicate,
            bucket="btw-docs",
            target_id="benchmark:childress",
            task_id="task:childress",
            publisher="SEC",
            source_class="federal_filing",
            discovery_method="independent_sec_edgar_search",
            verified_at="2026-07-25T00:55:00Z",
        )
        spec["document_sha256"] = retrieval["sha256"]
        with self.assertRaisesRegex(ValueError, "exactly once"):
            build_packet(spec, receipt, duplicate)

    def test_capacity_normalization_can_remain_blocked(self):
        spec = copy.deepcopy(self.spec)
        spec["claims"].append(
            {
                "claim_key": "power",
                "subject_hint": "Childress",
                "predicate": "reported_power_capacity_mw",
                "value": {"type": "number", "number": 750, "unit": "MW"},
                "qualifier": "exact",
                "anchor_keys": ["location"],
            }
        )
        spec["blocked_normalizations"].append(
            {
                "claim_key": "power",
                "proposed_fact_kind": "capacity",
                "reason": "capacity semantics require review",
            }
        )
        _, seeds, _ = build_packet(spec, self.receipt, self.payload)
        self.assertEqual(
            seeds["blocked_normalizations"][0]["state"],
            "blocked_pending_review",
        )
        self.assertFalse(seeds["policy"]["fact_creation_allowed"])

    def test_claim_value_must_be_present_in_its_anchor(self):
        spec = copy.deepcopy(self.spec)
        spec["claims"][1]["value"]["text"] = "Dallas"
        with self.assertRaisesRegex(ValueError, "absent from"):
            build_packet(spec, self.receipt, self.payload)


if __name__ == "__main__":
    unittest.main()
