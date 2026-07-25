import copy
import unittest

from engine.sources.schedule import build_schedule, verify_schedule


class WatcherScheduleTest(unittest.TestCase):
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
            "sources": [
                self.source("0000000001"),
                self.source("0000000002"),
            ],
        }

    @staticmethod
    def source(cik):
        return {
            "source_id": f"sec-submissions:cik-{cik}",
            "publisher": {
                "cik": cik,
                "name": f"Company {cik}",
                "tickers": [f"T{cik[-1]}"],
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
                "forms": ["8-K"],
            },
        }

    def test_schedule_spreads_watchers_evenly(self):
        schedule = build_schedule(self.registry)
        self.assertEqual(
            [row["phase_offset_seconds"] for row in schedule["watchers"]],
            [0, 300],
        )
        self.assertEqual(
            verify_schedule(schedule, self.registry)["phase_collisions"], 0
        )

    def test_schedule_is_independent_of_input_order(self):
        reversed_registry = copy.deepcopy(self.registry)
        reversed_registry["sources"].reverse()
        # The registry verifier deliberately rejects unsorted input.
        with self.assertRaisesRegex(ValueError, "sorted"):
            build_schedule(reversed_registry)

    def test_tampered_phase_is_rejected(self):
        schedule = build_schedule(self.registry)
        schedule["watchers"][0]["phase_offset_seconds"] = 42
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            verify_schedule(schedule, self.registry)

    def test_registry_change_invalidates_schedule(self):
        schedule = build_schedule(self.registry)
        changed = copy.deepcopy(self.registry)
        changed["sources"][0]["maximum_staleness_seconds"] = 901
        with self.assertRaises(ValueError):
            verify_schedule(schedule, changed)


if __name__ == "__main__":
    unittest.main()
