import { expect, test } from "@playwright/test";

type ScenarioJob = {
  status: string;
  terminal?: boolean;
  error?: string | null;
  result?: { scan_id?: string } | null;
};

async function login(page: import("@playwright/test").Page, username: string, password: string) {
  await page.goto("/workspace");
  const directDemo = page.getByRole("button", { name: /local demo · analyst/i });
  try {
    await directDemo.waitFor({ state: "visible", timeout: 10_000 });
    return;
  } catch {
    // Normal authentication mode keeps the sign-in flow below.
  }
  await page.getByRole("button", { name: /sign in to server/i }).click();
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await expect(page.getByRole("button", { name: /server connected/i })).toBeVisible();
}

async function runScenarioAndWait(
  request: import("@playwright/test").APIRequestContext,
  headers: Record<string, string>,
): Promise<string> {
  const catalogue = await request.get("/api/attacklab/scenarios");
  expect(catalogue.ok()).toBeTruthy();
  const scenarios = await catalogue.json() as { scenarios: { scenario_id: string }[] };
  const profileResponse = await request.get("/api/system/profiles");
  expect(profileResponse.ok()).toBeTruthy();
  const profiles = await profileResponse.json() as { profiles: { name: string }[] };
  const scenario = scenarios.scenarios[0];
  const profile = profiles.profiles[0];
  expect(scenario?.scenario_id).toEqual(expect.any(String));
  expect(profile?.name).toEqual(expect.any(String));
  const run = await request.post(`/api/attacklab/scenarios/${encodeURIComponent(scenario.scenario_id)}/run`, {
    headers,
    data: { profile: profile.name },
  });
  expect(run.status()).toBe(202);
  const queued = await run.json() as { job_id?: string; status?: string };
  expect(queued.job_id).toEqual(expect.any(String));

  let completed: ScenarioJob | undefined;
  await expect.poll(async () => {
    const response = await request.get(`/api/jobs/${encodeURIComponent(queued.job_id!)}`);
    expect(response.ok()).toBeTruthy();
    completed = await response.json() as ScenarioJob;
    return completed.terminal === true;
  }, {
    timeout: 120_000,
    message: `Attack Lab job ${queued.job_id} did not complete`,
  }).toBeTruthy();

  if (!completed?.result?.scan_id) {
    throw new Error(`Completed Attack Lab job ${queued.job_id} did not return a scan ID.`);
  }
  return completed.result.scan_id;
}

test("assessment dialog registers an empty required asset role and selects it", async ({ page }) => {
  await login(page, "analyst", "analystpassword");
  await page.getByRole("button", { name: /new assessment/i }).click();
  await expect(page.getByText(/no active compatible assets registered/i)).toBeVisible();
  await page.route("**/api/assets/upload", async route => {
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({
      id: "DAT-E2E0001", kind: "dataset", name: "browser-dataset", digest: "sha256:e2e",
      lifecycle: "ACTIVE", created_at: "2026-01-01T00:00:00Z",
    }) });
  });
  await page.getByLabel("Choose dataset asset file").setInputFiles({ name: "dataset.zip", mimeType: "application/zip", buffer: Buffer.from("test archive") });
  await page.getByRole("button", { name: "Register dataset" }).click();
  await expect(page.getByRole("combobox", { name: "dataset" })).toHaveValue("DAT-E2E0001");
  await expect(page.getByText(/no active compatible assets registered/i)).toHaveCount(0);
});

test("Attack Lab keeps its runner context separate from the selected assessment", async ({ page }) => {
  await login(page, "analyst", "analystpassword");
  await page.getByRole("button", { name: "Attack Lab", exact: true }).click();
  await expect(page.getByText("Independent scenario runner")).toBeVisible();
  await expect(page.getByText("Runner", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Assessment details" })).toHaveCount(0);
});

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
  const contract = await (await context.request.get("/api/system/metadata")).json();
  const target = contract.statuses.disposition.find((item: string) => item !== finding.disposition);
  const reason = contract.governance.reason_codes[0];

  const request = await context.request.post(`/api/findings/${finding.id}/decision`, { headers, data: {
    target_disposition: target, reason_code: reason,
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
  const contract = await (await analyst.request.get("/api/system/metadata")).json();
  const target = contract.statuses.disposition.find((item: string) => item !== finding.disposition);
  const reason = contract.governance.reason_codes[0];
  const decision = await analyst.request.post(`/api/findings/${finding.id}/decision`, { headers: analystHeaders, data: { target_disposition: target, reason_code: reason, justification: "A second account must be able to independently approve this tested request." } });

  const approver = await browser.newContext({ baseURL: "http://127.0.0.1:4173" });
  const approverPage = await approver.newPage();
  await login(approverPage, "approver", "approverpassword");
  const approverSession = await approver.request.get("/api/auth/me");
  const response = await approver.request.post(`/api/governance/decisions/${(await decision.json()).id}/approve`, { headers: { Origin: "http://127.0.0.1:4173", "X-CSRF-Token": (await approverSession.json()).csrf }, data: { justification: "Independent approver completed the E2E disposition review." } });
  expect(response.ok()).toBeTruthy();
  await analyst.close(); await approver.close();
});
