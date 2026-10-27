from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "publish.yml"


class WorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_duplicate_runs_wait_instead_of_cancelling_a_live_publish(self) -> None:
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_expensive_dependencies_are_cached_and_downloads_are_bounded(self) -> None:
        self.assertIn("cache: pip", self.workflow)
        self.assertIn("actions/cache@v4", self.workflow)
        self.assertIn("--connect-timeout", self.workflow)
        self.assertIn("--max-time", self.workflow)
        self.assertIn("--retry-all-errors", self.workflow)

    def test_publish_builds_manifest_and_verifies_the_public_pages_bytes(self) -> None:
        self.assertIn("deployment_verifier.py build", self.workflow)
        self.assertIn("deployment_verifier.py verify", self.workflow)
        self.assertIn("actions/upload-artifact@v4", self.workflow)
        self.assertIn("actions/download-artifact@v4", self.workflow)


if __name__ == "__main__":
    unittest.main()
