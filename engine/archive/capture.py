"""Fetch an official source, hash it, and seal a private archive receipt.

Fetching and sealing are separate on purpose. The fetch step writes exact
source bytes and retrieval metadata to a temporary directory. After those
bytes are uploaded to private object storage and downloaded again, the seal
step verifies the remote copy byte-for-byte before creating a repository
receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

RETRIEVAL_SCHEMA = "computerecord.source-retrieval.v1"
RECEIPT_SCHEMA = "computerecord.evidence-capture-receipt.v1"
BATCH_SCHEMA = "computerecord.evidence-capture-batch.v1"
CLASSIFICATION = "private_evidence_receipt"
BATCH_CLASSIFICATION = "private_evidence_manifest"
DEFAULT_MAX_BYTES = 25 * 1024 * 1024
DEFAULT_MIN_BYTES = 1024
USER_AGENT = (
    "TheComputeRecord/0.1 "
    "(+https://computerecord.com; public-records archive)"
)
CONTENT_EXTENSIONS = {
    "application/pdf": "pdf",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/plain": "txt",
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


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_timestamp(value: str, field: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return value


def _host_matches(hostname: str, allowed_host: str) -> bool:
    hostname = hostname.rstrip(".").lower()
    allowed_host = allowed_host.rstrip(".").lower()
    return hostname == allowed_host or hostname.endswith("." + allowed_host)


def validate_source_url_shape(url: str, allowed_host: str) -> str:
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.port
        or not _host_matches(hostname, allowed_host)
    ):
        raise ValueError(
            f"source URL must be public HTTPS on {allowed_host}: {url}"
        )
    return url


def validate_source_url(url: str, allowed_host: str) -> str:
    validate_source_url_shape(url, allowed_host)
    hostname = (urllib.parse.urlparse(url).hostname or "").lower()
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as error:
        raise ValueError(f"source hostname did not resolve: {hostname}") from error
    if not addresses:
        raise ValueError(f"source hostname did not resolve: {hostname}")
    for address in addresses:
        parsed_ip = ipaddress.ip_address(address)
        if not parsed_ip.is_global:
            raise ValueError(f"source hostname resolves to non-public IP: {address}")
    return url


class RestrictedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_host: str):
        super().__init__()
        self.allowed_host = allowed_host

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        target = urllib.parse.urljoin(request.full_url, new_url)
        validate_source_url(target, self.allowed_host)
        return super().redirect_request(
            request, file_pointer, code, message, headers, target
        )


def _read_limited(response: Any, maximum: int) -> bytes:
    payload = response.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError(f"source response exceeds {maximum} bytes")
    return payload


def _content_type(headers: Any, payload: bytes) -> tuple[str, str]:
    content_type = (headers.get("content-type") or "").split(";", 1)[0]
    content_type = content_type.strip().lower()
    if payload.startswith(b"%PDF-"):
        return "application/pdf", "pdf"
    extension = CONTENT_EXTENSIONS.get(content_type)
    if not extension:
        raise ValueError(f"unsupported source content type: {content_type or 'none'}")
    return content_type, extension


def fetch_source(
    url: str,
    *,
    allowed_host: str,
    captured_at: str,
    maximum_bytes: int = DEFAULT_MAX_BYTES,
    minimum_bytes: int = DEFAULT_MIN_BYTES,
) -> tuple[bytes, dict[str, Any]]:
    parse_timestamp(captured_at, "captured_at")
    validate_source_url(url, allowed_host)
    opener = urllib.request.build_opener(RestrictedRedirectHandler(allowed_host))
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9",
            "User-Agent": USER_AGENT,
        },
    )
    with opener.open(request, timeout=60) as response:
        payload = _read_limited(response, maximum_bytes)
        final_url = response.geturl()
        validate_source_url(final_url, allowed_host)
        status = getattr(response, "status", None) or response.getcode()
        headers = response.headers
    if status != 200:
        raise ValueError(f"source returned HTTP {status}")
    if len(payload) < minimum_bytes:
        raise ValueError(
            f"suspiciously small source response: {len(payload)} bytes"
        )
    content_type, extension = _content_type(headers, payload)
    sha256 = sha256_bytes(payload)
    retrieval = {
        "schema": RETRIEVAL_SCHEMA,
        "allowed_host": allowed_host,
        "archive_key": f"docs/{sha256}.{extension}",
        "captured_at": captured_at,
        "content_type": content_type,
        "final_url": final_url,
        "http_date": headers.get("date"),
        "http_status": status,
        "requested_url": url,
        "sha256": sha256,
        "size_bytes": len(payload),
    }
    return payload, retrieval


def build_receipt(
    retrieval: dict[str, Any],
    remote_payload: bytes,
    *,
    bucket: str,
    target_id: str,
    task_id: str,
    publisher: str,
    source_class: str,
    discovery_method: str,
    verified_at: str,
) -> dict[str, Any]:
    if retrieval.get("schema") != RETRIEVAL_SCHEMA:
        raise ValueError("unknown source retrieval schema")
    parse_timestamp(retrieval["captured_at"], "captured_at")
    parse_timestamp(verified_at, "verified_at")
    remote_sha256 = sha256_bytes(remote_payload)
    if remote_sha256 != retrieval.get("sha256"):
        raise ValueError("remote archive object does not match source retrieval")
    if len(remote_payload) != retrieval.get("size_bytes"):
        raise ValueError("remote archive object size does not match retrieval")
    expected_key = (
        f"docs/{retrieval['sha256']}."
        f"{CONTENT_EXTENSIONS[retrieval['content_type']]}"
    )
    if retrieval.get("archive_key") != expected_key:
        raise ValueError("archive key is not content-addressed")
    if not bucket or "/" in bucket:
        raise ValueError("invalid private archive bucket")
    if not target_id or not task_id:
        raise ValueError("capture receipt must link an intake task and target")

    return {
        "schema": RECEIPT_SCHEMA,
        "classification": CLASSIFICATION,
        "archive": {
            "backend": "cloudflare_r2",
            "bucket": bucket,
            "key": expected_key,
            "private": True,
            "remote_sha256": remote_sha256,
            "verification": "downloaded_and_sha256_matched",
            "verified_at": verified_at,
        },
        "pipeline_state": {
            "claim_extracted": False,
            "document_captured": True,
            "entity_seed_created": False,
            "publication_allowed": False,
        },
        "research_link": {
            "benchmark_target_id": target_id,
            "intake_task_id": task_id,
        },
        "retrieval": retrieval,
        "rights": {
            "public_copy_allowed": False,
            "redistribution_status": "private_only_pending_review",
            "rights_basis": "public_record",
        },
        "source": {
            "benchmark_lead_reused": False,
            "discovery_method": discovery_method,
            "independently_discovered": True,
            "publisher": publisher,
            "source_class": source_class,
        },
    }


def verify_receipt(
    receipt: dict[str, Any],
    *,
    object_payload: bytes | None = None,
) -> dict[str, Any]:
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unknown evidence capture receipt schema")
    if receipt.get("classification") != CLASSIFICATION:
        raise ValueError("capture receipt must remain private evidence metadata")
    retrieval = receipt.get("retrieval") or {}
    archive = receipt.get("archive") or {}
    source = receipt.get("source") or {}
    rights = receipt.get("rights") or {}
    pipeline_state = receipt.get("pipeline_state") or {}
    research_link = receipt.get("research_link") or {}

    if retrieval.get("schema") != RETRIEVAL_SCHEMA:
        raise ValueError("unknown retrieval schema")
    parse_timestamp(retrieval["captured_at"], "captured_at")
    parse_timestamp(archive["verified_at"], "verified_at")
    allowed_host = retrieval.get("allowed_host") or ""
    validate_source_url_shape(retrieval.get("requested_url") or "", allowed_host)
    validate_source_url_shape(retrieval.get("final_url") or "", allowed_host)
    if retrieval.get("http_status") != 200:
        raise ValueError("capture receipt must represent an HTTP 200 response")
    if retrieval.get("content_type") not in CONTENT_EXTENSIONS:
        raise ValueError("capture receipt has an unsupported content type")
    if (
        not isinstance(retrieval.get("size_bytes"), int)
        or retrieval["size_bytes"] < 1024
    ):
        raise ValueError("capture receipt source size is suspicious")
    if not re.fullmatch(r"[0-9a-f]{64}", retrieval.get("sha256") or ""):
        raise ValueError("capture receipt has an invalid SHA-256")
    if archive.get("backend") != "cloudflare_r2" or not archive.get("private"):
        raise ValueError("evidence archive must be private Cloudflare R2")
    if not archive.get("bucket") or "/" in archive["bucket"]:
        raise ValueError("capture receipt has an invalid archive bucket")
    expected_key = (
        f"docs/{retrieval['sha256']}."
        f"{CONTENT_EXTENSIONS[retrieval['content_type']]}"
    )
    if archive.get("key") != expected_key:
        raise ValueError("receipt archive key is not content-addressed")
    if archive.get("remote_sha256") != retrieval.get("sha256"):
        raise ValueError("remote archive hash does not match retrieval")
    if archive.get("verification") != "downloaded_and_sha256_matched":
        raise ValueError("remote archive was not independently verified")
    if source != {
        "benchmark_lead_reused": False,
        "discovery_method": source.get("discovery_method"),
        "independently_discovered": True,
        "publisher": source.get("publisher"),
        "source_class": source.get("source_class"),
    }:
        raise ValueError("source discovery boundary drift")
    if not all(
        source.get(field)
        for field in ("discovery_method", "publisher", "source_class")
    ):
        raise ValueError("source provenance metadata is incomplete")
    if rights != {
        "public_copy_allowed": False,
        "redistribution_status": "private_only_pending_review",
        "rights_basis": "public_record",
    }:
        raise ValueError("rights policy must fail closed")
    if pipeline_state != {
        "claim_extracted": False,
        "document_captured": True,
        "entity_seed_created": False,
        "publication_allowed": False,
    }:
        raise ValueError("capture receipt escaped the document-only state")
    if not all(
        research_link.get(field)
        for field in ("benchmark_target_id", "intake_task_id")
    ):
        raise ValueError("capture receipt is not linked to research intake")
    if object_payload is not None:
        if sha256_bytes(object_payload) != retrieval.get("sha256"):
            raise ValueError("provided archive object does not match receipt")
        if len(object_payload) != retrieval.get("size_bytes"):
            raise ValueError("provided archive object size does not match receipt")
    return {
        "archive_key": expected_key,
        "sha256": retrieval["sha256"],
        "size_bytes": retrieval["size_bytes"],
    }


def build_batch_manifest(
    queue_path: Path,
    receipt_paths: list[Path],
    *,
    root: Path,
) -> dict[str, Any]:
    root = root.resolve()
    queue_path = queue_path.resolve()
    queue_relative_path = queue_path.relative_to(root).as_posix()
    queue = load_json(queue_path)
    if queue.get("classification") != "research_queue":
        raise ValueError("capture batch input must be a research queue")
    known_tasks = {
        task["task_id"]: task for task in queue.get("tasks") or []
    }
    rows = []
    seen_tasks: set[str] = set()
    for receipt_path in sorted(receipt_paths, key=lambda path: str(path)):
        receipt_path = receipt_path.resolve()
        receipt_relative_path = receipt_path.relative_to(root).as_posix()
        receipt = load_json(receipt_path)
        verify_receipt(receipt)
        task_id = receipt["research_link"]["intake_task_id"]
        target_id = receipt["research_link"]["benchmark_target_id"]
        task = known_tasks.get(task_id)
        if not task or task.get("benchmark_id") != target_id:
            raise ValueError("capture receipt does not match a sealed intake task")
        benchmark_lead_urls = {
            lead.get("url") for lead in task.get("discovery_leads") or []
        }
        retrieval_urls = {
            receipt["retrieval"].get("requested_url"),
            receipt["retrieval"].get("final_url"),
        }
        if benchmark_lead_urls & retrieval_urls:
            raise ValueError(
                "capture URL was copied from the benchmark discovery leads"
            )
        if task_id in seen_tasks:
            raise ValueError("capture batch contains duplicate intake tasks")
        seen_tasks.add(task_id)
        rows.append(
            {
                "archive_key": receipt["archive"]["key"],
                "benchmark_target_id": target_id,
                "intake_task_id": task_id,
                "path": receipt_relative_path,
                "receipt_sha256": sha256_bytes(receipt_path.read_bytes()),
                "source_sha256": receipt["retrieval"]["sha256"],
            }
        )
    return {
        "schema": BATCH_SCHEMA,
        "classification": BATCH_CLASSIFICATION,
        "inputs": {
            "intake_queue_path": queue_relative_path,
            "intake_queue_sha256": sha256_bytes(queue_path.read_bytes()),
        },
        "policy": {
            "claims_created": False,
            "entity_seeds_created": False,
            "private_archive_only": True,
            "publication_allowed": False,
        },
        "receipts": rows,
        "summary": {
            "captured_documents": len(rows),
            "claims_created": 0,
            "entity_seeds_created": 0,
        },
    }


def verify_batch_manifest(
    manifest_path: Path,
    *,
    root: Path,
    expected_receipts: int | None = None,
) -> dict[str, int]:
    manifest = load_json(manifest_path)
    if manifest.get("schema") != BATCH_SCHEMA:
        raise ValueError("unknown evidence capture batch schema")
    if manifest.get("classification") != BATCH_CLASSIFICATION:
        raise ValueError("capture batch must remain private evidence metadata")
    root = root.resolve()
    queue_path = (root / manifest["inputs"]["intake_queue_path"]).resolve()
    queue_path.relative_to(root)
    if (
        sha256_bytes(queue_path.read_bytes())
        != manifest["inputs"]["intake_queue_sha256"]
    ):
        raise ValueError("capture batch intake queue hash mismatch")
    receipt_paths = []
    for row in manifest.get("receipts") or []:
        receipt_path = (root / row["path"]).resolve()
        receipt_path.relative_to(root)
        receipt_paths.append(receipt_path)
    expected = build_batch_manifest(queue_path, receipt_paths, root=root)
    if manifest != expected:
        raise ValueError("capture batch is not reproducible from its receipts")
    if expected_receipts is not None and len(receipt_paths) != expected_receipts:
        raise ValueError(
            f"expected {expected_receipts} capture receipts, "
            f"found {len(receipt_paths)}"
        )
    return {
        "captured_documents": len(receipt_paths),
        "claims_created": manifest["summary"]["claims_created"],
        "entity_seeds_created": manifest["summary"]["entity_seeds_created"],
    }


def fetch_command(args: argparse.Namespace) -> None:
    payload, retrieval = fetch_source(
        args.url,
        allowed_host=args.allowed_host,
        captured_at=args.captured_at,
        maximum_bytes=args.maximum_bytes,
        minimum_bytes=args.minimum_bytes,
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = CONTENT_EXTENSIONS[retrieval["content_type"]]
    object_path = output_dir / f"source.{extension}"
    object_path.write_bytes(payload)
    write_json(output_dir / "retrieval.json", retrieval)
    print(
        f"retrieved {retrieval['size_bytes']} bytes "
        f"sha256={retrieval['sha256']} object={object_path}"
    )


def seal_command(args: argparse.Namespace) -> None:
    receipt = build_receipt(
        load_json(Path(args.retrieval)),
        Path(args.remote_object).read_bytes(),
        bucket=args.bucket,
        target_id=args.target_id,
        task_id=args.task_id,
        publisher=args.publisher,
        source_class=args.source_class,
        discovery_method=args.discovery_method,
        verified_at=args.verified_at,
    )
    output = Path(args.output)
    write_json(output, receipt)
    print(
        f"sealed {receipt['archive']['key']} "
        f"receipt_sha256={sha256_bytes(output.read_bytes())}"
    )


def verify_command(args: argparse.Namespace) -> None:
    payload = Path(args.object_file).read_bytes() if args.object_file else None
    result = verify_receipt(load_json(Path(args.receipt)), object_payload=payload)
    print(
        f"capture verification: {result['archive_key']} "
        f"{result['size_bytes']} bytes sha256={result['sha256']}"
    )


def build_batch_command(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    manifest = build_batch_manifest(
        Path(args.queue).resolve(),
        [Path(path).resolve() for path in args.receipt],
        root=root,
    )
    output = Path(args.output)
    write_json(output, manifest)
    print(
        f"sealed capture batch: {manifest['summary']['captured_documents']} "
        f"documents, manifest_sha256={sha256_bytes(output.read_bytes())}"
    )


def verify_batch_command(args: argparse.Namespace) -> None:
    result = verify_batch_manifest(
        Path(args.manifest),
        root=Path(args.root).resolve(),
        expected_receipts=args.expected_receipts,
    )
    print(
        "capture batch verification: "
        f"{result['captured_documents']} documents, "
        f"{result['claims_created']} claims, "
        f"{result['entity_seeds_created']} entity seeds"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("--url", required=True)
    fetch_parser.add_argument("--allowed-host", required=True)
    fetch_parser.add_argument("--captured-at", required=True)
    fetch_parser.add_argument("--output-dir", required=True)
    fetch_parser.add_argument("--maximum-bytes", type=int, default=DEFAULT_MAX_BYTES)
    fetch_parser.add_argument("--minimum-bytes", type=int, default=DEFAULT_MIN_BYTES)
    fetch_parser.set_defaults(func=fetch_command)

    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("--retrieval", required=True)
    seal_parser.add_argument("--remote-object", required=True)
    seal_parser.add_argument("--bucket", required=True)
    seal_parser.add_argument("--target-id", required=True)
    seal_parser.add_argument("--task-id", required=True)
    seal_parser.add_argument("--publisher", required=True)
    seal_parser.add_argument("--source-class", required=True)
    seal_parser.add_argument("--discovery-method", required=True)
    seal_parser.add_argument("--verified-at", required=True)
    seal_parser.add_argument("--output", required=True)
    seal_parser.set_defaults(func=seal_command)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--receipt", required=True)
    verify_parser.add_argument("--object-file")
    verify_parser.set_defaults(func=verify_command)

    batch_parser = subparsers.add_parser("build-batch")
    batch_parser.add_argument("--root", required=True)
    batch_parser.add_argument("--queue", required=True)
    batch_parser.add_argument("--receipt", action="append", required=True)
    batch_parser.add_argument("--output", required=True)
    batch_parser.set_defaults(func=build_batch_command)

    verify_batch_parser = subparsers.add_parser("verify-batch")
    verify_batch_parser.add_argument("--root", required=True)
    verify_batch_parser.add_argument("--manifest", required=True)
    verify_batch_parser.add_argument("--expected-receipts", type=int)
    verify_batch_parser.set_defaults(func=verify_batch_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
