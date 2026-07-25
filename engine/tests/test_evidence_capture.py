import copy
import tempfile
import unittest
from pathlib import Path

from engine.archive.capture import (
    build_batch_manifest,
    build_receipt,
    sha256_bytes,
    verify_batch_manifest,
    verify_receipt,
    write_json,
)


class EvidenceCaptureTest(unittest.TestCase):
    def setUp(self):
        self.payload = b"<html>" + (b"official filing " * 100) + b"</html>"
        self.sha256 = sha256_bytes(self.payload)
        self.retrieval = {
            "schema": "computerecord.source-retrieval.v1",
            "allowed_host": "sec.gov",
            "archive_key": f"docs/{self.sha256}.html",
            "captured_at": "2026-07-24T20:00:00Z",
            "content_type": "text/html",
            "final_url": "https://www.sec.gov/Archives/example.htm",
            "http_date": "Fri, 24 Jul 2026 20:00:00 GMT",
            "http_status": 200,
            "requested_url": "https://www.sec.gov/Archives/example.htm",
            "sha256": self.sha256,
            "size_bytes": len(self.payload),
        }

    def _receipt(self):
        return build_receipt(
            self.retrieval,
            self.payload,
            bucket="btw-docs",
            target_id="neocloud-buildout-registry:childress",
            task_id="m3-primary-source-intake:childress",
            publisher="U.S. Securities and Exchange Commission",
            source_class="federal_filing",
            discovery_method="independent_sec_edgar_search",
            verified_at="2026-07-24T20:05:00Z",
        )

    def test_remote_bytes_are_required_to_seal_the_receipt(self):
        receipt = self._receipt()
        result = verify_receipt(receipt, object_payload=self.payload)
        self.assertEqual(result["sha256"], self.sha256)
        self.assertEqual(receipt["archive"]["key"], f"docs/{self.sha256}.html")
        self.assertTrue(receipt["archive"]["private"])

    def test_remote_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_receipt(
                self.retrieval,
                self.payload + b"changed",
                bucket="btw-docs",
                target_id="target",
                task_id="task",
                publisher="SEC",
                source_class="federal_filing",
                discovery_method="independent_sec_edgar_search",
                verified_at="2026-07-24T20:05:00Z",
            )

    def test_receipt_cannot_publish_or_create_entities(self):
        receipt = self._receipt()
        receipt["pipeline_state"]["entity_seed_created"] = True
        with self.assertRaisesRegex(ValueError, "document-only state"):
            verify_receipt(receipt)

    def test_rights_default_cannot_be_relaxed_silently(self):
        receipt = copy.deepcopy(self._receipt())
        receipt["rights"]["public_copy_allowed"] = True
        with self.assertRaisesRegex(ValueError, "fail closed"):
            verify_receipt(receipt)

    def test_receipt_url_cannot_escape_the_allowed_host(self):
        receipt = copy.deepcopy(self._receipt())
        receipt["retrieval"]["final_url"] = "https://example.com/filing"
        with self.assertRaisesRegex(ValueError, "public HTTPS"):
            verify_receipt(receipt)

    def test_batch_is_pinned_to_queue_task_and_receipt_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "queue.json"
            receipt_path = root / "batch" / "receipt.json"
            manifest_path = root / "batch" / "manifest.json"
            write_json(
                queue_path,
                {
                    "classification": "research_queue",
                    "tasks": [
                        {
                            "task_id": "m3-primary-source-intake:childress",
                            "benchmark_id": (
                                "neocloud-buildout-registry:childress"
                            ),
                        }
                    ],
                },
            )
            write_json(receipt_path, self._receipt())
            manifest = build_batch_manifest(
                queue_path, [receipt_path], root=root
            )
            write_json(manifest_path, manifest)
            result = verify_batch_manifest(
                manifest_path, root=root, expected_receipts=1
            )
            self.assertEqual(result["captured_documents"], 1)

            changed = self._receipt()
            changed["source"]["publisher"] = "Changed publisher"
            write_json(receipt_path, changed)
            with self.assertRaisesRegex(ValueError, "not reproducible"):
                verify_batch_manifest(manifest_path, root=root)

    def test_batch_paths_cannot_escape_repository_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            write_json(
                manifest_path,
                {
                    "schema": "computerecord.evidence-capture-batch.v1",
                    "classification": "private_evidence_manifest",
                    "inputs": {
                        "intake_queue_path": "../queue.json",
                        "intake_queue_sha256": "0" * 64,
                    },
                    "receipts": [],
                },
            )
            with self.assertRaises(ValueError):
                verify_batch_manifest(manifest_path, root=root)

    def test_batch_rejects_a_reused_benchmark_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "queue.json"
            receipt_path = root / "receipt.json"
            receipt = self._receipt()
            reused_url = receipt["retrieval"]["requested_url"]
            write_json(
                queue_path,
                {
                    "classification": "research_queue",
                    "tasks": [
                        {
                            "task_id": "m3-primary-source-intake:childress",
                            "benchmark_id": (
                                "neocloud-buildout-registry:childress"
                            ),
                            "discovery_leads": [{"url": reused_url}],
                        }
                    ],
                },
            )
            write_json(receipt_path, receipt)
            with self.assertRaisesRegex(ValueError, "copied from"):
                build_batch_manifest(queue_path, [receipt_path], root=root)


if __name__ == "__main__":
    unittest.main()
