import { QueryClient, onlineManager } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppRoutes, Providers, ROUTER_FUTURE } from "./App";
import { api, setAccessToken } from "./api";
import { chartPoints } from "./pages/ForecastChart";
import { templateCsv } from "./pages/FacilityPages";
import { ageBand, ageInFull, sexLabel } from "./ui";

type Handler = (init: RequestInit) => { status: number; body?: unknown };
let routes: Record<string, Handler>;
let calls: string[];

function json(status: number, body?: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response;
}

beforeEach(() => {
  jest.restoreAllMocks(); // the offline test stubs navigator.onLine
  onlineManager.setOnline(true);
  calls = [];
  setAccessToken(null);
  routes = { "POST /api/v1/auth/refresh": () => ({ status: 401, body: { detail: "Not signed in." } }) };
  globalThis.fetch = jest.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input).split("?")[0];
    const key = `${init.method ?? "GET"} ${url}`;
    calls.push(key);
    const handler = routes[key];
    const { status, body } = handler ? handler(init) : { status: 404, body: { detail: "no route" } };
    return Promise.resolve(json(status, body));
  }) as jest.Mock;
});

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <Providers client={client}>
      <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
        <AppRoutes />
      </MemoryRouter>
    </Providers>,
  );
}

const FACILITY = { code: "A", name: "Alpha Dispensary", level: "dispensary" };
const HCW = { username: "hcw-a", role: "healthcare_worker", facility: FACILITY };
const FM = { username: "fm-a", role: "facility_manager", facility: FACILITY };
const ALERT = {
  id: 7,
  antigen: "BCG",
  antigen_name: "BCG",
  raised_on: "2025-12-29",
  projected_breach_week: "2025-12-29",
  projected_doses: "-12.00",
  safety_minimum: "30.00",
  status: "open",
  acknowledged_by: null,
};
const OVERVIEW = {
  as_of: "2025-12-29",
  children_under_two: 120,
  defaulters: 9,
  children_with_due_dose: 14,
  doses_due_in_7_days: 6,
  alerts_open: 1,
  alerts_acknowledged: 0,
  antigens_low_stock: 2,
  antigens_out_of_stock: 0,
  next_session: null,
};
const BALANCE = {
  as_of: "2025-12-29",
  rows: [{ antigen: "BCG", antigen_name: "BCG", balance_doses: 40, weekly_use_doses: 25, weeks_left: 1.6 }],
};
const SERIES = {
  antigen: "BCG",
  antigen_name: "BCG",
  model: "moving_average",
  accuracy: { model: "moving_average", mase: 0.77, mae: 4.7, smape: 0.38, coverage80: 0.81 },
  history: [
    { week_start: "2025-12-15", issued: 8 },
    { week_start: "2025-12-22", issued: 10 },
  ],
  forecast: [
    { week_start: "2025-12-29", yhat: 9, lo80: 5, hi80: 14 },
    { week_start: "2026-01-05", yhat: 9, lo80: 5, hi80: 14 },
  ],
};

function signedIn(user: unknown) {
  routes["POST /api/v1/auth/refresh"] = () => ({ status: 200, body: { access: "token", user } });
  routes["GET /api/v1/alerts"] = () => ({ status: 200, body: { results: [ALERT] } });
  routes["GET /api/v1/dashboard"] = () => ({ status: 200, body: OVERVIEW });
  routes["GET /api/v1/stock/balance"] = () => ({ status: 200, body: BALANCE });
}

test("unauthenticated visitors are sent to the login page", async () => {
  renderAt("/inventory");
  expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
});

test("a refused login shows the server's generic message", async () => {
  routes["POST /api/v1/auth/login"] = () => ({ status: 401, body: { detail: "Username or password incorrect." } });
  renderAt("/login");
  fireEvent.change(await screen.findByLabelText(/Username/), { target: { value: "x" } });
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "y" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Username or password incorrect.")).toBeInTheDocument();
});

test("a health worker lands on the overview with counts, alerts and the synthetic-data notice", async () => {
  signedIn(null);
  routes["POST /api/v1/auth/refresh"] = () => ({ status: 401 });
  routes["POST /api/v1/auth/login"] = () => ({ status: 200, body: { access: "token", user: HCW } });
  renderAt("/login");
  fireEvent.change(await screen.findByLabelText(/Username/), { target: { value: "hcw-a" } });
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "long-enough-pw" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("link", { name: "Defaulters: 9" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Stock-out alerts: 1" })).toBeInTheDocument();
  expect(await screen.findByText(/projected to run out/)).toBeInTheDocument();
  expect(screen.getByText("All records shown are synthetic.")).toBeInTheDocument();
  const nav = screen.getAllByRole("navigation", { name: "Sections" })[0];
  expect(within(nav).getByText("Stock")).toBeInTheDocument();
  expect(within(nav).queryByText("Users")).not.toBeInTheDocument();
  expect(within(nav).queryByText("Import data")).not.toBeInTheDocument();
});

test("the stock screen shows the status of each vaccine in words, not colour alone", async () => {
  signedIn(HCW);
  renderAt("/inventory");
  const list = await screen.findByRole("list", { name: "Current stock per vaccine" });
  expect(within(list).getByText("Low: under 2 weeks")).toBeInTheDocument();
  expect(within(list).getByText(/25 doses used per week; 1.6 weeks left/)).toBeInTheDocument();
});

test("only the facility manager can acknowledge a stock-out alert", async () => {
  signedIn(HCW);
  const first = renderAt("/inventory");
  expect(await screen.findByText(/projected to run out/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Acknowledge BCG alert" })).not.toBeInTheDocument();
  first.unmount();

  signedIn(FM);
  routes["POST /api/v1/alerts/7/acknowledge"] = () => ({ status: 200, body: { ...ALERT, status: "acknowledged" } });
  renderAt("/inventory");
  fireEvent.click(await screen.findByRole("button", { name: "Acknowledge BCG alert" }));
  await waitFor(() => expect(calls).toContain("POST /api/v1/alerts/7/acknowledge"));
});

test("the forecast has a table alternative with the 80% interval, the model and its accuracy", async () => {
  signedIn(HCW);
  routes["GET /api/v1/forecasts"] = () => ({
    status: 200,
    body: { run: { run_at: "2025-12-29T06:00:00Z", source: "baselines", as_of: "2025-12-29", data_sha256: "x" }, antigens: [SERIES] },
  });
  renderAt("/inventory?tab=forecast");
  expect(await screen.findByRole("img", { name: /Weekly doses of BCG/ })).toBeInTheDocument();
  expect(screen.getByText(/Moving average \(last 4 weeks\)/)).toBeInTheDocument();
  expect(screen.getByText("0.77")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Table" }));
  const table = await screen.findByRole("table");
  expect(within(table).getByText("High (80%)")).toBeInTheDocument();
  expect(within(table).getAllByText("14")).toHaveLength(2);
});

test("the forecast line joins the last observed week and carries the interval only for future weeks", () => {
  const points = chartPoints(SERIES);
  expect(points).toHaveLength(4);
  expect(points[1]).toEqual({ week: "2025-12-22", issued: 10, forecast: 10 });
  expect(points[2]).toEqual({ week: "2025-12-29", forecast: 9, band: [5, 14] });
});

test("an administrator never sees clinical screens", async () => {
  routes["POST /api/v1/auth/refresh"] = () => ({
    status: 200,
    body: { access: "token", user: { username: "admin", role: "system_admin", facility: null } },
  });
  routes["GET /api/v1/admin/overview"] = () => ({
    status: 200,
    body: {
      users_by_role: { system_admin: 1, healthcare_worker: 12 },
      users_inactive: 0,
      users_locked: 0,
      facilities: 12,
      logins_7_days: 3,
      failed_logins_7_days: 1,
      lockouts_7_days: 0,
      forecast_run: null,
    },
  });
  renderAt("/inventory");
  expect(await screen.findByText("The forecast job has not run yet.")).toBeInTheDocument();
  const nav = screen.getAllByRole("navigation", { name: "Sections" })[0];
  expect(within(nav).getByText("Users")).toBeInTheDocument();
  expect(within(nav).queryByText("Stock")).not.toBeInTheDocument();
  expect(calls).not.toContain("GET /api/v1/stock/balance");
  expect(calls).not.toContain("GET /api/v1/dashboard");
});

test("an expired access token is refreshed once and the request retried", async () => {
  let first = true;
  routes["GET /api/v1/defaulters"] = () => {
    if (first) {
      first = false;
      return { status: 401 };
    }
    return { status: 200, body: { count: 0 } };
  };
  routes["POST /api/v1/auth/refresh"] = () => ({ status: 200, body: { access: "new", user: HCW } });
  await expect(api("/defaulters")).resolves.toEqual({ count: 0 });
  expect(calls).toEqual(["GET /api/v1/defaulters", "POST /api/v1/auth/refresh", "GET /api/v1/defaulters"]);
});

test("registering a likely duplicate asks before creating a new record", async () => {
  signedIn(HCW);
  routes["POST /api/v1/children"] = (init) => {
    const body = JSON.parse(String(init.body));
    return body.confirm_new
      ? { status: 201, body: { id: "new-id", system_id: "IMM-A-00002" } }
      : {
          status: 409,
          body: {
            detail: "duplicate",
            candidates: [{ id: "c1", system_id: "IMM-A-00001", given_name: "Amani", family_name: "Otieno" }],
          },
        };
  };
  routes["GET /api/v1/children/new-id/immunizations"] = () => ({ status: 404 });
  renderAt("/children?tab=register");
  fireEvent.change(await screen.findByLabelText(/Given name/), { target: { value: "Baraka" } });
  fireEvent.change(screen.getByLabelText(/Family name/), { target: { value: "Otieno" } });
  fireEvent.change(screen.getByLabelText(/Date of birth/), { target: { value: "2025-06-01" } });
  fireEvent.change(screen.getByLabelText(/Caregiver name/), { target: { value: "Rehema" } });
  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  expect(await screen.findByText(/already registered here/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Register as new anyway" }));
  await waitFor(() => expect(calls.filter((c) => c === "POST /api/v1/children")).toHaveLength(2));
});

test("a session plan shows shortfalls and records attendance with the chosen doses", async () => {
  signedIn(HCW);
  const detail = {
    id: 3,
    date: "2025-12-29",
    kind: "outreach",
    location_name: "Market",
    capacity: 10,
    status: "planned",
    children: [
      {
        rank: 1,
        child_id: "c1",
        system_id: "IMM-A-00001",
        name: "Amani Otieno",
        caregiver_name: "Rehema",
        date_of_birth: "2025-06-01",
        attended: null,
        doses: [
          { dose_code: "PENTA-1", given: false },
          { dose_code: "OPV-1", given: false },
        ],
      },
    ],
    needs: [
      {
        antigen: "PENTA",
        antigen_name: "Pentavalent",
        doses_planned: 1,
        vials_planned: 1,
        in_stock_doses: 0,
        forecast_week_doses: 20,
        shortfall_doses: 1,
        shortfall_with_forecast_doses: 21,
      },
    ],
  };
  let sent: unknown;
  routes["GET /api/v1/sessions/3"] = () => ({ status: 200, body: detail });
  routes["POST /api/v1/sessions/3/attendance"] = (init) => {
    sent = JSON.parse(String(init.body));
    return { status: 201, body: { ...detail, status: "held" } };
  };
  renderAt("/scheduling/sessions/3");
  expect(await screen.findByText(/Not enough stock for this plan: Pentavalent \(short by 1\)/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Generate plan" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "OPV-1" }));
  fireEvent.click(screen.getByRole("button", { name: "Record attendance and doses for Amani Otieno" }));
  await waitFor(() => expect(sent).toEqual({ child_id: "c1", attended: true, doses: ["PENTA-1"] }));
});

test("going offline shows a notice and blocks saving, keeping the loaded data on screen", async () => {
  signedIn(HCW);
  routes["GET /api/v1/stock/transactions"] = () => ({ status: 200, body: { results: [] } });
  renderAt("/inventory?tab=ledger");
  const save = await screen.findByRole("button", { name: "Save transaction" });
  expect(save).toBeEnabled();
  jest.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  act(() => {
    window.dispatchEvent(new Event("offline"));
  });
  expect(await screen.findByText(/You are offline/)).toBeInTheDocument();
  expect(save).toBeDisabled();
  expect(screen.getByText("Record a stock transaction")).toBeInTheDocument();
  jest.restoreAllMocks();
});

test("import templates start with the exact columns the server expects and use the manager's facility", () => {
  const [header, example] = templateCsv("immunizations", "SYN-D01").trim().split("\n");
  expect(header).toBe("child_system_id,date_of_birth,dose_code,given_on,facility_code,lot_number");
  expect(example.split(",")[4]).toBe("SYN-D01");
  expect(templateCsv("stock", "SYN-D01").split("\n")[0]).toBe(
    "date,facility_code,antigen_code,lot_number,kind,quantity_doses",
  );
});

const OTHER_FACILITY = { code: "B", name: "Beta Health Centre", level: "health_centre" };
const DEMO_ACCOUNTS = [
  { username: "admin", role: "system_admin", facility: null },
  HCW,
  FM,
  { username: "hcw-b", role: "healthcare_worker", facility: OTHER_FACILITY },
];

test("age is stated the way a clinic card states it, and sex in words", () => {
  expect(ageInFull(3)).toBe("3 days");
  expect(ageInFull(20)).toBe("2 weeks");
  expect(ageInFull(211)).toBe("6 months");
  expect(ageInFull(800)).toBe("2 years 2 months");
  expect(ageInFull(731)).toBe("2 years");
  expect(ageBand(150).key).toBe("0-5");
  expect(ageBand(400).key).toBe("12-17");
  expect(ageBand(729).key).toBe("18-23");
  expect(sexLabel("F")).toBe("Female");
  expect(sexLabel("M")).toBe("Male");
});

test("no account picker appears unless the server offers demonstration accounts", async () => {
  renderAt("/login");
  expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  await waitFor(() => expect(calls).toContain("GET /api/v1/auth/demo"));
  expect(screen.queryByText("Demonstration only")).not.toBeInTheDocument();
});

test("in demonstration mode a role is picked per facility, labelled as demo only", async () => {
  routes["GET /api/v1/auth/demo"] = () => ({ status: 200, body: { accounts: DEMO_ACCOUNTS } });
  let chosen = "";
  routes["POST /api/v1/auth/demo"] = (init) => {
    chosen = JSON.parse(String(init.body)).username;
    return { status: 200, body: { access: "token", user: FM } };
  };
  signedIn(null);
  routes["POST /api/v1/auth/refresh"] = () => ({ status: 401 });
  renderAt("/login");
  expect(await screen.findByText("Demonstration only")).toBeInTheDocument();
  expect(screen.getByText(/In real use every person signs in with their own username and password/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Sign in as facility manager/ }));
  expect(await screen.findByText(/Demonstration mode: signed in as fm-a/)).toBeInTheDocument();
  expect(chosen).toBe("fm-a");
});

test("switching account signs out and never shows the previous account's cached data", async () => {
  routes["GET /api/v1/auth/demo"] = () => ({ status: 200, body: { accounts: DEMO_ACCOUNTS } });
  routes["POST /api/v1/auth/logout"] = () => ({ status: 204 });
  signedIn(HCW);
  renderAt("/overview");
  expect(await screen.findByRole("link", { name: "Defaulters: 9" })).toBeInTheDocument();
  routes["POST /api/v1/auth/refresh"] = () => ({ status: 401 });
  fireEvent.click(await screen.findByRole("button", { name: "Switch account" }));
  expect(await screen.findByText("Demonstration only")).toBeInTheDocument();
  expect(calls).toContain("POST /api/v1/auth/logout");
  routes["GET /api/v1/dashboard"] = () => ({ status: 200, body: { ...OVERVIEW, defaulters: 4 } });
  routes["POST /api/v1/auth/demo"] = () => ({
    status: 200,
    body: { access: "token", user: { ...HCW, username: "hcw-b", facility: OTHER_FACILITY } },
  });
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Facility" }));
  fireEvent.click(await screen.findByRole("option", { name: /Beta Health Centre/ }));
  fireEvent.click(screen.getByRole("button", { name: /Sign in as health worker/ }));
  expect(await screen.findByRole("link", { name: "Defaulters: 4" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Defaulters: 9" })).not.toBeInTheDocument();
});

test("signing out still ends the session in the browser when the server call fails", async () => {
  signedIn(HCW);
  routes["POST /api/v1/auth/logout"] = () => {
    throw new Error("network down");
  };
  renderAt("/overview");
  const out = await screen.findAllByRole("button", { name: "Sign out" });
  routes["POST /api/v1/auth/refresh"] = () => ({ status: 401 });
  fireEvent.click(out[0]);
  expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
});

const CHILD = {
  id: "c1",
  system_id: "IMM-A-00001",
  given_name: "Amani",
  family_name: "Otieno",
  sex: "F",
  date_of_birth: "2025-06-01",
  caregiver_name: "Rehema Otieno",
  registration_facility: "A",
  registered_on: "2025-06-01",
  is_synthetic: true,
  age_days: 211,
};

test("the child record describes the child: sex, age and age group on the clinical date", async () => {
  signedIn(HCW);
  routes["GET /api/v1/children/c1/immunizations"] = () => ({
    status: 200,
    body: { as_of: "2025-12-29", read_only: false, child: CHILD, history: [], doses: [], schedule: [] },
  });
  renderAt("/children/c1");
  const details = await screen.findByLabelText("Child details");
  expect(within(details).getByText("Female")).toBeInTheDocument();
  expect(within(details).getByText("6 months")).toBeInTheDocument();
  expect(within(details).getByText("6 to 11 months")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Edit details" })).toHaveAttribute("href", "/children/c1/edit");
});

test("editing a child sends only the changed fields and shows the server's refusal", async () => {
  signedIn(HCW);
  routes["GET /api/v1/children/c1"] = () => ({ status: 200, body: { ...CHILD, read_only: false } });
  let sent: unknown = null;
  routes["PATCH /api/v1/children/c1"] = (init) => {
    sent = JSON.parse(String(init.body));
    return { status: 400, body: { date_of_birth: ["With this date of birth, OPV-0 would fall outside its age window."] } };
  };
  renderAt("/children/c1/edit");
  const save = await screen.findByRole("button", { name: "Save changes" });
  expect(save).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Caregiver name/), { target: { value: "Juma Otieno" } });
  fireEvent.click(save);
  expect(await screen.findByText(/OPV-0 would fall outside its age window/)).toBeInTheDocument();
  expect(sent).toEqual({ caregiver_name: "Juma Otieno" });
});

test("a record from another facility cannot be edited", async () => {
  signedIn(HCW);
  routes["GET /api/v1/children/c1"] = () => ({ status: 200, body: { ...CHILD, registration_facility: "B", read_only: true } });
  renderAt("/children/c1/edit");
  expect(await screen.findByText(/Only that facility can correct the details/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
});

test("defaulters are described by sex and age group and can be filtered by both", async () => {
  signedIn(FM);
  const row = (n: number, sex: string, age_days: number) => ({
    rank: n,
    child_id: `c${n}`,
    system_id: `IMM-A-0000${n}`,
    name: `Child ${n}`,
    sex,
    age_days,
    overdue_count: 1,
    overdue: ["MR-1"],
    days_to_nearest_max_age: 100,
  });
  routes["GET /api/v1/defaulters"] = () => ({
    status: 200,
    body: { as_of: "2025-12-29", count: 3, results: [row(1, "F", 300), row(2, "M", 300), row(3, "F", 600)] },
  });
  routes["GET /api/v1/sessions"] = () => ({ status: 200, body: { results: [] } });
  renderAt("/scheduling");
  const bySex = await screen.findByRole("table", { name: "Defaulters by sex" });
  expect(within(bySex).getByRole("row", { name: /Female 2 67%/ })).toBeInTheDocument();
  const byAge = screen.getByRole("table", { name: "Defaulters by age group" });
  expect(within(byAge).getByRole("row", { name: /6 to 11 months 2 67% 1 \/ 1/ })).toBeInTheDocument();
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Sex" }));
  fireEvent.click(await screen.findByRole("option", { name: "Male" }));
  expect(await screen.findByText(/1 of 3 shown/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "2. Child 2" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "1. Child 1" })).not.toBeInTheDocument();
});
