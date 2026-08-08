import copy
import unittest

from engine.research.decision import build_decision, sha256_json
from engine.research.staging import (
    build_load_manifest,
    build_staging_plan,
    render_load_sql,
    verify_staging_plan,
)


class IdentityStagingTest(unittest.TestCase):
    def setUp(self):
        self.claims = {
            "schema": "computerecord.anchored-source-assertions.v1",
            "classification": "validated_source_assertions",
            "claims": [{"claim_id": "claim-1"}],
        }
        self.seeds = {
            "schema": "computerecord.entity-seed-candidates.v1",
            "classification": "staging_entity_seed_candidates",
            "candidates": [{
                "candidate_id": "candidate-1",
                "candidate_key": "organization-example",
                "canonical_name": "Example",
                "entity_type": "organization",
                "proposed_attributes": {},
                "support_claim_ids": ["claim-1"],
            }],
            "blocked_normalizations": [],
            "policy": {
                "database_writes_allowed": False,
                "fact_creation_allowed": False,
                "promotion_allowed": False,
            },
        }
        self.review = {
            "schema": "computerecord.claim-review-manifest.v1",
            "classification": "proposed_review",
            "review_id": "review-1",
            "review_state": "proposed",
            "outputs": {
                "claim_ids": ["claim-1"],
                "claims_sha256": sha256_json(self.claims),
                "entity_seeds_sha256": sha256_json(self.seeds),
            },
            "policy": {
                "database_writes": False,
                "facts_created": False,
                "merge_requests_review_decision": True,
                "promotion_allowed": False,
                "source_assertions_only": True,
            },
        }
        self.spec = {
            "schema": "computerecord.review-decision-spec.v1",
            "review_id": "review-1",
            "input": {
                "review_manifest_sha256": sha256_json(self.review),
                "entity_seeds_sha256": sha256_json(self.seeds),
            },
            "decision": "approved_for_entity_seed_staging",
            "approved_entity_candidate_ids": ["candidate-1"],
            "blocked_normalization_claim_ids": [],
            "github_review": {
                "repository": "ykorets/computerecord",
                "pull_request_number": 1,
                "pull_request_url": "https://github.com/ykorets/computerecord/pull/1",
                "approved_head_commit": "a" * 40,
                "merge_commit": "b" * 40,
                "merged_at": "2026-08-06T00:00:00Z",
                "merged_by": "ykorets",
            },
            "reviewer": {
                "display_name": "Yaro Korets",
                "github_login": "ykorets",
                "github_node_id": "user-1",
            },
            "rationale": "Approve identities only.",
            "policy": {
                "database_writes_allowed": False,
                "fact_creation_allowed": False,
                "promotion_allowed": False,
                "staging_allowed": True,
            },
        }

    def packet(self):
        return {
            "packet_key": "example",
            "decision_spec": self.spec,
            "review_manifest": self.review,
            "entity_seeds": self.seeds,
            "review_decision": build_decision(self.spec, self.review, self.seeds),
            "claims": self.claims,
        }

    def test_plan_reproduces_and_preserves_canonical_blocker(self):
        plan = build_staging_plan([self.packet()])
        self.assertEqual(plan["summary"]["identity_candidates"], 1)
        self.assertEqual(plan["rows"][0]["canonical_blockers"], [
            "missing_organization_type"
        ])
        self.assertEqual(verify_staging_plan(plan, [self.packet()]), plan["summary"])

    def test_claim_support_cannot_escape_reviewed_claims(self):
        packet = self.packet()
        packet["entity_seeds"] = copy.deepcopy(self.seeds)
        packet["entity_seeds"]["candidates"][0]["support_claim_ids"] = ["other"]
        with self.assertRaises(ValueError):
            build_staging_plan([packet])

    def test_plan_cannot_be_changed_after_sealing(self):
        packet = self.packet()
        plan = build_staging_plan([packet])
        plan["policy"]["database_writes_allowed"] = True
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            verify_staging_plan(plan, [packet])

    def loadable_plan(self):
        plan = build_staging_plan([self.packet()])
        plan["batch_id"] = "00000000-0000-4000-8000-000000000001"
        plan["inputs"][0]["review_id"] = (
            "00000000-0000-4000-8000-000000000002"
        )
        plan["inputs"][0]["decision_id"] = (
            "00000000-0000-4000-8000-000000000003"
        )
        plan["rows"][0]["candidate_id"] = (
            "00000000-0000-4000-8000-000000000004"
        )
        plan["rows"][0]["source_decision_id"] = (
            "00000000-0000-4000-8000-000000000003"
        )
        plan["rows"][0]["support_claim_ids"] = [
            "00000000-0000-4000-8000-000000000005"
        ]
        return plan

    def test_load_request_is_staging_only_and_deterministic(self):
        plan = self.loadable_plan()
        manifest = build_load_manifest(plan, "projectref123")
        sql = render_load_sql(plan, manifest)
        self.assertEqual(sql, render_load_sql(plan, manifest))
        self.assertTrue(manifest["policy"]["database_writes_allowed"])
        self.assertTrue(manifest["policy"]["staging_tables_only"])
        self.assertFalse(manifest["policy"]["canonical_writes_allowed"])
        self.assertIn("insert into core.identity_staging_candidate", sql)
        self.assertIn("seal_identity_staging_batch", sql)
        self.assertNotIn("insert into core.entity", sql)
        self.assertNotIn("insert into core.fact_version", sql)
        self.assertNotIn("insert into compute.", sql)

    def test_load_manifest_drift_fails_closed(self):
        plan = self.loadable_plan()
        manifest = build_load_manifest(plan, "projectref123")
        manifest["expected"]["identity_candidates"] = 2
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            render_load_sql(plan, manifest)


if __name__ == "__main__":
    unittest.main()
