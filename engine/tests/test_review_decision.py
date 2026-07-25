import copy
import unittest

from engine.research.decision import (
    build_decision,
    sha256_json,
    verify_decision,
)


class ReviewDecisionTest(unittest.TestCase):
    def setUp(self):
        self.seeds = {
            "schema": "computerecord.entity-seed-candidates.v1",
            "classification": "staging_entity_seed_candidates",
            "candidates": [
                {"candidate_id": "candidate-a"},
                {"candidate_id": "candidate-b"},
            ],
            "blocked_normalizations": [{"claim_id": "blocked-capacity"}],
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
            "approved_entity_candidate_ids": [
                "candidate-a",
                "candidate-b",
            ],
            "blocked_normalization_claim_ids": ["blocked-capacity"],
            "github_review": {
                "repository": "ykorets/computerecord",
                "pull_request_number": 6,
                "pull_request_url": (
                    "https://github.com/ykorets/computerecord/pull/6"
                ),
                "approved_head_commit": "a" * 40,
                "merge_commit": "b" * 40,
                "merged_at": "2026-07-25T21:26:44Z",
                "merged_by": "ykorets",
            },
            "reviewer": {
                "display_name": "Yaro Korets",
                "github_login": "ykorets",
                "github_node_id": "user-1",
            },
            "rationale": "Approve only entity seeds.",
            "policy": {
                "database_writes_allowed": False,
                "fact_creation_allowed": False,
                "promotion_allowed": False,
                "staging_allowed": True,
            },
        }

    def test_decision_reproduces_from_exact_inputs(self):
        decision = build_decision(self.spec, self.review, self.seeds)
        result = verify_decision(
            decision, self.spec, self.review, self.seeds
        )
        self.assertEqual(result["approved_entity_candidates"], 2)
        self.assertEqual(result["blocked_normalizations"], 1)

    def test_decision_must_approve_exact_candidate_set(self):
        spec = copy.deepcopy(self.spec)
        spec["approved_entity_candidate_ids"].pop()
        with self.assertRaisesRegex(ValueError, "exact entity candidate set"):
            build_decision(spec, self.review, self.seeds)

    def test_blocked_capacity_cannot_be_approved(self):
        spec = copy.deepcopy(self.spec)
        spec["approved_entity_candidate_ids"].append("blocked-capacity")
        with self.assertRaisesRegex(ValueError, "exact entity candidate set"):
            build_decision(spec, self.review, self.seeds)

    def test_tampered_review_manifest_hash_is_rejected(self):
        review = copy.deepcopy(self.review)
        review["packet_key"] = "tampered"
        with self.assertRaisesRegex(ValueError, "pinned hashes"):
            build_decision(self.spec, review, self.seeds)

    def test_malformed_merge_commit_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["github_review"]["merge_commit"] = "not-a-commit"
        with self.assertRaisesRegex(ValueError, "merge_commit is invalid"):
            build_decision(spec, self.review, self.seeds)

    def test_decision_cannot_enable_database_writes(self):
        spec = copy.deepcopy(self.spec)
        spec["policy"]["database_writes_allowed"] = True
        with self.assertRaisesRegex(ValueError, "escaped entity-seed staging"):
            build_decision(spec, self.review, self.seeds)


if __name__ == "__main__":
    unittest.main()
