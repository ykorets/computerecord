import copy
import json
import unittest

from engine.sources.sec_submissions import (
    discover_candidates,
    verify_candidate_batch,
)


class SecSubmissionsAdapterTest(unittest.TestCase):
    def setUp(self):
        self.source = {
            "source_id": "sec-submissions:cik-0001144879",
            "publisher": {
                "cik": "0001144879",
                "name": "Applied Digital Corp.",
                "tickers": ["APLD"],
            },
            "coverage_scope": {
                "candidate_type": "filing",
                "forms": ["8-K", "10-Q", "10-K"],
            },
        }
        self.document = {
            "cik": "0001144879",
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0001493152-26-030333",
                        "0001628280-26-045215",
                        "0001493152-26-028993",
                    ],
                    "filingDate": [
                        "2026-06-26",
                        "2026-06-24",
                        "2026-06-17",
                    ],
                    "reportDate": [
                        "2026-06-26",
                        "2026-06-22",
                        "2026-03-10",
                    ],
                    "acceptanceDateTime": [
                        "2026-06-26T21:03:38.000Z",
                        "2026-06-24T20:37:27.000Z",
                        "2026-06-17T12:01:01.000Z",
                    ],
                    "form": ["8-K", "4", "8-K/A"],
                    "primaryDocument": [
                        "form8-k.htm",
                        "xslF345X06/wk-form4.xml",
                        "form8-ka.htm",
                    ],
                    "primaryDocDescription": ["8-K", "FORM 4", "8-K/A"],
                    "items": ["1.01,2.03,3.02,9.01", "", "1.01"],
                }
            },
        }
        self.payload = (
            json.dumps(self.document, sort_keys=True) + "\n"
        ).encode()
        self.discovered_at = "2026-07-25T23:00:00Z"

    def test_adapter_emits_relevant_forms_only(self):
        batch = discover_candidates(
            self.source,
            self.payload,
            discovered_at=self.discovered_at,
        )
        self.assertEqual(
            [candidate["form"] for candidate in batch["candidates"]],
            ["8-K", "8-K/A"],
        )
        self.assertTrue(
            batch["candidates"][0]["primary_document_url"].startswith(
                "https://www.sec.gov/Archives/edgar/data/1144879/"
            )
        )

    def test_cursor_emits_only_newer_relevant_filings(self):
        batch = discover_candidates(
            self.source,
            self.payload,
            discovered_at=self.discovered_at,
            after_accession="0001493152-26-028993",
        )
        self.assertEqual(len(batch["candidates"]), 1)
        self.assertEqual(
            batch["input"]["next_accession"], "0001493152-26-030333"
        )

    def test_missing_cursor_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "cursor is absent"):
            discover_candidates(
                self.source,
                self.payload,
                discovered_at=self.discovered_at,
                after_accession="0000000000-00-000000",
            )

    def test_cik_mismatch_is_rejected(self):
        document = copy.deepcopy(self.document)
        document["cik"] = "9999999999"
        payload = json.dumps(document).encode()
        with self.assertRaisesRegex(ValueError, "CIK mismatch"):
            discover_candidates(
                self.source,
                payload,
                discovered_at=self.discovered_at,
            )

    def test_unequal_recent_arrays_are_rejected(self):
        document = copy.deepcopy(self.document)
        document["filings"]["recent"]["form"].pop()
        payload = json.dumps(document).encode()
        with self.assertRaisesRegex(ValueError, "unequal lengths"):
            discover_candidates(
                self.source,
                payload,
                discovered_at=self.discovered_at,
            )

    def test_candidate_batch_reproduces(self):
        batch = discover_candidates(
            self.source,
            self.payload,
            discovered_at=self.discovered_at,
            after_accession="0001493152-26-028993",
        )
        result = verify_candidate_batch(
            batch,
            self.source,
            self.payload,
            discovered_at=self.discovered_at,
            after_accession="0001493152-26-028993",
        )
        self.assertEqual(result["candidates"], 1)


if __name__ == "__main__":
    unittest.main()
