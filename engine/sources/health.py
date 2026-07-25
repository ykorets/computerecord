"""Observe registered sources and build a deterministic watcher health report."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from engine.sources.registry import load_json, verify_registry
from engine.sources.schedule import canonical_json_bytes, verify_schedule

OBSERVATION_SCHEMA = "computerecord.source-observation-batch.v1"
HEALTH_SCHEMA = "computerecord.source-health-report.v1"
OBSERVATION_CLASSIFICATION = "operational_source_observations"
HEALTH_CLASSIFICATION = "operational_source_health"
USER_AGENT = (
    "TheComputeRecord/0.1 "
    "(+https://computerecord.com; contact: Yaro Korets)"
)
MAXIMUM_RESPONSE_BYTES = 10 * 1024 * 1024


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO 8601 UTC timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def fetch_sec_submissions(source: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        source["url"],
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(MAXIMUM_RESPONSE_BYTES + 1)
        final_url = response.geturl()
        status = getattr(response, "status", None) or response.getcode()
        content_type = (
            (response.headers.get("content-type") or "")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
    if final_url != source["url"]:
        raise ValueError("SEC submissions endpoint redirected")
    if status != 200:
        raise ValueError(f"SEC submissions endpoint returned HTTP {status}")
    if len(payload) > MAXIMUM_RESPONSE_BYTES:
        raise ValueError("SEC submissions response exceeds size limit")
    if content_type not in {"application/json", "application/octet-stream"}:
        raise ValueError("SEC submissions endpoint returned non-JSON content")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("SEC submissions response is not valid JSON") from error
    response_cik = str(document.get("cik") or "").zfill(10)
    if response_cik != source["publisher"]["cik"]:
        raise ValueError("SEC submissions response CIK mismatch")
    return {
        "content_type": content_type,
        "http_status": status,
        "response_sha256": sha256_bytes(payload),
        "size_bytes": len(payload),
        "validated_cik": response_cik,
    }


def observe_sources(
    registry: dict[str, Any],
    observed_at: str,
    *,
    fetcher: Callable[[dict[str, Any]], dict[str, Any]] = fetch_sec_submissions,
    previous_response_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    verify_registry(registry)
    parse_utc(observed_at, "observed_at")
    previous_response_hashes = previous_response_hashes or {}
    observations = []
    for source in registry["sources"]:
        source_id = source["source_id"]
        observation_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                (
                    "https://computerecord.com/id/source-observation/"
                    f"{source_id}/{observed_at}"
                ),
            )
        )
        try:
            response = fetcher(source)
            previous_hash = previous_response_hashes.get(source_id)
            if previous_hash is None:
                change_state = "baseline"
            elif previous_hash == response["response_sha256"]:
                change_state = "unchanged"
            else:
                change_state = "changed"
            observations.append(
                {
                    "observation_id": observation_id,
                    "source_id": source_id,
                    "checked_at": observed_at,
                    "outcome": "success",
                    "change_state": change_state,
                    "response": response,
                }
            )
        except (OSError, TimeoutError, ValueError) as error:
            observations.append(
                {
                    "observation_id": observation_id,
                    "source_id": source_id,
                    "checked_at": observed_at,
                    "outcome": "failure",
                    "change_state": "unknown",
                    "failure": {
                        "error_type": type(error).__name__,
                    },
                }
            )
    return {
        "schema": OBSERVATION_SCHEMA,
        "classification": OBSERVATION_CLASSIFICATION,
        "observed_at": observed_at,
        "input": {
            "registry_schema": registry["schema"],
            "registry_sha256": sha256_json(registry),
        },
        "policy": {
            "facts_created": False,
            "raw_responses_committed": False,
            "response_hashes_only": True,
        },
        "observations": observations,
    }


def verify_observation_batch(
    batch: dict[str, Any],
    registry: dict[str, Any],
    *,
    require_all_successful: bool = False,
) -> dict[str, int]:
    verify_registry(registry)
    if batch.get("schema") != OBSERVATION_SCHEMA:
        raise ValueError("unknown source observation schema")
    if batch.get("classification") != OBSERVATION_CLASSIFICATION:
        raise ValueError("source observation classification drift")
    parse_utc(batch.get("observed_at"), "observed_at")
    if batch.get("input") != {
        "registry_schema": registry["schema"],
        "registry_sha256": sha256_json(registry),
    }:
        raise ValueError("source observations do not pin the registry")
    if batch.get("policy") != {
        "facts_created": False,
        "raw_responses_committed": False,
        "response_hashes_only": True,
    }:
        raise ValueError("source observations escaped operational metadata")
    expected_ids = [source["source_id"] for source in registry["sources"]]
    actual_ids = [
        observation["source_id"] for observation in batch.get("observations") or []
    ]
    if actual_ids != expected_ids:
        raise ValueError("source observations must cover the exact registry")
    successes = 0
    failures = 0
    for observation in batch["observations"]:
        source_id = observation["source_id"]
        expected_observation_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                (
                    "https://computerecord.com/id/source-observation/"
                    f"{source_id}/{batch['observed_at']}"
                ),
            )
        )
        if (
            observation.get("observation_id") != expected_observation_id
            or observation.get("checked_at") != batch["observed_at"]
        ):
            raise ValueError("source observation identity drift")
        if observation.get("outcome") == "success":
            successes += 1
            response = observation.get("response") or {}
            if (
                response.get("http_status") != 200
                or response.get("validated_cik")
                != source_id.removeprefix("sec-submissions:cik-")
                or len(response.get("response_sha256") or "") != 64
                or not isinstance(response.get("size_bytes"), int)
                or response["size_bytes"] < 2
                or observation.get("change_state")
                not in {"baseline", "unchanged", "changed"}
                or "failure" in observation
            ):
                raise ValueError("successful source observation is invalid")
        elif observation.get("outcome") == "failure":
            failures += 1
            if (
                observation.get("change_state") != "unknown"
                or not (observation.get("failure") or {}).get("error_type")
                or "response" in observation
            ):
                raise ValueError("failed source observation is invalid")
        else:
            raise ValueError("unknown source observation outcome")
    if require_all_successful and failures:
        raise ValueError(f"source observation batch has {failures} failures")
    return {"observations": len(actual_ids), "successes": successes, "failures": failures}


def build_health_report(
    registry: dict[str, Any],
    schedule: dict[str, Any],
    batch: dict[str, Any],
    *,
    as_of: str,
) -> dict[str, Any]:
    verify_schedule(schedule, registry)
    verify_observation_batch(batch, registry)
    as_of_time = parse_utc(as_of, "as_of")
    schedule_by_id = {
        watcher["source_id"]: watcher for watcher in schedule["watchers"]
    }
    rows = []
    for observation in batch["observations"]:
        checked_at = parse_utc(observation["checked_at"], "checked_at")
        age_seconds = int((as_of_time - checked_at).total_seconds())
        if age_seconds < 0:
            raise ValueError("health report cannot predate observations")
        deadline = schedule_by_id[observation["source_id"]][
            "freshness_deadline_seconds"
        ]
        if observation["outcome"] == "failure":
            status = "watcher_failed"
            last_success_at = None
        elif age_seconds > deadline:
            status = "stale"
            last_success_at = observation["checked_at"]
        elif observation["change_state"] == "unchanged":
            status = "source_silent_healthy"
            last_success_at = observation["checked_at"]
        else:
            status = "healthy"
            last_success_at = observation["checked_at"]
        rows.append(
            {
                "source_id": observation["source_id"],
                "status": status,
                "last_checked_at": observation["checked_at"],
                "last_success_at": last_success_at,
                "seconds_since_check": age_seconds,
                "freshness_deadline_seconds": deadline,
                "change_state": observation["change_state"],
            }
        )
    status_counts = {
        status: sum(row["status"] == status for row in rows)
        for status in ("healthy", "source_silent_healthy", "watcher_failed", "stale")
    }
    return {
        "schema": HEALTH_SCHEMA,
        "classification": HEALTH_CLASSIFICATION,
        "as_of": as_of,
        "input": {
            "registry_sha256": sha256_json(registry),
            "schedule_sha256": sha256_json(schedule),
            "observation_batch_sha256": sha256_json(batch),
        },
        "sources": rows,
        "summary": {
            "sources": len(rows),
            **status_counts,
        },
    }


def observe_command(args: argparse.Namespace) -> None:
    write_json(
        Path(args.output),
        observe_sources(load_json(Path(args.registry)), args.observed_at),
    )


def verify_observations_command(args: argparse.Namespace) -> None:
    result = verify_observation_batch(
        load_json(Path(args.observations)),
        load_json(Path(args.registry)),
        require_all_successful=args.require_all_successful,
    )
    print(
        "source observation verification: "
        f"{result['observations']} observations, "
        f"{result['successes']} successes, "
        f"{result['failures']} failures"
    )


def health_command(args: argparse.Namespace) -> None:
    write_json(
        Path(args.output),
        build_health_report(
            load_json(Path(args.registry)),
            load_json(Path(args.schedule)),
            load_json(Path(args.observations)),
            as_of=args.as_of,
        ),
    )


def verify_health_command(args: argparse.Namespace) -> None:
    expected = build_health_report(
        load_json(Path(args.registry)),
        load_json(Path(args.schedule)),
        load_json(Path(args.observations)),
        as_of=args.as_of,
    )
    actual = load_json(Path(args.health))
    if actual != expected:
        raise ValueError("source health report does not reproduce")
    print(
        "source health verification: "
        f"{actual['summary']['sources']} sources, "
        f"{actual['summary']['healthy']} healthy, "
        f"{actual['summary']['watcher_failed']} failed, "
        f"{actual['summary']['stale']} stale"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    observe = subparsers.add_parser("observe")
    observe.add_argument("--registry", required=True)
    observe.add_argument("--observed-at", required=True)
    observe.add_argument("--output", required=True)
    observe.set_defaults(func=observe_command)
    verify_observations = subparsers.add_parser("verify-observations")
    verify_observations.add_argument("--registry", required=True)
    verify_observations.add_argument("--observations", required=True)
    verify_observations.add_argument("--require-all-successful", action="store_true")
    verify_observations.set_defaults(func=verify_observations_command)
    health = subparsers.add_parser("health")
    health.add_argument("--registry", required=True)
    health.add_argument("--schedule", required=True)
    health.add_argument("--observations", required=True)
    health.add_argument("--as-of", required=True)
    health.add_argument("--output", required=True)
    health.set_defaults(func=health_command)
    verify_health = subparsers.add_parser("verify-health")
    verify_health.add_argument("--registry", required=True)
    verify_health.add_argument("--schedule", required=True)
    verify_health.add_argument("--observations", required=True)
    verify_health.add_argument("--health", required=True)
    verify_health.add_argument("--as-of", required=True)
    verify_health.set_defaults(func=verify_health_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
