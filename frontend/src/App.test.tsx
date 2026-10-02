import { QueryClient } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppRoutes, Providers, ROUTER_FUTURE } from "./App";
import { api, setAccessToken } from "./api";
import { chartPoints } from "./pages/ForecastChart";

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
