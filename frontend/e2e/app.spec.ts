import { expect, test, type Locator, type Page } from "@playwright/test";
import path from "node:path";

const PASSWORD = process.env.E2E_PASSWORD ?? "";
const SHOTS = process.env.E2E_SHOTS ?? "";

async function signIn(page: Page, username: string) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

// Demonstration sign-in (D-46): the e2e server runs with IMMDSS_DEMO_LOGIN on and its test accounts flagged.
async function demoSignIn(page: Page, role: "health worker" | "facility manager" | "system administrator") {
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(`Sign in as ${role}`) }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
}

// Every section of the page, not only the part in the window. The window is stretched to the page's height
// rather than using a full-page capture, so fixed bars (side menu, bottom navigation) stay where they belong.
async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  const project = test.info().project.name;
  const size = page.viewportSize()!;
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width: size.width, height: Math.max(size.height, height) });
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, `F-UI-${name}_${project}.png`) });
  await page.setViewportSize(size);
}

async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page must not scroll sideways").toBeLessThanOrEqual(1);
}

function phone(): boolean {
  return test.info().project.name === "phone";
}

// DataList renders a table on wide screens and a list of cards on phones.
function dataList(page: Page | Locator, name: string | RegExp): Locator {
  return page.getByRole(phone() ? "list" : "table", { name });
}

async function pick(page: Page, label: string, option: string | RegExp) {
  await page.getByRole("combobox", { name: label }).click();
  const options =
    typeof option === "string" ? page.getByRole("option", { name: option, exact: true }) : page.getByRole("option", { name: option });
  await options.first().click();
  await expect(page.getByRole("listbox")).toHaveCount(0);
}

test.beforeAll(() => {
  expect(PASSWORD.length, "E2E_PASSWORD is set by scripts/dev.py e2e").toBeGreaterThan(15);
});

test("TC-S-01 real-use sign-in: own credentials only, and a wrong password gets the generic refusal", async ({
  page,
}) => {
  // As on a real installation, where the server answers 404 and no account picker exists.
  await page.route("**/api/v1/auth/demo", (route) => route.fulfill({ status: 404, body: "{}" }));
  await page.goto("/login");
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByText("Demonstration only")).toHaveCount(0);
  await shot(page, "01-login");
  await page.getByLabel("Username").fill("e2e-hcw");
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Username or password incorrect.")).toBeVisible();
  await expectNoSidewaysScroll(page);
});

test("TC-S-08 demonstration mode: pick a role, see the banner, switch account, sign out", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Demonstration only")).toBeVisible();
  await expect(page.getByText(/In real use every person signs in with their own username and password/)).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "02-login-demo");

  await demoSignIn(page, "health worker");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText(phone() ? "Demo: e2e-hcw" : /Demonstration mode: signed in as e2e-hcw/)).toBeVisible();

  await page.getByRole("button", { name: "Switch account" }).click();
  await expect(page.getByText("Demonstration only")).toBeVisible();
  await page.getByRole("button", { name: /Sign in as facility manager/ }).click();
  await expect(page.getByText(phone() ? "Demo: e2e-fm" : /Demonstration mode: signed in as e2e-fm/)).toBeVisible();
  await page.goto("/audit");
  await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();

  await page.getByRole("button", { name: "Switch account" }).click();
  await pick(page, "Facility", /\(.*\)$/);
  await page.getByRole("button", { name: /Sign in as system administrator/ }).click();
  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
  await expect(page.getByText(phone() ? "Demo: e2e-admin" : /signed in as e2e-admin/)).toBeVisible();

  await signOut(page);
  await page.reload();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/login$/);
});

test("TC-S-09 the other facility's health worker is offered by facility in demonstration mode", async ({ page }) => {
  await page.goto("/login");
  const facility = page.getByRole("combobox", { name: "Facility" });
  await facility.click();
  const options = page.getByRole("option");
  await expect(options).toHaveCount(2);
  await options.nth(1).click();
  await page.getByRole("button", { name: /Sign in as health worker/ }).click();
  await expect(page.getByText(phone() ? "Demo: e2e-hcw-other" : /signed in as e2e-hcw-other/)).toBeVisible();
});

test("TC-S-02 a health worker sees the overview, stock, forecast and ledger", async ({ page }) => {
  await signIn(page, "e2e-hcw");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Defaulters: \d+/ })).toBeVisible();
  await expect(page.getByText("All records shown are synthetic.")).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "03-overview");

  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Stock" }).click();
  await expect(page.getByRole("list", { name: "Current stock per vaccine" }).getByRole("listitem")).toHaveCount(7);
  await expectNoSidewaysScroll(page);
  await shot(page, "04-stock-and-alerts");

  await page.getByRole("tab", { name: "Forecast" }).click();
  await expect(page.getByRole("img", { name: /Weekly doses of/ })).toBeVisible();
  await expect(page.getByText("Accuracy of this model in the latest backtest")).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "05-forecast");
  await page.getByRole("button", { name: "Table" }).click();
  await expect(page.getByText("High (80%)").first()).toBeVisible();
  await shot(page, "06-forecast-table");

  await page.getByRole("tab", { name: "Ledger" }).click();
  await expect(page.getByRole("heading", { name: "Record a stock transaction" })).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "07-ledger");

  await page.getByRole("tab", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Replenishment and safety buffer" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Edit .* policy/ })).toHaveCount(0);
});

test("TC-S-10 the manager edits a stock policy and acknowledges an alert", async ({ page }) => {
  await signIn(page, "e2e-fm");
  await page.goto("/inventory?tab=settings");
  const policies = dataList(page, "Stock policy per vaccine");
  await expect(policies).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "08-stock-settings");

  await page.getByRole("button", { name: "Edit BCG policy" }).click();
  const buffer = page.getByLabel("Safety buffer (0.25 means 25%)");
  const original = await buffer.inputValue();
  await buffer.fill("0.4");
  await shot(page, "09-stock-policy-edit");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(policies.getByText("40%").first()).toBeVisible();
  await page.getByRole("button", { name: "Edit BCG policy" }).click();
  await page.getByLabel("Safety buffer (0.25 means 25%)").fill(original);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.goto("/inventory");
  const acknowledge = page.getByRole("button", { name: /Acknowledge .* alert/ }).first();
  if (await acknowledge.count()) {
    await acknowledge.click();
    await expect(page.getByText("Acknowledged by e2e-fm.").first()).toBeVisible();
  }
});

test("TC-S-03 register a child, see sex and age, record a dose, edit the details", async ({ page }) => {
  const family = `E2e${Date.now()}`;
  await signIn(page, "e2e-hcw");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  await page.goto("/inventory");
  const bcg = page.getByRole("list", { name: "Current stock per vaccine" }).getByRole("listitem").filter({ hasText: /^BCG/ });
  await expect(bcg).toBeVisible();
  if (Number((await bcg.innerText()).match(/(\d+)\s*doses in stock/)?.[1] ?? 0) < 1) {
    await page.getByRole("tab", { name: "Ledger" }).click();
    await pick(page, "Vaccine", "BCG");
    await page.getByLabel("Doses").fill("40");
    await page.getByLabel("Date", { exact: true }).fill("2025-12-29");
    await page.getByRole("button", { name: "Save transaction" }).click();
    await expect(page.getByText("Saved.")).toBeVisible();
  }

  await page.goto("/children?tab=register");
  await page.getByLabel("Given name").fill("Zawadi");
  await page.getByLabel("Family name").fill(family);
  await pick(page, "Sex", "Male");
  await page.getByLabel("Date of birth").fill("2025-12-20");
  await page.getByLabel("Caregiver name").fill("Test Caregiver");
  await shot(page, "15-register");
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByRole("heading", { name: `Zawadi ${family}` })).toBeVisible();
  const details = page.getByLabel("Child details");
  await expect(details.getByText("Male", { exact: true })).toBeVisible();
  await expect(details.getByText("1 week", { exact: true })).toBeVisible();
  await expect(details.getByText("0 to 5 months")).toBeVisible();

  await pick(page, "Dose", "BCG-1");
  await page.getByRole("button", { name: "Save dose" }).click();
  await expect(page.getByText("Dose recorded and issued from stock.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Immunization history (1)" })).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "16-child-record");

  await page.getByRole("link", { name: "Edit details" }).click();
  await expect(page.getByRole("heading", { name: "Edit child details" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await page.getByLabel("Date of birth").fill("2020-01-01");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/BCG-1 given on .* would fall outside its age window/)).toBeVisible();
  await page.getByLabel("Date of birth").fill("2025-12-20");
  await pick(page, "Sex", "Female");
  await page.getByLabel("Caregiver name").fill("Corrected Caregiver");
  await expectNoSidewaysScroll(page);
  await shot(page, "17-child-edit");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Details saved.")).toBeVisible();
  await expect(details.getByText("Female", { exact: true })).toBeVisible();
  await expect(details.getByText("Corrected Caregiver")).toBeVisible();

  await page.goto("/inventory?tab=ledger");
  await expect(page.getByText("BCG, issue").first()).toBeVisible();
});

test("TC-S-04 another facility finds the child by exact ID and gets a read-only record", async ({ page }) => {
  await signIn(page, "e2e-hcw");
  await page.goto("/children");
  const recent = dataList(page, "The 10 children most recently registered at this facility");
  await expect(recent).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "14-children-find");
  await recent.getByRole("link").first().click();
  const systemId = (await page.getByText(/System ID IMM-/).innerText()).replace("System ID ", "").trim();
  const childUrl = page.url();
  await signOut(page);

  await signIn(page, "e2e-hcw-other");
  await page.goto("/children");
  await page.getByLabel("System ID").fill(systemId);
  await page.getByRole("button", { name: "Search" }).click();
  const found = dataList(page, "1 matching children");
  await expect(found.getByText(/Female|Male/).first()).toBeVisible();
  await found.getByRole("link").first().click();
  await expect(page.getByText("registered at another facility")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Record a dose" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Edit details" })).toHaveCount(0);
  await shot(page, "18-child-read-only");
  await page.goto(`${new URL(childUrl).pathname}/edit`);
  await expect(page.getByText("Only that facility can correct the details.")).toBeVisible();
});

test("TC-S-05 the manager reviews who is overdue, plans a session and records attendance", async ({ page }) => {
  await signIn(page, "e2e-fm");
  await page.goto("/scheduling");
  await expect(page.getByRole("heading", { name: /Defaulters \(\d+\)/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Who is overdue" })).toBeVisible();
  await expect(dataList(page, "Defaulters by sex")).toBeVisible();
  await expect(dataList(page, "Defaulters by age group")).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "10-defaulters");

  await pick(page, "Sex", "Female");
  await pick(page, "Age group", "12 to 17 months");
  await expect(page.getByText(/\d+ of \d+ shown/)).toBeVisible();
  const ranked = dataList(page, "Prioritised defaulter list for outreach planning");
  const firstAge = ranked.getByText(/^1[2-7] months$/).first();
  if (await firstAge.count()) await expect(firstAge).toBeVisible();
  await shot(page, "11-defaulters-filtered");

  await page.getByRole("tab", { name: "Sessions" }).click();
  await page.getByRole("button", { name: "New session" }).click();
  await page.getByLabel("Date").fill("2025-12-29");
  await page.getByLabel("Location").fill(`Market ${Date.now()}`);
  await page.getByLabel("Capacity (children)").fill("3");
  await shot(page, "12-session-new");
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("button", { name: "Generate plan" }).click();
  const children = page.getByRole("list", { name: "Children planned, in priority order" }).getByRole("listitem");
  await expect(children).toHaveCount(3);
  await expect(children.first().getByText(/(Female|Male), .* on the session day/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Vaccines needed" })).toBeVisible();

  await children.first().getByRole("button", { name: /Mark .* as not attended/ }).click();
  await expect(children.first().getByText("Did not attend")).toBeVisible();
  await expect(page.getByText(/outreach session, held/)).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "13-session-plan");

  await page.goto("/scheduling?tab=sessions");
  await expect(dataList(page, "The latest 30 sessions of this facility")).toBeVisible();
});

test("TC-S-06 the manager's facility pages; the health worker cannot reach them", async ({ page }) => {
  await signIn(page, "e2e-fm");
  await page.goto("/schedule");
  await expect(page.getByRole("heading", { name: "Vaccine schedule" })).toBeVisible();
  await shot(page, "19-vaccine-schedule");

  await page.goto("/imports");
  await expect(page.getByRole("heading", { name: "Import data" })).toBeVisible();
  const header = "child_system_id,date_of_birth,dose_code,given_on,facility_code,lot_number";
  await page.locator('input[type="file"]').setInputFiles({
    name: "check.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(`${header}\nIMM-NONE-99999,2025-01-06,MR-1,2025-12-29,NONE,\n`),
  });
  await page.getByRole("button", { name: "Check file" }).click();
  await expect(page.getByText(/1 rows read, 1 rejected\. Nothing was saved \(dry run\)\./)).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "20-import-check");

  await page.goto("/audit");
  await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();
  await shot(page, "21-audit");

  await page.goto("/more");
  await expect(page.getByRole("heading", { name: "More" })).toBeVisible();
  await shot(page, "22-more");
  await signOut(page);

  await signIn(page, "e2e-hcw");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await page.goto("/audit");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await page.goto("/imports");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});

test("TC-S-07 the administrator manages accounts, facilities and the schedule, never clinical screens", async ({
  page,
}) => {
  const stamp = String(Date.now()).slice(-6);
  await signIn(page, "e2e-admin");
  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
  await expectNoSidewaysScroll(page);
  await shot(page, "23-admin");
  await page.goto("/inventory");
  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
  await page.goto("/children/00000000-0000-0000-0000-000000000000/edit");
  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();

  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: /Users \(\d+\)/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Deactivate e2e-admin" })).toBeDisabled();
  await expectNoSidewaysScroll(page);
  await shot(page, "24-admin-users");

  const username = `e2e-new-${stamp}`;
  await page.getByRole("button", { name: "Create a user" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Username").fill(username);
  await pick(page, "Facility", /.+/);
  await dialog.getByLabel("Initial password (12+ characters)").fill(`Pw-${stamp}-long-enough-x`);
  await shot(page, "25-admin-user-new");
  await dialog.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("button", { name: `Deactivate ${username}` })).toBeVisible();
  await page.getByRole("button", { name: `Deactivate ${username}` }).click();
  await expect(page.getByRole("button", { name: `Activate ${username}` })).toBeVisible();
  await page.getByRole("button", { name: `Activate ${username}` }).click();
  await expect(page.getByRole("button", { name: `Deactivate ${username}` })).toBeVisible();
  await page.getByRole("button", { name: `Set a new password for ${username}` }).click();
  await page.getByLabel("New password (12+ characters)").fill(`New-${stamp}-long-enough-y`);
  await shot(page, "26-admin-user-password");
  await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.goto("/admin/facilities");
  await expect(page.getByRole("heading", { name: /Facilities \(\d+\)/ })).toBeVisible();
  await shot(page, "27-admin-facilities");
  await page.getByRole("button", { name: "Add a facility" }).click();
  const facility = page.getByRole("dialog");
  await facility.getByLabel(/^Code/).fill(`E2E-${stamp}`);
  await facility.getByLabel(/^Name/).fill(`Test Clinic ${stamp}`);
  await facility.getByLabel("Ownership").fill("public");
  await facility.getByLabel(/^County/).fill("Test County");
  await facility.getByLabel("Sub-county").fill("Test Sub-county");
  await shot(page, "28-admin-facility-new");
  await facility.getByRole("button", { name: /Add|Create|Save/ }).click();
  await expect(page.getByText(`Test Clinic ${stamp}`)).toBeVisible();

  await page.goto("/admin/schedule");
  await expect(page.getByRole("heading", { name: "Schedule" })).toBeVisible();
  await shot(page, "29-admin-schedule");
  await page.getByRole("button", { name: "Edit MR-2" }).click();
  const interval = page.getByLabel("Minimum interval after the previous dose (days)");
  const original = await interval.inputValue();
  await interval.fill(String(Number(original) + 1));
  await shot(page, "30-admin-schedule-edit");
  await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Edit MR-2" }).click();
  await expect(page.getByLabel("Minimum interval after the previous dose (days)")).toHaveValue(String(Number(original) + 1));
  await page.getByLabel("Minimum interval after the previous dose (days)").fill(original);
  await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
