import copy
import unittest

from engine.sources.registry import verify_registry


class SourceRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = {
            "schema": "computerecord.source-registry.v1",
            "classification": "operational_primary_source_registry",
            "sealed_at": "2026-07-25T22:45:33Z",
            "authority": {
                "publisher": "U.S. Securities and Exchange Commission",
                "documentation_url": (
                    "https://www.sec.gov/search-filings/"
                    "edgar-application-programming-interfaces"
                ),
                "company_index_url": (
                    "https://www.sec.gov/files/"
                    "company_tickers_exchange.json"
                ),
                "company_index_sha256": "a" * 64,
                "company_index_retrieved_at": "2026-07-25T22:45:33Z",
            },
            "policy": {
                "competitor_sources_allowed": False,
                "discovery_creates_facts": False,
                "filing_document_capture_required": True,
                "registry_is_public": True,
            },
            "sources": [self.source("0001144879", "Applied Digital Corp.")],
        }

    @staticmethod
    def source(cik, name):
        return {
            "source_id": f"sec-submissions:cik-{cik}",
            "publisher": {
                "cik": cik,
                "name": name,
                "tickers": ["APLD"],
            },
            "jurisdiction": "US-federal",
            "source_type": "sec_company_submissions",
            "url": f"https://data.sec.gov/submissions/CIK{cik}.json",
            "adapter": "sec_submissions_v1",
            "schedule": {"interval_seconds": 600, "jitter_seconds": 60},
            "tier": 1,
            "expected_change_interval_seconds": 2592000,
            "maximum_staleness_seconds": 900,
            "coverage_scope": {
                "candidate_type": "filing",
                "forms": ["8-K", "10-Q", "10-K"],
            },
        }

    def test_registry_accepts_exact_contract(self):
        self.assertEqual(
            verify_registry(self.registry, expected_sources=1)["sources"], 1
        )

    def test_registry_rejects_competitor_sources(self):
        registry = copy.deepcopy(self.registry)
        registry["policy"]["competitor_sources_allowed"] = True
        with self.assertRaisesRegex(ValueError, "discovery-only boundary"):
            verify_registry(registry)

    def test_registry_rejects_non_official_url(self):
        registry = copy.deepcopy(self.registry)
        registry["sources"][0]["url"] = "https://example.com/feed.json"
        with self.assertRaisesRegex(ValueError, "does not match its CIK"):
            verify_registry(registry)

    def test_registry_rejects_duplicate_cik(self):
        registry = copy.deepcopy(self.registry)
        registry["sources"].append(copy.deepcopy(registry["sources"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate watcher"):
            verify_registry(registry)

    def test_registry_rejects_slow_tier_one_schedule(self):
        registry = copy.deepcopy(self.registry)
        registry["sources"][0]["schedule"]["interval_seconds"] = 3600
        with self.assertRaisesRegex(ValueError, "schedule drift"):
            verify_registry(registry)


if __name__ == "__main__":
    unittest.main()
