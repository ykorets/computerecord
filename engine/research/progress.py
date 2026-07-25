"""Build current research progress from immutable queues, receipts, and decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.archive.capture import load_json, verify_batch_manifest
from engine.research.decision import verify_decision

SCHEMA = "computerecord.research-progress.v1"
CLASSIFICATION = "generated_research_progress"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _utc_timestamp(value: str) -> None:
    if not value.endswith("Z"):
        raise ValueError("progress as_of must be an ISO 8601 UTC timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("progress as_of must include a timezone")


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def build_progress(
    *,
    root: Path,
    queue_path: Path,
    capture_manifest_paths: list[Path],
    review_packet_dirs: list[Path],
    as_of: str,
) -> dict[str, Any]:
    root = root.resolve()
    _utc_timestamp(as_of)
    queue_path = queue_path.resolve()
    queue_path.relative_to(root)
    queue = load_json(queue_path)
    if queue.get("classification") != "research_queue":
        raise ValueError("progress input must be the sealed research queue")
    tasks = {task["task_id"]: task for task in queue["tasks"]}

    captured_by_task: dict[str, dict[str, Any]] = {}
    capture_inputs = []
    for manifest_path in sorted(
        (path.resolve() for path in capture_manifest_paths), key=str
    ):
        manifest_path.relative_to(root)
        verify_batch_manifest(manifest_path, root=root)
        manifest = load_json(manifest_path)
        capture_inputs.append(
            {
                "path": _relative(root, manifest_path),
                "sha256": sha256_bytes(manifest_path.read_bytes()),
            }
        )
        for receipt in manifest["receipts"]:
            task_id = receipt["intake_task_id"]
            if task_id in captured_by_task:
                raise ValueError("progress inputs capture one task more than once")
            captured_by_task[task_id] = receipt

    reviewed_by_task: dict[str, dict[str, Any]] = {}
    review_inputs = []
    source_to_task = {
        receipt["source_sha256"]: task_id
        for task_id, receipt in captured_by_task.items()
    }
    for packet_dir in sorted(
        (path.resolve() for path in review_packet_dirs), key=str
    ):
        packet_dir.relative_to(root)
        spec = load_json(packet_dir / "decision-spec.json")
        review = load_json(packet_dir / "review-manifest.json")
        seeds = load_json(packet_dir / "entity-seeds.json")
        decision = load_json(packet_dir / "review-decision.json")
        result = verify_decision(decision, spec, review, seeds)
        task_id = source_to_task.get(review["inputs"]["source_sha256"])
        if not task_id:
            raise ValueError("review decision lacks a captured source task")
        if task_id in reviewed_by_task:
            raise ValueError("progress inputs review one task more than once")
        reviewed_by_task[task_id] = {
            "approved_entity_candidates": result[
                "approved_entity_candidates"
            ],
            "blocked_normalizations": result["blocked_normalizations"],
            "decision_id": decision["decision_id"],
        }
        review_inputs.append(
            {
                "path": _relative(root, packet_dir),
                "review_manifest_sha256": sha256_bytes(
                    (packet_dir / "review-manifest.json").read_bytes()
                ),
                "review_decision_sha256": sha256_bytes(
                    (packet_dir / "review-decision.json").read_bytes()
                ),
            }
        )

    rows = []
    for task_id, task in sorted(tasks.items()):
        capture = captured_by_task.get(task_id)
        review = reviewed_by_task.get(task_id)
        rows.append(
            {
                "task_id": task_id,
                "benchmark_target_id": task["benchmark_id"],
                "priority": task["priority"],
                "document_state": (
                    "captured_private" if capture else "not_captured"
                ),
                "source_sha256": capture["source_sha256"] if capture else None,
                "claim_review_state": (
                    "reviewed_source_assertions"
                    if review
                    else "not_reviewed"
                ),
                "entity_seed_state": (
                    "approved_for_staging"
                    if review
                    else "blocked_pending_independent_evidence"
                ),
                "approved_entity_candidates": (
                    review["approved_entity_candidates"] if review else 0
                ),
                "blocked_normalizations": (
                    review["blocked_normalizations"] if review else 0
                ),
                "review_decision_id": (
                    review["decision_id"] if review else None
                ),
            }
        )
    summary = {
        "tasks": len(rows),
        "captured_documents": len(captured_by_task),
        "reviewed_tasks": len(reviewed_by_task),
        "approved_entity_candidates": sum(
            row["approved_entity_candidates"] for row in rows
        ),
        "blocked_normalizations": sum(
            row["blocked_normalizations"] for row in rows
        ),
        "database_rows_written": 0,
        "canonical_facts_created": 0,
    }
    return {
        "schema": SCHEMA,
        "classification": CLASSIFICATION,
        "as_of": as_of,
        "inputs": {
            "queue": {
                "path": _relative(root, queue_path),
                "sha256": sha256_bytes(queue_path.read_bytes()),
            },
            "capture_manifests": capture_inputs,
            "review_packets": review_inputs,
        },
        "policy": {
            "database_writes_allowed": False,
            "facts_created": False,
            "projection_only": True,
        },
        "summary": summary,
        "tasks": rows,
    }


def _build_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return build_progress(
        root=Path(args.root),
        queue_path=Path(args.queue),
        capture_manifest_paths=[Path(path) for path in args.capture_manifest],
        review_packet_dirs=[Path(path) for path in args.review_packet],
        as_of=args.as_of,
    )


def build_command(args: argparse.Namespace) -> None:
    write_json(Path(args.output), _build_from_args(args))


def verify_command(args: argparse.Namespace) -> None:
    actual = load_json(Path(args.progress))
    expected = _build_from_args(args)
    if actual != expected:
        raise ValueError("research progress does not reproduce from inputs")
    summary = actual["summary"]
    print(
        "research progress verification: "
        f"{summary['tasks']} tasks, "
        f"{summary['captured_documents']} captured, "
        f"{summary['reviewed_tasks']} reviewed, "
        f"{summary['approved_entity_candidates']} entity candidates approved"
    )


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--capture-manifest", action="append", default=[])
    parser.add_argument("--review-packet", action="append", default=[])
    parser.add_argument("--as-of", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    _common(build)
    build.add_argument("--output", required=True)
    build.set_defaults(func=build_command)
    verify = subparsers.add_parser("verify")
    _common(verify)
    verify.add_argument("--progress", required=True)
    verify.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
