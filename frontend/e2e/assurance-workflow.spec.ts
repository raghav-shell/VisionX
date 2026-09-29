import { expect, test } from "@playwright/test";

type ScenarioJob = {
  status: string;
  error?: string | null;
  result?: { scan_id?: string } | null;
};

async function login(page: import("@playwright/test").Page, username: string, password: string) {
  await page.goto("/workspace");
  await page.getByRole("button", { name: /sign in to server/i }).click();
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await expect(page.getByText(new RegExp(`Connected · ${username}`))).toBeVisible();
}

async function runScenarioAndWait(
  request: import("@playwright/test").APIRequestContext,
  headers: Record<string, string>,
): Promise<string> {
  const run = await request.post("/api/attacklab/scenarios/label_flip_targeted/run", {
    headers,
    data: { profile: "selftest" },
  });
  expect(run.status()).toBe(202);
  const queued = await run.json() as { job_id?: string; status?: string };
  expect(queued.status).toBe("QUEUED");
  expect(queued.job_id).toEqual(expect.any(String));

  let completed: ScenarioJob | undefined;
  await expect.poll(async () => {
    const response = await request.get(`/api/jobs/${encodeURIComponent(queued.job_id!)}`);
    expect(response.ok()).toBeTruthy();
    completed = await response.json() as ScenarioJob;
    return completed.status;
  }, {
    timeout: 120_000,
    intervals: [100, 250, 500, 1_000],
    message: `Attack Lab job ${queued.job_id} did not complete`,
  }).toBe("COMPLETED");

  if (!completed?.result?.scan_id) {
    throw new Error(`Completed Attack Lab job ${queued.job_id} did not return a scan ID.`);
  }
  return completed.result.scan_id;
}

test("analyst can upload, run, inspect, request and audit a governed scan", async ({ page, context }) => {
  await login(page, "analyst", "analystpassword");
  const session = await context.request.get("/api/auth/me");
  const csrf = (await session.json()).csrf;
  const headers = { Origin: "http://127.0.0.1:4173", "X-CSRF-Token": csrf };

  // A bounded upload proves the browser route, asset registry, and type validation work together.
  const upload = await context.request.post("/api/assets/upload", { headers,
    multipart: { kind: "ledger", name: "browser-ledger", file: { name: "events.jsonl", mimeType: "application/x-ndjson", buffer: Buffer.from('{"event":"e2e"}\n') } } });
  expect(upload.status()).toBe(201);

  // Controlled attack lab creates a sealed scan with real finding/evidence data.
  const scanId = await runScenarioAndWait(context.request, headers);
  const findings = await context.request.get(`/api/scans/${scanId}/findings`);
  const finding = (await findings.json()).findings[0];
  expect(finding.evidence.length).toBeGreaterThan(0);

  const request = await context.request.post(`/api/findings/${finding.id}/decision`, { headers, data: {
    target_disposition: "ACCEPT", reason_code: "ACCEPTED_RISK",
    justification: "E2E governance request has sufficient explanation for independent review.",
  } });
  expect(request.status()).toBe(201);
  const decisionId = (await request.json()).id;
  const selfApproval = await context.request.post(`/api/governance/decisions/${decisionId}/approve`, { headers, data: { justification: "Self approval must fail." } });
  expect(selfApproval.status()).toBe(403);

  const audit = await context.request.post("/api/provenance/verify", { data: {} });
  expect(audit.ok()).toBeTruthy();
  expect((await audit.json()).intact).toBeTruthy();
});

test("a second approver can approve a pending request", async ({ browser }) => {
  const analyst = await browser.newContext({ baseURL: "http://127.0.0.1:4173" });
  const analystPage = await analyst.newPage();
  await login(analystPage, "analyst", "analystpassword");
  const analystSession = await analyst.request.get("/api/auth/me");
  const analystHeaders = { Origin: "http://127.0.0.1:4173", "X-CSRF-Token": (await analystSession.json()).csrf };
  const scanId = await runScenarioAndWait(analyst.request, analystHeaders);
  const finding = (await (await analyst.request.get(`/api/scans/${scanId}/findings`)).json()).findings[0];
  const decision = await analyst.request.post(`/api/findings/${finding.id}/decision`, { headers: analystHeaders, data: { target_disposition: "ACCEPT", reason_code: "ACCEPTED_RISK", justification: "A second account must be able to independently approve this tested request." } });

  const approver = await browser.newContext({ baseURL: "http://127.0.0.1:4173" });
  const approverPage = await approver.newPage();
  await login(approverPage, "approver", "approverpassword");
  const approverSession = await approver.request.get("/api/auth/me");
  const response = await approver.request.post(`/api/governance/decisions/${(await decision.json()).id}/approve`, { headers: { Origin: "http://127.0.0.1:4173", "X-CSRF-Token": (await approverSession.json()).csrf }, data: { justification: "Independent approver completed the E2E disposition review." } });
  expect(response.ok()).toBeTruthy();
  await analyst.close(); await approver.close();
});
