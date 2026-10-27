from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


class DeploymentVerificationError(RuntimeError):
    """Raised when the public Pages deployment does not match the build."""


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_manifest(public_dir: Path, run_id: str) -> dict[str, Any]:
    candidates = [public_dir / "data" / "briefing.json"]
    candidates.extend(sorted((public_dir / "widgets").glob("*.html")))
    candidates.extend(sorted((public_dir / "widgets").glob("*.png")))
    files: dict[str, dict[str, Any]] = {}
    for path in candidates:
        if not path.is_file():
            continue
        payload = path.read_bytes()
        relative = path.relative_to(public_dir).as_posix()
        files[relative] = {"sha256": _digest(payload), "bytes": len(payload)}
    return {"schema_version": 1, "run_id": str(run_id), "files": files}


def _download(
    url: str,
    *,
    timeout: float,
    retries: int,
    opener: Callable[..., Any],
    sleep: Callable[[float], None],
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"Cache-Control": "no-cache"})
            with opener(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # urllib exposes several transient exception types
            last_error = exc
            if attempt >= retries:
                break
            sleep(min(2**attempt, 4))
    raise DeploymentVerificationError(f"public file download failed: {last_error}")


def verify_public_deployment(
    base_url: str,
    expected_manifest: dict[str, Any],
    *,
    timeout: float = 20,
    retries: int = 3,
    opener: Callable[..., Any] = urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    run_id = str(expected_manifest.get("run_id") or "")
    cache_buster = quote(run_id, safe="")
    manifest_url = urljoin(base_url.rstrip("/") + "/", "deployment-manifest.json")
    manifest_payload = _download(
        f"{manifest_url}?run={cache_buster}",
        timeout=timeout,
        retries=retries,
        opener=opener,
        sleep=sleep,
    )
    try:
        public_manifest = json.loads(manifest_payload)
    except (TypeError, ValueError) as exc:
        raise DeploymentVerificationError("public deployment manifest is invalid JSON") from exc

    public_run_id = str(public_manifest.get("run_id") or "")
    if public_run_id != run_id:
        raise DeploymentVerificationError(
            f"public run ID mismatch: expected {run_id!r}, got {public_run_id!r}"
        )

    for relative, metadata in sorted(expected_manifest.get("files", {}).items()):
        file_url = urljoin(base_url.rstrip("/") + "/", relative)
        payload = _download(
            f"{file_url}?run={cache_buster}",
            timeout=timeout,
            retries=retries,
            opener=opener,
            sleep=sleep,
        )
        actual_hash = _digest(payload)
        expected_hash = str(metadata.get("sha256") or "")
        if actual_hash != expected_hash:
            raise DeploymentVerificationError(
                f"SHA-256 mismatch for {relative}: expected {expected_hash}, got {actual_hash}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and verify ABO Pages artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--public-dir", type=Path, default=Path("public"))
    build_parser.add_argument("--run-id", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--base-url", required=True)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "build":
        manifest = build_manifest(args.public_dir, args.run_id)
        output = args.public_dir / "deployment-manifest.json"
        output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {output} ({len(manifest['files'])} files)")
        return

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    verify_public_deployment(args.base_url, manifest)
    print(f"verified public deployment for run {manifest.get('run_id')}")


if __name__ == "__main__":
    main()
