"""Build and verify a deterministic watcher schedule from the source registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from engine.sources.registry import load_json, verify_registry

SCHEMA = "computerecord.watcher-schedule.v1"
CLASSIFICATION = "operational_watcher_schedule"
SCHEDULER_VERSION = "tiered-phase-v1"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def build_schedule(registry: dict[str, Any]) -> dict[str, Any]:
    verify_registry(registry)
    sources = registry["sources"]
    by_interval: dict[int, list[dict[str, Any]]] = {}
    for source in sources:
        interval = source["schedule"]["interval_seconds"]
        by_interval.setdefault(interval, []).append(source)

    entries = []
    for interval, cohort in sorted(by_interval.items()):
        cohort = sorted(cohort, key=lambda source: source["source_id"])
        slot_width = interval // len(cohort)
        if slot_width < 1:
            raise ValueError("watcher cohort is too large for its interval")
        for index, source in enumerate(cohort):
            entries.append(
                {
                    "source_id": source["source_id"],
                    "tier": source["tier"],
                    "interval_seconds": interval,
                    "phase_offset_seconds": index * slot_width,
                    "jitter_seconds": source["schedule"]["jitter_seconds"],
                    "freshness_deadline_seconds": source[
                        "maximum_staleness_seconds"
                    ],
                }
            )

    entries.sort(key=lambda entry: entry["source_id"])
    return {
        "schema": SCHEMA,
        "classification": CLASSIFICATION,
        "scheduler_version": SCHEDULER_VERSION,
        "input": {
            "registry_schema": registry["schema"],
            "registry_sha256": sha256_json(registry),
        },
        "policy": {
            "catch_up_after_missed_slot": True,
            "concurrent_runs_per_source": 1,
            "discovery_only": True,
            "schedule_uses_wall_clock_utc": True,
        },
        "watchers": entries,
    }


def verify_schedule(
    schedule: dict[str, Any], registry: dict[str, Any]
) -> dict[str, int]:
    expected = build_schedule(registry)
    if schedule != expected:
        raise ValueError("watcher schedule does not reproduce from registry")
    offsets = {
        (entry["interval_seconds"], entry["phase_offset_seconds"])
        for entry in schedule["watchers"]
    }
    if len(offsets) != len(schedule["watchers"]):
        raise ValueError("watcher schedule contains phase collisions")
    return {
        "watchers": len(schedule["watchers"]),
        "interval_cohorts": len(
            {entry["interval_seconds"] for entry in schedule["watchers"]}
        ),
        "phase_collisions": 0,
    }


def build_command(args: argparse.Namespace) -> None:
    write_json(
        Path(args.output),
        build_schedule(load_json(Path(args.registry))),
    )


def verify_command(args: argparse.Namespace) -> None:
    result = verify_schedule(
        load_json(Path(args.schedule)),
        load_json(Path(args.registry)),
    )
    print(
        "watcher schedule verification: "
        f"{result['watchers']} watchers, "
        f"{result['interval_cohorts']} interval cohort, "
        f"{result['phase_collisions']} phase collisions"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--registry", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(func=build_command)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--registry", required=True)
    verify.add_argument("--schedule", required=True)
    verify.set_defaults(func=verify_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
