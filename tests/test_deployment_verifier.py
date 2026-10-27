from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from deployment_verifier import (
    DeploymentVerificationError,
    build_manifest,
    verify_public_deployment,
)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class DeploymentVerifierTests(unittest.TestCase):
    def test_manifest_contains_feed_and_all_widget_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            public = Path(temp_dir)
            (public / "data").mkdir()
            (public / "widgets").mkdir()
            (public / "data" / "briefing.json").write_bytes(b"{}")
            (public / "widgets" / "economy.html").write_bytes(b"widget")
            (public / "widgets" / "economy.png").write_bytes(b"png")

            manifest = build_manifest(public, "run-100")

        self.assertEqual(manifest["run_id"], "run-100")
        self.assertEqual(
            manifest["files"]["data/briefing.json"]["sha256"],
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        )
        self.assertEqual(
            sorted(manifest["files"]),
            [
                "data/briefing.json",
                "widgets/economy.html",
                "widgets/economy.png",
            ],
        )

    def test_verification_rejects_a_stale_public_run(self) -> None:
        expected = {"run_id": "run-200", "files": {}}
        public = json.dumps({"run_id": "run-199", "files": {}}).encode()

        with self.assertRaisesRegex(DeploymentVerificationError, "run ID"):
            verify_public_deployment(
                "https://pages.example.test/",
                expected,
                opener=lambda *_args, **_kwargs: _Response(public),
                retries=0,
            )

    def test_verification_rejects_a_public_file_hash_mismatch(self) -> None:
        expected = {
            "run_id": "run-201",
            "files": {
                "data/briefing.json": {
                    "sha256": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
                    "bytes": 2,
                }
            },
        }
        public_manifest = json.dumps(expected).encode()

        def opener(request, **_kwargs):
            url = getattr(request, "full_url", str(request))
            payload = public_manifest if "deployment-manifest" in url else b'{"wrong":true}'
            return _Response(payload)

        with self.assertRaisesRegex(DeploymentVerificationError, "SHA-256"):
            verify_public_deployment(
                "https://pages.example.test/", expected, opener=opener, retries=0
            )

    def test_verification_retries_a_transient_download_failure(self) -> None:
        expected = {"run_id": "run-202", "files": {}}
        public = json.dumps(expected).encode()
        attempts = 0

        def opener(*_args, **_kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("temporary")
            return _Response(public)

        verify_public_deployment(
            "https://pages.example.test/",
            expected,
            opener=opener,
            retries=1,
            sleep=lambda _seconds: None,
        )

        self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()
