import assert from "node:assert/strict";
import test from "node:test";

import { inspectAndDispatch } from "./worker.mjs";

const NOW = new Date("2026-10-27T12:00:00Z");

function response(body, status = 200) {
  const payload = status === 204 ? null : (typeof body === "string" ? body : JSON.stringify(body));
  return new Response(payload, {
    status,
    headers: { "content-type": "application/json" },
  });
}

function environment(overrides = {}) {
  return {
    FEED_URL: "https://pages.example.test/data/briefing.json",
    GITHUB_OWNER: "chakhan82",
    GITHUB_REPO: "abo-data",
    GITHUB_WORKFLOW: "publish.yml",
    GITHUB_REF: "main",
    GITHUB_TOKEN: "test-token",
    MAX_DATA_AGE_MINUTES: "50",
    ...overrides,
  };
}

test("fresh public data does not call GitHub", async () => {
  const calls = [];
  const result = await inspectAndDispatch(environment(), async (url, options = {}) => {
    calls.push([String(url), options.method || "GET"]);
    return response({ collection: { completed_at: "2026-10-27T11:30:00Z" } });
  }, NOW);

  assert.equal(result.action, "fresh");
  assert.equal(calls.length, 1);
});

test("an active run suppresses a duplicate dispatch for stale data", async () => {
  const calls = [];
  const result = await inspectAndDispatch(environment(), async (url, options = {}) => {
    calls.push([String(url), options.method || "GET"]);
    if (String(url).includes("briefing.json")) {
      return response({ collection: { completed_at: "2026-10-27T09:00:00Z" } });
    }
    return response({ workflow_runs: [{ status: "in_progress" }] });
  }, NOW);

  assert.equal(result.action, "active_run");
  assert.equal(calls.some((call) => call[1] === "POST"), false);
});

test("stale public data dispatches the workflow when no run is active", async () => {
  const calls = [];
  const result = await inspectAndDispatch(environment(), async (url, options = {}) => {
    calls.push([String(url), options.method || "GET"]);
    if (String(url).includes("briefing.json")) {
      return response({ generated_at: "2026-10-27T09:00:00Z" });
    }
    if ((options.method || "GET") === "POST") return response("", 204);
    return response({ workflow_runs: [] });
  }, NOW);

  assert.equal(result.action, "dispatched");
  assert.equal(calls.filter((call) => call[1] === "POST").length, 1);
});

test("a malformed feed is treated as stale", async () => {
  const result = await inspectAndDispatch(environment(), async (url, options = {}) => {
    if (String(url).includes("briefing.json")) return response("not-json");
    if ((options.method || "GET") === "POST") return response("", 204);
    return response({ workflow_runs: [] });
  }, NOW);

  assert.equal(result.action, "dispatched");
  assert.equal(result.reason, "invalid_feed");
});

test("dispatch failure throws and sends the optional alert", async () => {
  const alerts = [];
  const env = environment({ ALERT_WEBHOOK_URL: "https://alerts.example.test/hook" });
  await assert.rejects(
    inspectAndDispatch(env, async (url, options = {}) => {
      if (String(url).includes("briefing.json")) {
        return response({ generated_at: "2026-10-27T09:00:00Z" });
      }
      if (String(url).includes("alerts.example.test")) {
        alerts.push(JSON.parse(options.body));
        return response("", 204);
      }
      if ((options.method || "GET") === "POST") return response("denied", 403);
      return response({ workflow_runs: [] });
    }, NOW),
    /dispatch failed: 403/,
  );
  assert.equal(alerts.length, 1);
  assert.match(alerts[0].text, /dispatch failed/);
});
