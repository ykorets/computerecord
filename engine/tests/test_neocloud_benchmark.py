import json
import tempfile
import unittest
from pathlib import Path

from engine.benchmarks.neocloud import (
    CLASSIFICATION,
    _extract_public_endpoint,
    build_capture,
    resolve_targets,
    verify_artifacts,
    write_json,
)


class NeocloudBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.landing = b"""<html><head>
        <link rel="canonical" href="https://example.test/registry.html">
        </head></html>"""
        self.rows = [
            {
                "id": "abilene",
                "name": "Stargate Abilene",
                "operator": "Crusoe",
                "city": "Abilene",
                "county": ["Taylor"],
                "state": "TX",
                "lat": 1,
                "lng": 2,
                "stage": "live",
                "gross_current_mw": 100,
                "participants": [{"layer": "power"}],
                "site_dates": [{"key": "live"}],
                "sources": [
                    {
                        "label": "Primary filing",
                        "url": "https://source.test/a",
                        "type": "primary",
                    }
                ],
            },
            {
                "id": "microsoft-abilene",
                "name": "Crusoe Abilene AI Factory Campus (Microsoft)",
                "operator": "Crusoe",
                "city": "Abilene",
                "county": ["Taylor"],
                "state": "TX",
                "lat": 3,
                "lng": 4,
                "stage": "building",
                "participants": [],
                "site_dates": [],
                "sources": [],
            },
        ]
        self.facilities = {
            "facilities": [
                {
                    "slug": "crusoe-stargate-abilene",
                    "name": "Crusoe Stargate Abilene",
                    "aliases": ["Longhorn Data Center"],
                    "state": "TX",
                    "geo": "(-99,32)",
                    "developer": "Crusoe / Lancium",
                    "offtaker": "OpenAI via Oracle",
                    "status": "operating",
                    "first_power": "2025-09-01",
                    "unit": [{"model": "LM2500"}],
                    "sources": [{"url": "https://source.test/b"}],
                }
            ]
        }

    def test_capture_is_benchmark_only_and_does_not_copy_capacity_values(self):
        targets, manifest = build_capture(
            self.landing,
            json.dumps(self.rows).encode(),
            captured_at="2026-07-14T18:16:23Z",
            landing_headers={"Date": "Tue, 14 Jul 2026 18:15:09 GMT"},
        )
        self.assertEqual(manifest["classification"], CLASSIFICATION)
        self.assertEqual(len(targets["targets"]), 2)
        first = targets["targets"][0]
        self.assertEqual(first["classification"], CLASSIFICATION)
        self.assertTrue(first["source_field_presence"]["capacity_disclosed"])
        self.assertNotIn("gross_current_mw", json.dumps(first))
        self.assertEqual(
            manifest["landing_page"]["http_date"],
            "Tue, 14 Jul 2026 18:15:09 GMT",
        )

    def test_capture_rejects_non_supabase_endpoint(self):
        landing = """
        const SUPA_URL = 'http://127.0.0.1:5432';
        const REGISTRY_KEY = 'public-key';
        """
        with self.assertRaisesRegex(ValueError, "HTTPS supabase.co"):
            _extract_public_endpoint(landing)

    def test_resolution_is_deterministic_and_conservative(self):
        targets, _ = build_capture(
            self.landing,
            json.dumps(self.rows).encode(),
            captured_at="2026-07-14T18:16:23Z",
        )
        resolutions, gap_report = resolve_targets(
            targets,
            self.facilities,
            {"announcements": []},
            btw_mirror_commit="abc123",
        )
        by_id = {
            item["benchmark_id"]: item for item in resolutions["resolutions"]
        }
        resolved = by_id["neocloud-buildout-registry:abilene"]
        separate = by_id["neocloud-buildout-registry:microsoft-abilene"]
        self.assertEqual(resolved["resolution_state"], "resolved_btw_facility")
        self.assertEqual(
            resolved["resolved_entity"]["slug"], "crusoe-stargate-abilene"
        )
        self.assertEqual(separate["resolution_state"], "unresolved")
        self.assertEqual(gap_report["summary"]["targets"], 2)
        self.assertEqual(gap_report["summary"]["resolved_btw_facility"], 1)

    def test_announcement_leads_never_resolve_identity(self):
        targets, _ = build_capture(
            self.landing,
            json.dumps(self.rows[:1]).encode(),
            captured_at="2026-07-14T18:16:23Z",
        )
        resolutions, _ = resolve_targets(
            targets,
            {"facilities": []},
            {
                "announcements": [
                    {
                        "name": "Stargate Abilene Power Project",
                        "state": "TX",
                        "county": "Taylor County",
                        "source": {"url": "https://source.test/power"},
                    }
                ]
            },
            btw_mirror_commit="abc123",
        )
        result = resolutions["resolutions"][0]
        self.assertEqual(result["resolution_state"], "unresolved")
        self.assertTrue(result["announcement_leads"])

    def test_artifact_verifier_closes_the_50_target_contract(self):
        targets, manifest = build_capture(
            self.landing,
            json.dumps(self.rows).encode(),
            captured_at="2026-07-14T18:16:23Z",
        )
        resolutions, gap_report = resolve_targets(
            targets,
            self.facilities,
            {"announcements": []},
            btw_mirror_commit="abc123",
        )
        with tempfile.TemporaryDirectory() as directory:
            artifact_dir = Path(directory)
            target_sha = write_json(artifact_dir / "targets.json", targets)
            manifest["normalized_targets"] = {
                "path": "targets.json",
                "row_count": 2,
                "sha256": target_sha,
            }
            manifest["registry_response"]["row_count"] = 2
            write_json(artifact_dir / "manifest.json", manifest)
            write_json(artifact_dir / "resolution.json", resolutions)
            write_json(artifact_dir / "gap-report.json", gap_report)
            summary = verify_artifacts(artifact_dir, expected_count=2)
            self.assertEqual(summary["resolved"], 1)
            self.assertEqual(summary["unresolved"], 1)
            with self.assertRaisesRegex(ValueError, "expected 50"):
                verify_artifacts(artifact_dir, expected_count=50)


if __name__ == "__main__":
    unittest.main()
