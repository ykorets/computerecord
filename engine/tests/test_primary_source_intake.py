import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from engine.research.intake import (
    CLASSIFICATION,
    EVIDENCE_STATE,
    LEAD_CLASSIFICATION,
    SEED_STATE,
    build_queue,
    verify_artifacts,
    write_json,
)


class PrimarySourceIntakeTest(unittest.TestCase):
    def setUp(self):
        self.targets = {
            "schema": "computerecord.coverage-benchmark-targets.v1",
            "classification": "benchmark_only",
            "targets": [
                {
                    "benchmark_id": "benchmark:childress",
                    "classification": "benchmark_only",
                    "identity": {"name": "Childress", "operator": "IREN"},
                    "source_location": {
                        "city": "Childress",
                        "counties": ["Childress"],
                        "state": "TX",
                    },
                    "source_record_id": "childress",
                    "source_leads": [
                        {
                            "classification": "benchmark_discovery_lead",
                            "label": "SEC filing",
                            "reported_type": "primary",
                            "url": "https://www.sec.gov/Archives/example.htm",
                        }
                    ],
                },
                {
                    "benchmark_id": "benchmark:abilene",
                    "classification": "benchmark_only",
                    "identity": {"name": "Abilene", "operator": "Crusoe"},
                    "source_location": {
                        "city": "Abilene",
                        "counties": ["Taylor"],
                        "state": "TX",
                    },
                    "source_record_id": "abilene",
                    "source_leads": [],
                },
            ],
        }
        self.resolution = {
            "algorithm_version": "test-v1",
            "classification": "benchmark_only",
            "resolutions": [
                {
                    "benchmark_id": "benchmark:childress",
                    "resolution_state": "unresolved",
                },
                {
                    "benchmark_id": "benchmark:abilene",
                    "resolution_state": "resolved_btw_facility",
                    "resolved_entity": {
                        "entity_type": "btw_facility",
                        "slug": "abilene",
                    },
                },
            ],
        }

    def _build(self):
        return build_queue(
            self.targets,
            self.resolution,
            targets_sha256="targets-sha",
            resolution_sha256="resolution-sha",
        )

    def test_only_unresolved_targets_enter_the_queue(self):
        queue, report = self._build()
        self.assertEqual(queue["classification"], CLASSIFICATION)
        self.assertEqual(len(queue["tasks"]), 1)
        task = queue["tasks"][0]
        self.assertEqual(task["benchmark_id"], "benchmark:childress")
        self.assertEqual(task["priority"], "p0")
        self.assertEqual(task["evidence_state"], EVIDENCE_STATE)
        self.assertEqual(task["entity_seed_state"], SEED_STATE)
        self.assertEqual(report["summary"]["tasks"], 1)
        self.assertEqual(report["summary"]["captured_documents"], 0)

    def test_competitor_link_remains_an_unverified_lead(self):
        queue, _ = self._build()
        lead = queue["tasks"][0]["discovery_leads"][0]
        self.assertEqual(lead["classification"], LEAD_CLASSIFICATION)
        self.assertTrue(queue["policy"]["independent_rediscovery_required"])
        self.assertFalse(queue["policy"]["competitor_leads_are_evidence"])
        serialized = json.dumps(queue)
        self.assertNotIn('"claim"', serialized)
        self.assertNotIn('"document_id"', serialized)
        self.assertNotIn('"entity_id"', serialized)

    def test_non_https_leads_fail_closed(self):
        self.targets["targets"][0]["source_leads"][0]["url"] = (
            "http://www.sec.gov/Archives/example.htm"
        )
        with self.assertRaisesRegex(ValueError, "public HTTPS"):
            self._build()

    def test_promoted_input_lead_fails_closed(self):
        self.targets["targets"][0]["source_leads"][0]["classification"] = "evidence"
        with self.assertRaisesRegex(ValueError, "benchmark discovery lead"):
            self._build()

    def test_verifier_detects_promotion_or_input_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets_path = root / "targets.json"
            resolution_path = root / "resolution.json"
            write_json(targets_path, self.targets)
            write_json(resolution_path, self.resolution)
            queue, report = build_queue(
                self.targets,
                self.resolution,
                targets_sha256=hashlib.sha256(targets_path.read_bytes()).hexdigest(),
                resolution_sha256=hashlib.sha256(
                    resolution_path.read_bytes()
                ).hexdigest(),
            )
            artifact_dir = root / "artifacts"
            write_json(artifact_dir / "queue.json", queue)
            write_json(artifact_dir / "report.json", report)
            summary = verify_artifacts(
                artifact_dir,
                targets_path,
                resolution_path,
                expected_tasks=1,
            )
            self.assertEqual(summary["p0"], 1)

            promoted = copy.deepcopy(queue)
            promoted["tasks"][0]["discovery_leads"][0][
                "classification"
            ] = "evidence"
            write_json(artifact_dir / "queue.json", promoted)
            with self.assertRaisesRegex(ValueError, "not reproducible"):
                verify_artifacts(artifact_dir, targets_path, resolution_path)


if __name__ == "__main__":
    unittest.main()
