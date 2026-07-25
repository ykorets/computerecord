import json
import tempfile
import unittest
from pathlib import Path

from engine.research.progress import build_progress


class ResearchProgressTest(unittest.TestCase):
    def test_empty_progress_preserves_sealed_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "queue.json"
            queue = {
                "classification": "research_queue",
                "tasks": [
                    {
                        "task_id": "task:a",
                        "benchmark_id": "target:a",
                        "priority": "p0",
                    }
                ],
            }
            queue_path.write_text(json.dumps(queue), encoding="utf-8")
            progress = build_progress(
                root=root,
                queue_path=queue_path,
                capture_manifest_paths=[],
                review_packet_dirs=[],
                as_of="2026-07-25T23:00:00Z",
            )
            self.assertEqual(progress["summary"]["tasks"], 1)
            self.assertEqual(progress["summary"]["captured_documents"], 0)
            self.assertEqual(
                progress["tasks"][0]["document_state"], "not_captured"
            )
            self.assertEqual(
                progress["tasks"][0]["entity_seed_state"],
                "blocked_pending_independent_evidence",
            )

    def test_progress_requires_sealed_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "queue.json"
            queue_path.write_text(
                json.dumps({"classification": "facts", "tasks": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "sealed research queue"):
                build_progress(
                    root=root,
                    queue_path=queue_path,
                    capture_manifest_paths=[],
                    review_packet_dirs=[],
                    as_of="2026-07-25T23:00:00Z",
                )

    def test_progress_timestamp_must_be_utc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "queue.json"
            queue_path.write_text(
                json.dumps(
                    {"classification": "research_queue", "tasks": []}
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "UTC"):
                build_progress(
                    root=root,
                    queue_path=queue_path,
                    capture_manifest_paths=[],
                    review_packet_dirs=[],
                    as_of="2026-07-25T23:00:00",
                )


if __name__ == "__main__":
    unittest.main()
