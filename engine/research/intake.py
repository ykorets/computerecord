"""Build and verify the M3 independent-source intake queue.

The queue turns unresolved coverage-benchmark targets into research work. It
does not turn competitor links into evidence, documents, claims, entities, or
facts. Every lead remains explicitly unverified until it is independently
rediscovered and captured by the evidence pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any

QUEUE_SCHEMA = "computerecord.primary-source-intake.v1"
REPORT_SCHEMA = "computerecord.primary-source-intake-report.v1"
CLASSIFICATION = "research_queue"
INPUT_CLASSIFICATION = "benchmark_only"
LEAD_CLASSIFICATION = "unverified_benchmark_discovery_lead"
EVIDENCE_STATE = "not_captured"
SEED_STATE = "blocked_pending_independent_evidence"

FORBIDDEN_FACT_FIELDS = {
    "gross_current_mw",
    "gross_planned_mw",
    "critical_current_mw",
    "critical_planned_mw",
    "site_total_mw",
    "capacity_mw",
    "capacity",
    "fact",
    "claim",
    "document_id",
    "entity_id",
    "resolved_entity",
}


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> str:
    payload = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_all_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_all_keys(child))
        return keys
    return set()


def _validate_https_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError(f"research leads must be public HTTPS URLs: {value}")
    return value


def _lead_kind(url: str) -> str:
    hostname = (urllib.parse.urlparse(url).hostname or "").lower()
    if hostname == "sec.gov" or hostname.endswith(".sec.gov"):
        return "federal_filing"
    if hostname.endswith(".gov") or hostname.endswith(".us"):
        return "government_record"
    return "organization_publication"


def _priority(lead_kinds: list[str]) -> tuple[str, list[str]]:
    kinds = set(lead_kinds)
    if "federal_filing" in kinds:
        return "p0", ["federal filing lead available for independent lookup"]
    if "government_record" in kinds:
        return "p1", ["government record lead available for independent lookup"]
    return "p2", ["organization publication requires independent lookup"]


def build_queue(
    targets_document: dict[str, Any],
    resolution_document: dict[str, Any],
    *,
    targets_sha256: str,
    resolution_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if targets_document.get("classification") != INPUT_CLASSIFICATION:
        raise ValueError("targets input must be benchmark_only")
    if resolution_document.get("classification") != INPUT_CLASSIFICATION:
        raise ValueError("resolution input must be benchmark_only")

    target_rows = targets_document.get("targets") or []
    resolution_rows = resolution_document.get("resolutions") or []
    targets = {row["benchmark_id"]: row for row in target_rows}
    resolutions = {row["benchmark_id"]: row for row in resolution_rows}
    if len(targets) != len(target_rows):
        raise ValueError("benchmark target ids must be unique")
    if len(resolutions) != len(resolution_rows):
        raise ValueError("benchmark resolution ids must be unique")
    if set(targets) != set(resolutions):
        raise ValueError("targets and resolutions must contain the same ids")

    tasks = []
    for benchmark_id in sorted(targets):
        resolution = resolutions[benchmark_id]
        if resolution.get("resolution_state") != "unresolved":
            continue
        target = targets[benchmark_id]
        leads = []
        lead_kinds = []
        for lead in sorted(
            target.get("source_leads") or [],
            key=lambda row: (row.get("url") or "", row.get("label") or ""),
        ):
            if lead.get("classification") != "benchmark_discovery_lead":
                raise ValueError("input source must remain a benchmark discovery lead")
            url = _validate_https_url(lead["url"])
            kind = _lead_kind(url)
            lead_kinds.append(kind)
            leads.append(
                {
                    "classification": LEAD_CLASSIFICATION,
                    "label": lead.get("label"),
                    "reported_type_hint": lead.get("reported_type"),
                    "research_kind_hint": kind,
                    "url": url,
                }
            )
        priority, priority_reasons = _priority(lead_kinds)
        location = target.get("source_location") or {}
        identity = target.get("identity") or {}
        tasks.append(
            {
                "benchmark_id": benchmark_id,
                "classification": CLASSIFICATION,
                "discovery_leads": leads,
                "entity_seed_state": SEED_STATE,
                "evidence_state": EVIDENCE_STATE,
                "priority": priority,
                "priority_reasons": priority_reasons,
                "required_outputs": [
                    "independently_discovered_source_url",
                    "immutable_document_capture",
                    "rights_and_redistribution_decision",
                    "anchored_identity_claim",
                    "reviewed_entity_resolution_decision",
                ],
                "target_hint": {
                    "city": location.get("city"),
                    "counties": location.get("counties") or [],
                    "name": identity.get("name"),
                    "operator": identity.get("operator"),
                    "state": location.get("state"),
                },
                "task_id": "m3-primary-source-intake:"
                + target["source_record_id"],
            }
        )

    queue = {
        "schema": QUEUE_SCHEMA,
        "classification": CLASSIFICATION,
        "inputs": {
            "benchmark_classification": INPUT_CLASSIFICATION,
            "benchmark_schema": targets_document.get("schema"),
            "resolution_algorithm_version": resolution_document.get(
                "algorithm_version"
            ),
            "resolution_sha256": resolution_sha256,
            "targets_sha256": targets_sha256,
        },
        "policy": {
            "competitor_leads_are_evidence": False,
            "entity_creation_allowed": False,
            "fact_creation_allowed": False,
            "independent_rediscovery_required": True,
            "raw_document_required_before_extraction": True,
        },
        "tasks": tasks,
    }
    report = build_report(queue)
    return queue, report


def build_report(queue: dict[str, Any]) -> dict[str, Any]:
    priority_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    lead_kind_counts: Counter[str] = Counter()
    tasks_with_kind: dict[str, set[str]] = {}
    total_leads = 0

    for task in queue.get("tasks") or []:
        priority_counts[task["priority"]] += 1
        state_counts[task["target_hint"].get("state") or "unknown"] += 1
        task_kinds = {
            lead["research_kind_hint"] for lead in task.get("discovery_leads") or []
        }
        total_leads += len(task.get("discovery_leads") or [])
        for kind in task_kinds:
            tasks_with_kind.setdefault(kind, set()).add(task["task_id"])
        for lead in task.get("discovery_leads") or []:
            lead_kind_counts[lead["research_kind_hint"]] += 1

    return {
        "schema": REPORT_SCHEMA,
        "classification": CLASSIFICATION,
        "inputs": queue["inputs"],
        "summary": {
            "blocked_entity_seeds": len(queue.get("tasks") or []),
            "captured_documents": 0,
            "tasks": len(queue.get("tasks") or []),
            "unverified_discovery_leads": total_leads,
        },
        "by_priority": [
            {"priority": priority, "task_count": count}
            for priority, count in sorted(priority_counts.items())
        ],
        "by_state": [
            {"state": state, "task_count": count}
            for state, count in sorted(state_counts.items())
        ],
        "by_research_kind": [
            {
                "lead_count": lead_kind_counts[kind],
                "research_kind": kind,
                "task_count": len(tasks_with_kind.get(kind, set())),
            }
            for kind in sorted(lead_kind_counts)
        ],
    }


def verify_artifacts(
    artifact_dir: Path,
    targets_path: Path,
    resolution_path: Path,
    *,
    expected_tasks: int | None = None,
) -> dict[str, int]:
    queue = _load_json(artifact_dir / "queue.json")
    report = _load_json(artifact_dir / "report.json")
    targets = _load_json(targets_path)
    resolution = _load_json(resolution_path)

    if queue.get("schema") != QUEUE_SCHEMA or report.get("schema") != REPORT_SCHEMA:
        raise ValueError("unknown intake artifact schema")
    if (
        queue.get("classification") != CLASSIFICATION
        or report.get("classification") != CLASSIFICATION
    ):
        raise ValueError("intake artifacts must be research_queue")

    expected_inputs = {
        "benchmark_classification": INPUT_CLASSIFICATION,
        "benchmark_schema": targets.get("schema"),
        "resolution_algorithm_version": resolution.get("algorithm_version"),
        "resolution_sha256": sha256_bytes(resolution_path.read_bytes()),
        "targets_sha256": sha256_bytes(targets_path.read_bytes()),
    }
    if queue.get("inputs") != expected_inputs or report.get("inputs") != expected_inputs:
        raise ValueError("intake artifacts are not pinned to their exact inputs")

    expected_queue, expected_report = build_queue(
        targets,
        resolution,
        targets_sha256=expected_inputs["targets_sha256"],
        resolution_sha256=expected_inputs["resolution_sha256"],
    )
    if queue != expected_queue:
        raise ValueError("intake queue is not reproducible from benchmark inputs")
    if report != expected_report:
        raise ValueError("intake report is not reproducible from the queue")

    tasks = queue.get("tasks") or []
    if expected_tasks is not None and len(tasks) != expected_tasks:
        raise ValueError(
            f"expected {expected_tasks} intake tasks, found {len(tasks)}"
        )
    if _all_keys(queue) & FORBIDDEN_FACT_FIELDS:
        raise ValueError("canonical fact, claim, document, or entity fields leaked")
    if queue.get("policy") != {
        "competitor_leads_are_evidence": False,
        "entity_creation_allowed": False,
        "fact_creation_allowed": False,
        "independent_rediscovery_required": True,
        "raw_document_required_before_extraction": True,
    }:
        raise ValueError("intake policy drift")

    task_ids = [task["task_id"] for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("intake task ids must be unique")
    for task in tasks:
        if (
            task.get("classification") != CLASSIFICATION
            or task.get("evidence_state") != EVIDENCE_STATE
            or task.get("entity_seed_state") != SEED_STATE
        ):
            raise ValueError("intake task escaped its pre-evidence state")
        for lead in task.get("discovery_leads") or []:
            if lead.get("classification") != LEAD_CLASSIFICATION:
                raise ValueError("benchmark discovery lead was promoted")
            _validate_https_url(lead["url"])

    return {
        "tasks": len(tasks),
        "p0": sum(task["priority"] == "p0" for task in tasks),
        "p1": sum(task["priority"] == "p1" for task in tasks),
        "p2": sum(task["priority"] == "p2" for task in tasks),
    }


def build_command(args: argparse.Namespace) -> None:
    targets_path = Path(args.targets)
    resolution_path = Path(args.resolution)
    queue, report = build_queue(
        _load_json(targets_path),
        _load_json(resolution_path),
        targets_sha256=sha256_bytes(targets_path.read_bytes()),
        resolution_sha256=sha256_bytes(resolution_path.read_bytes()),
    )
    output_dir = Path(args.output_dir)
    write_json(output_dir / "queue.json", queue)
    write_json(output_dir / "report.json", report)


def verify_command(args: argparse.Namespace) -> None:
    summary = verify_artifacts(
        Path(args.artifact_dir),
        Path(args.targets),
        Path(args.resolution),
        expected_tasks=args.expected_tasks,
    )
    print(
        "intake verification: "
        f"{summary['tasks']} tasks "
        f"(p0={summary['p0']}, p1={summary['p1']}, p2={summary['p2']})"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--targets", required=True)
    build_parser.add_argument("--resolution", required=True)
    build_parser.add_argument("--output-dir", required=True)
    build_parser.set_defaults(func=build_command)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--artifact-dir", required=True)
    verify_parser.add_argument("--targets", required=True)
    verify_parser.add_argument("--resolution", required=True)
    verify_parser.add_argument("--expected-tasks", type=int)
    verify_parser.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
