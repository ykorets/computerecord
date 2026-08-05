import copy
import tempfile
import unittest
from pathlib import Path

from engine.archive.capture import write_json
from engine.research.normalizations import (
    build_packet,
    sha256_json,
    verify_packet,
)


class FactNormalizationsTest(unittest.TestCase):
    def setUp(self):
        self.claims = {
            "schema": "computerecord.anchored-source-assertions.v1",
            "classification": "validated_source_assertions",
            "document": {"source_sha256": "a" * 64},
            "claims": [{
                "claim_id": "claim-capacity",
                "claim_key": "reported_capacity",
                "value": {"type": "number", "number": 352, "unit": "MW"},
            }],
        }
        self.seeds = {
            "schema": "computerecord.entity-seed-candidates.v1",
            "classification": "staging_entity_seed_candidates",
            "candidates": [{
                "candidate_id": "campus-1",
                "candidate_key": "campus-beacon-point",
            }],
            "blocked_normalizations": [],
            "policy": {
                "database_writes_allowed": False,
                "fact_creation_allowed": False,
                "promotion_allowed": False,
            },
        }
        self.spec = {
            "schema": "computerecord.fact-normalization-spec.v1",
            "packet_key": "beacon-point-capacity-v1",
            "inputs": {
                "claims_sha256": sha256_json(self.claims),
                "entity_seeds_sha256": sha256_json(self.seeds),
            },
            "candidates": [{
                "normalization_key": "beacon-point-planned-it-capacity",
                "subject_candidate_key": "campus-beacon-point",
                "fact_kind": "capacity",
                "epistemic_type": "reported",
                "verification_state": "source_asserted",
                "period_start": None,
                "period_end": None,
                "issued_at": "2026-06-10T00:00:00Z",
                "forecast_horizon": None,
                "scenario": None,
                "support_claim_keys": ["reported_capacity"],
                "payload": {
                    "capacity_type": "planned_it_mw",
                    "capacity_basis": "planned_it",
                    "qualifier": "exact",
                    "value_mw": 352,
                    "scope_candidate_key": "campus-beacon-point",
                },
                "rationale": "The filing reports planned critical IT capacity.",
            }],
        }

    def test_packet_reproduces_with_explicit_epistemic_semantics(self):
        normalizations, review = build_packet(
            self.spec, self.claims, self.seeds
        )
        candidate = normalizations["candidates"][0]
        self.assertEqual(candidate["epistemic_type"], "reported")
        self.assertEqual(candidate["issued_at"], "2026-06-10T00:00:00Z")
        self.assertEqual(candidate["payload"]["scope_candidate_id"], "campus-1")
        self.assertFalse(normalizations["policy"]["fact_creation_allowed"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "fact-normalizations.json", normalizations)
            write_json(root / "normalization-review-manifest.json", review)
            write_json(root / "spec.json", self.spec)
            write_json(root / "claims.json", self.claims)
            write_json(root / "entity-seeds.json", self.seeds)
            result = verify_packet(
                root,
                root / "spec.json",
                root / "claims.json",
                root / "entity-seeds.json",
            )
            self.assertEqual(result["normalization_candidates"], 1)

    def test_epistemic_type_cannot_be_implicit(self):
        spec = copy.deepcopy(self.spec)
        del spec["candidates"][0]["epistemic_type"]
        with self.assertRaisesRegex(ValueError, "explicit epistemic_type"):
            build_packet(spec, self.claims, self.seeds)

    def test_all_measurement_fields_must_be_explicit(self):
        spec = copy.deepcopy(self.spec)
        del spec["candidates"][0]["period_start"]
        with self.assertRaisesRegex(ValueError, "explicit, including nulls"):
            build_packet(spec, self.claims, self.seeds)

    def test_source_claims_cannot_be_normalized_as_derived(self):
        spec = copy.deepcopy(self.spec)
        spec["candidates"][0]["epistemic_type"] = "derived"
        with self.assertRaisesRegex(ValueError, "cannot create derived"):
            build_packet(spec, self.claims, self.seeds)

    def test_forecast_requires_vintage_and_horizon(self):
        spec = copy.deepcopy(self.spec)
        candidate = spec["candidates"][0]
        candidate["epistemic_type"] = "forecast"
        candidate["issued_at"] = None
        with self.assertRaisesRegex(ValueError, "issued_at and forecast_horizon"):
            build_packet(spec, self.claims, self.seeds)

    def test_forecast_preserves_scenario_reference(self):
        spec = copy.deepcopy(self.spec)
        candidate = spec["candidates"][0]
        candidate["epistemic_type"] = "forecast"
        candidate["forecast_horizon"] = "2029-12-31"
        candidate["scenario"] = {"scenario_key": "base_case", "version": 2}
        normalizations, _ = build_packet(spec, self.claims, self.seeds)
        self.assertEqual(
            normalizations["candidates"][0]["scenario"],
            {"scenario_key": "base_case", "version": 2},
        )

    def test_nonforecast_cannot_carry_forecast_semantics(self):
        spec = copy.deepcopy(self.spec)
        spec["candidates"][0]["forecast_horizon"] = "2029-12-31"
        with self.assertRaisesRegex(ValueError, "only forecast"):
            build_packet(spec, self.claims, self.seeds)

    def test_period_shape_fails_closed(self):
        spec = copy.deepcopy(self.spec)
        candidate = spec["candidates"][0]
        candidate["period_start"] = "2027-12-31"
        candidate["period_end"] = "2027-01-01"
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            build_packet(spec, self.claims, self.seeds)

    def test_capacity_value_must_match_mw_source_claim(self):
        spec = copy.deepcopy(self.spec)
        spec["candidates"][0]["payload"]["value_mw"] = 500
        with self.assertRaisesRegex(ValueError, "not present in MW source claims"):
            build_packet(spec, self.claims, self.seeds)

    def test_capacity_type_and_basis_cannot_be_mixed(self):
        spec = copy.deepcopy(self.spec)
        spec["candidates"][0]["payload"]["capacity_basis"] = "critical_it"
        with self.assertRaisesRegex(ValueError, "type and basis"):
            build_packet(spec, self.claims, self.seeds)

    def test_tampered_input_hash_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["inputs"]["claims_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pinned artifacts"):
            build_packet(spec, self.claims, self.seeds)


if __name__ == "__main__":
    unittest.main()
