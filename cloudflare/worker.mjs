const ACTIVE_STATUSES = new Set(["queued", "in_progress", "waiting", "pending"]);

function required(env, name) {
  const value = env[name];
  if (!value) throw new Error(`missing required setting: ${name}`);
  return value;
}

function githubHeaders(env) {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${required(env, "GITHUB_TOKEN")}`,
    "Content-Type": "application/json",
    "User-Agent": "abo-data-freshness-worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function sendAlert(env, fetchImpl, message) {
  if (!env.ALERT_WEBHOOK_URL) return;
  try {
    await fetchImpl(env.ALERT_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: message }),
    });
  } catch (error) {
    console.error("ABO alert delivery failed", error);
  }
}

async function readFeed(env, fetchImpl, now) {
  try {
    const separator = env.FEED_URL.includes("?") ? "&" : "?";
    const response = await fetchImpl(`${env.FEED_URL}${separator}monitor=${now.getTime()}`, {
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) return { stale: true, reason: `feed_http_${response.status}` };
    const feed = await response.json();
    const timestamp = feed?.collection?.completed_at || feed?.generated_at;
    const completedAt = Date.parse(timestamp || "");
    if (!Number.isFinite(completedAt)) return { stale: true, reason: "invalid_feed" };
    const maxAgeMinutes = Number(env.MAX_DATA_AGE_MINUTES || "50");
    const ageMinutes = (now.getTime() - completedAt) / 60000;
    return {
      stale: ageMinutes > maxAgeMinutes,
      reason: ageMinutes > maxAgeMinutes ? "stale_feed" : "fresh_feed",
      age_minutes: Math.max(0, Math.round(ageMinutes * 10) / 10),
      completed_at: new Date(completedAt).toISOString(),
    };
  } catch (_error) {
    return { stale: true, reason: "invalid_feed" };
  }
}

export async function inspectAndDispatch(env, fetchImpl = fetch, now = new Date()) {
  required(env, "FEED_URL");
  const freshness = await readFeed(env, fetchImpl, now);
  if (!freshness.stale) return { action: "fresh", ...freshness };

  const owner = required(env, "GITHUB_OWNER");
  const repo = required(env, "GITHUB_REPO");
  const workflow = required(env, "GITHUB_WORKFLOW");
  const workflowPath = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${encodeURIComponent(workflow)}`;
  const runsResponse = await fetchImpl(`${workflowPath}/runs?per_page=20`, {
    headers: githubHeaders(env),
  });
  if (!runsResponse.ok) {
    const message = `ABO workflow status check failed: ${runsResponse.status}`;
    await sendAlert(env, fetchImpl, message);
    throw new Error(message);
  }
  const runs = await runsResponse.json();
  const activeRun = (runs.workflow_runs || []).find((run) => ACTIVE_STATUSES.has(run.status));
  if (activeRun) {
    return { action: "active_run", reason: freshness.reason, run_id: activeRun.id || null };
  }

  const dispatchResponse = await fetchImpl(`${workflowPath}/dispatches`, {
    method: "POST",
    headers: githubHeaders(env),
    body: JSON.stringify({ ref: env.GITHUB_REF || "main" }),
  });
  if (!dispatchResponse.ok) {
    const message = `ABO workflow dispatch failed: ${dispatchResponse.status}`;
    await sendAlert(env, fetchImpl, message);
    throw new Error(`dispatch failed: ${dispatchResponse.status}`);
  }
  return { action: "dispatched", reason: freshness.reason, age_minutes: freshness.age_minutes ?? null };
}

export default {
  async scheduled(_controller, env, context) {
    context.waitUntil(
      inspectAndDispatch(env)
        .then((result) => console.log("ABO freshness monitor", JSON.stringify(result)))
        .catch((error) => console.error("ABO freshness monitor failed", error)),
    );
  },
};
