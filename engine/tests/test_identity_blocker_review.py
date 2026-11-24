import copy
import json
import unittest
from pathlib import Path

from engine.research.identity_blocker_review import build_review


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "research/m5/identity-blocker-review"
STAGING = ROOT / "research/m5/identity-staging"


def load(path: Path):
    return json.loads(path.read_text())


class IdentityBlockerReviewTests(unittest.TestCase):
    def setUp(self):
        self.spec = load(ARTIFACT / "spec.json")
        self.plan = load(STAGING / "plan.json")
        self.load_manifest = load(STAGING / "load-manifest.json")
        self.receipt = load(STAGING / "production-receipt.json")
        self.stage_sql_sha256 = self.receipt["stage_sql_sha256"]

    def test_review_reproduces_exactly(self):
        review = build_review(
            self.spec, self.plan, self.load_manifest, self.receipt,
            self.stage_sql_sha256,
        )
        self.assertEqual(review, load(ARTIFACT / "review.json"))
        self.assertEqual(review["summary"]["blocked_candidates_reviewed"], 5)
        self.assertEqual(review["summary"]["blockers_cleared"], 0)

    def test_rejects_missing_blocker(self):
        spec = copy.deepcopy(self.spec)
        spec["assessments"].pop()
        with self.assertRaisesRegex(ValueError, "exact blocked candidate set"):
            build_review(
                spec, self.plan, self.load_manifest, self.receipt,
                self.stage_sql_sha256,
            )

    def test_rejects_unstaged_evidence(self):
        spec = copy.deepcopy(self.spec)
        spec["assessments"][0]["support_claim_ids"] = ["not-staged"]
        with self.assertRaisesRegex(ValueError, "staged support claims"):
            build_review(
                spec, self.plan, self.load_manifest, self.receipt,
                self.stage_sql_sha256,
            )

    def test_rejects_promotion_permission(self):
        spec = copy.deepcopy(self.spec)
        spec["policy"]["promotion_allowed"] = True
        with self.assertRaisesRegex(ValueError, "review-only policy"):
            build_review(
                spec, self.plan, self.load_manifest, self.receipt,
                self.stage_sql_sha256,
            )


if __name__ == "__main__":
    unittest.main()
