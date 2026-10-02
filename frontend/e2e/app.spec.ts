import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const PASSWORD = process.env.E2E_PASSWORD ?? "";
const SHOTS = process.env.E2E_SHOTS ?? "";

async function signIn(page: Page, username: string) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  const project = test.info().project.name;
  await page.screenshot({ path: path.join(SHOTS, `F-UI-${name}_${project}.png`), fullPage: false });
}

async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page must not scroll sideways").toBeLessThanOrEqual(1);
}

test.beforeAll(() => {
  expect(PASSWORD.length, "E2E_PASSWORD is set by scripts/dev.py e2e").toBeGreaterThan(15);
});

test("TC-S-01 a wrong password gets the generic refusal", async ({ page }) => {
  await page.goto("/login");
  await shot(page, "01-login");
  await page.getByLabel("Username").fill("e2e-hcw");
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Username or password incorrect.")).toBeVisible();
  await expectNoSidewaysScroll(page);
});

test("TC-S-02 a health worker sees the overview, stock, forecast and alerts", async ({ page }) => {
  await signIn(page, "e2e-hcw");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Defaulters: \d+/ })).toBeVisible();
  await expect(page.getByText("All records shown are synthetic.")).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "02-overview");

  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Stock" }).click();
  await expect(page.getByRole("list", { name: "Current stock per vaccine" }).getByRole("listitem")).toHaveCount(7);
  await expectNoSidewaysScroll(page);
  await shot(page, "03-stock");

  await page.getByRole("tab", { name: "Forecast" }).click();
  await expect(page.getByRole("img", { name: /Weekly doses of/ })).toBeVisible();
  await expect(page.getByText("Accuracy of this model in the latest backtest")).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "04-forecast");
  await page.getByRole("button", { name: "Table" }).click();
  await expect(page.getByText("High (80%)").first()).toBeVisible();
});

test("TC-S-03 register a child, record a dose, and see history and stock change", async ({ page }) => {
  const family = `E2e${Date.now()}`;
  await signIn(page, "e2e-hcw");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  await page.goto("/inventory");
  const bcg = page.getByRole("list", { name: "Current stock per vaccine" }).getByRole("listitem").filter({ hasText: /^BCG/ });
  await expect(bcg).toBeVisible();
  if (Number((await bcg.innerText()).match(/(\d+)\s*doses in stock/)?.[1] ?? 0) < 1) {
    await page.getByRole("tab", { name: "Ledger" }).click();
    await page.getByRole("combobox", { name: "Vaccine" }).click();
    await page.getByRole("option", { name: "BCG" }).click();
    await page.getByLabel("Doses").fill("40");
    await page.getByLabel("Date", { exact: true }).fill("2025-12-29");
    await page.getByRole("button", { name: "Save transaction" }).click();
    await expect(page.getByText("Saved.")).toBeVisible();
  }

  await page.goto("/children?tab=register");
  await page.getByLabel("Given name").fill("Zawadi");
  await page.getByLabel("Family name").fill(family);
  await page.getByLabel("Date of birth").fill("2025-12-20");
  await page.getByLabel("Caregiver name").fill("Test Caregiver");
  await shot(page, "05-register");
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByRole("heading", { name: `Zawadi ${family}` })).toBeVisible();

  await page.getByRole("combobox", { name: "Dose" }).click();
  await page.getByRole("option", { name: "BCG-1" }).click();
  await page.getByRole("button", { name: "Save dose" }).click();
  await expect(page.getByText("Dose recorded and issued from stock.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Immunization history (1)" })).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "06-child-record");

  await page.goto("/inventory?tab=ledger");
  await expect(page.getByText("BCG, issue").first()).toBeVisible();
});

test("TC-S-04 another facility finds the child by exact ID and gets a read-only record", async ({ page }) => {
  await signIn(page, "e2e-hcw");
  await page.goto("/children");
  const recent = page.getByRole(test.info().project.name === "phone" ? "list" : "table", {
    name: "The 10 children most recently registered at this facility",
  });
  await recent.getByRole("link").first().click();
  const systemId = (await page.getByText(/System ID IMM-/).innerText()).replace("System ID ", "").trim();
  await page.getByRole("button", { name: "Sign out" }).click();

  await signIn(page, "e2e-hcw-other");
  await page.goto("/children");
  await page.getByLabel("System ID").fill(systemId);
  await page.getByRole("button", { name: "Search" }).click();
  const found = page.getByRole(test.info().project.name === "phone" ? "list" : "table", { name: "1 matching children" });
  await found.getByRole("link").first().click();
  await expect(page.getByText("registered at another facility")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Record a dose" })).toHaveCount(0);
});

test("TC-S-05 the manager plans a session from the defaulter list and records attendance", async ({ page }) => {
  await signIn(page, "e2e-fm");
  await page.goto("/scheduling");
  await expect(page.getByRole("heading", { name: /Defaulters \(\d+\)/ })).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "07-defaulters");

  await page.getByRole("tab", { name: "Sessions" }).click();
  await page.getByRole("button", { name: "New session" }).click();
  await page.getByLabel("Date").fill("2025-12-29");
  await page.getByLabel("Location").fill(`Market ${Date.now()}`);
  await page.getByLabel("Capacity (children)").fill("3");
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("button", { name: "Generate plan" }).click();
  const children = page.getByRole("list", { name: "Children planned, in priority order" }).getByRole("listitem");
  await expect(children).toHaveCount(3);
  await expect(page.getByRole("heading", { name: "Vaccines needed" })).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "08-session-plan");

  await children.first().getByRole("button", { name: /Mark .* as not attended/ }).click();
  await expect(children.first().getByText("Did not attend")).toBeVisible();
  await expect(page.getByText(/outreach session, held/)).toBeVisible();
});

test("TC-S-06 the manager sees the audit log and import screen; the health worker does not", async ({ page }) => {
  await signIn(page, "e2e-fm");
  await page.goto("/audit");
  await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();
  await shot(page, "09-audit");
  await page.goto("/imports");
  await expect(page.getByRole("heading", { name: "Import data" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();

  await signIn(page, "e2e-hcw");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await page.goto("/audit");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});

test("TC-S-07 the administrator manages accounts and never reaches clinical screens", async ({ page }) => {
  await signIn(page, "e2e-admin");
  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "10-admin");
  await page.goto("/inventory");
  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: /Users \(\d+\)/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Deactivate e2e-admin" })).toBeDisabled();
  await expectNoSidewaysScroll(page);
  await shot(page, "11-admin-users");
});
