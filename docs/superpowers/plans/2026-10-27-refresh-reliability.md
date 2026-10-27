# ABO Refresh Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve ABO's public interfaces while making collection freshness, fallback reuse, duplicate execution, and deployed artifact identity observable and verifiable.

**Architecture:** Extend the collector with backward-compatible run metadata and semantic freshness reconciliation. Generate a public SHA-256 deployment manifest, verify it after Pages deployment, cache pinned fonts, and provide a Cloudflare Worker fallback that dispatches only when data is stale and no run is active.

**Tech Stack:** Python 3.12, `unittest`, GitHub Actions, Pillow, JavaScript ES modules, Node built-in test runner, Cloudflare Workers.

**Spec:** `docs/superpowers/specs/2026-10-27-refresh-reliability-design.md`

## Global Constraints

- Keep existing news selection, Android JSON fields, blog widget dimensions/design, and Pages paths.
- Add only backward-compatible JSON fields.
- Use Asia/Seoul timestamps with explicit offsets.
- Do not require Cloudflare credentials for repository tests.
- Do not treat workflow completion as proof of deployed data freshness.

## Review Focus

- A source fails while previous items exist: output must mark reuse and keep item timestamps.
- A run produces semantically identical content: `content_updated_at` must remain unchanged.
- A duplicate trigger arrives during a run: the existing run must not be cancelled.
- Pages/CDN serves an older artifact: verification must fail on run ID or SHA mismatch.
- Cloudflare observes stale data while another run is queued: it must not dispatch a duplicate.

---

### Task 1: Collection provenance and stable freshness

**Files:**
- Modify: `collector.py`
- Modify: `tests/test_collector.py`

**Interfaces:**
- Produces: `collection` metadata in the feed and stable `content_updated_at`/item `updated_at` values.
- Produces: `HttpClient(timeout: float = 18.0, retries: int = 3)` with bounded exponential retry.

- [ ] Write failing tests for retry count, previous-item reuse metadata, stable item timestamps, and unchanged semantic content preserving `content_updated_at`.
- [ ] Run the focused collector tests and confirm each fails for the missing behavior.
- [ ] Add internal provenance markers, semantic comparison helpers, run metadata, and retry logging with the smallest compatible changes.
- [ ] Strip internal markers before validation/output and keep legacy `source_health` strings.
- [ ] Run focused tests and the full Python suite.

### Task 2: Deployment manifest and public verification

**Files:**
- Create: `deployment_verifier.py`
- Create: `tests/test_deployment_verifier.py`
- Modify: `widget_renderer.py`
- Modify: `tests/test_widget_renderer.py`

**Interfaces:**
- Produces: `build_manifest(public_dir: Path, run_id: str) -> dict[str, object]`.
- Produces: `verify_public_deployment(base_url: str, manifest: dict[str, object], *, timeout: float, retries: int) -> None`.

- [ ] Write failing tests for manifest hashes, stale run IDs, mismatched JSON/widget hashes, retry success, and bounded failure.
- [ ] Run tests and confirm failure because the verifier does not exist.
- [ ] Implement manifest generation and public verification using the standard library.
- [ ] Add the run ID to widget HTML metadata without changing visible layout.
- [ ] Run verifier/widget tests and the full suite.

### Task 3: Workflow caching, download bounds, and duplicate handling

**Files:**
- Modify: `.github/workflows/publish.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: collector `collection.run_id` and deployment verifier CLI.
- Produces: cached pinned fonts, pip cache, queued concurrency, and post-deploy hash verification.

- [ ] Add a workflow-structure test that asserts `cancel-in-progress: false`, cache steps, bounded downloads, manifest generation, and post-deploy verification.
- [ ] Run it and confirm the current workflow fails those assertions.
- [ ] Replace per-run apt font installation with `actions/cache` plus pinned font downloads using retry/connect/max-time limits.
- [ ] Enable pip caching and bound the previous-feed download.
- [ ] Generate the deployment manifest before upload and verify public Pages after deploy.
- [ ] Run YAML/structure tests and the full suite.

### Task 4: Cloudflare stale-data fallback

**Files:**
- Create: `cloudflare/worker.mjs`
- Create: `cloudflare/worker.test.mjs`
- Create: `cloudflare/wrangler.toml.example`
- Modify: `README.md`

**Interfaces:**
- Produces: `inspectAndDispatch(env, fetchImpl, now) -> Promise<object>`.
- Consumes: Pages feed URL, GitHub workflow runs API, and workflow dispatch API.

- [ ] Write Node tests for fresh data, stale data, active-run suppression, malformed feed, dispatch failure, and optional alert delivery.
- [ ] Run `node --test cloudflare/worker.test.mjs` and confirm it fails before implementation.
- [ ] Implement the scheduled Worker with a 30-minute cron example and no persistent state requirement.
- [ ] Document only the required Cloudflare variables and fine-grained GitHub token permission.
- [ ] Run Node tests and the full repository suite.

### Task 5: End-to-end verification and publication

**Files:**
- Modify only files required by failures found above.

**Interfaces:**
- Validates all interfaces from Tasks 1-4.

- [ ] Run all Python and Node tests, plus local collector/widget generation against controlled fixtures.
- [ ] Validate duplicate-trigger behavior from workflow configuration and Worker tests.
- [ ] Review the diff for preserved app/widget/Pages contracts and absence of secrets.
- [ ] Commit and push the minimal patch to `chakhan82/abo-data`.
- [ ] Trigger `workflow_dispatch`, wait for build/deploy, then compare the run artifact, public JSON, and all widget hashes/run IDs.
- [ ] Report run links, observed source failures/reuse, external Cloudflare settings still required, and any residual GitHub scheduling risk.

