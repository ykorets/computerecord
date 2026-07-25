import copy
import unittest

from engine.sources.health import (
    build_health_report,
    observe_sources,
    verify_observation_batch,
)
from engine.sources.schedule import build_schedule


class SourceHealthTest(unittest.TestCase):
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
            "sources": [self.source("0001144879")],
        }
        self.schedule = build_schedule(self.registry)
        self.observed_at = "2026-07-25T23:00:00Z"

    @staticmethod
    def source(cik):
        return {
            "source_id": f"sec-submissions:cik-{cik}",
            "publisher": {
                "cik": cik,
                "name": "Applied Digital Corp.",
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
                "forms": ["8-K"],
            },
        }

    @staticmethod
    def success(_source):
        return {
            "content_type": "application/json",
            "http_status": 200,
            "response_sha256": "a" * 64,
            "size_bytes": 100,
            "validated_cik": "0001144879",
        }

    def test_successful_observation_is_healthy(self):
        batch = observe_sources(
            self.registry, self.observed_at, fetcher=self.success
        )
        self.assertEqual(
            verify_observation_batch(batch, self.registry)["successes"], 1
        )
        report = build_health_report(
            self.registry,
            self.schedule,
            batch,
            as_of=self.observed_at,
        )
        self.assertEqual(report["sources"][0]["status"], "healthy")

    def test_unchanged_source_is_not_a_watcher_failure(self):
        batch = observe_sources(
            self.registry,
            self.observed_at,
            fetcher=self.success,
            previous_response_hashes={
                "sec-submissions:cik-0001144879": "a" * 64
            },
        )
        report = build_health_report(
            self.registry,
            self.schedule,
            batch,
            as_of=self.observed_at,
        )
        self.assertEqual(
            report["sources"][0]["status"], "source_silent_healthy"
        )

    def test_fetch_failure_is_visible(self):
        def fail(_source):
            raise TimeoutError("test")

        batch = observe_sources(
            self.registry, self.observed_at, fetcher=fail
        )
        report = build_health_report(
            self.registry,
            self.schedule,
            batch,
            as_of=self.observed_at,
        )
        self.assertEqual(report["sources"][0]["status"], "watcher_failed")
        self.assertIsNone(report["sources"][0]["last_success_at"])

    def test_old_success_is_stale(self):
        batch = observe_sources(
            self.registry, self.observed_at, fetcher=self.success
        )
        report = build_health_report(
            self.registry,
            self.schedule,
            batch,
            as_of="2026-07-25T23:15:01Z",
        )
        self.assertEqual(report["sources"][0]["status"], "stale")

    def test_tampered_registry_hash_is_rejected(self):
        batch = observe_sources(
            self.registry, self.observed_at, fetcher=self.success
        )
        batch["input"]["registry_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pin the registry"):
            verify_observation_batch(batch, self.registry)

    def test_missing_source_is_rejected(self):
        batch = observe_sources(
            self.registry, self.observed_at, fetcher=self.success
        )
        tampered = copy.deepcopy(batch)
        tampered["observations"] = []
        with self.assertRaisesRegex(ValueError, "exact registry"):
            verify_observation_batch(tampered, self.registry)


if __name__ == "__main__":
    unittest.main()
