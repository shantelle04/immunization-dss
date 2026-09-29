import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppRoutes, ROUTER_FUTURE } from "./App";
import { api, setAccessToken } from "./api";
import { AuthProvider } from "./auth";

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
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const HCW = { username: "hcw-a", role: "healthcare_worker", facility: { code: "A", name: "Alpha Dispensary", level: "dispensary" } };

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

test("a health worker lands on the inventory table after signing in", async () => {
  routes["POST /api/v1/auth/login"] = () => ({ status: 200, body: { access: "token", user: HCW } });
  routes["GET /api/v1/stock/balance"] = () => ({
    status: 200,
    body: {
      as_of: "2025-12-29",
      rows: [{ antigen: "BCG", antigen_name: "BCG", balance_doses: 40, weekly_use_doses: 25, weeks_left: 1.6 }],
    },
  });
  routes["GET /api/v1/stock/transactions"] = () => ({ status: 200, body: { results: [] } });
  renderAt("/login");
  fireEvent.change(await screen.findByLabelText(/Username/), { target: { value: "hcw-a" } });
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "long-enough-pw" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Current stock (as of 2025-12-29)")).toBeInTheDocument();
  expect(screen.getByText("Low: under 2 weeks")).toBeInTheDocument();
  expect(screen.getByText("All records shown are synthetic.")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Administration" })).not.toBeInTheDocument();
});

test("an administrator never sees clinical screens", async () => {
  routes["POST /api/v1/auth/refresh"] = () => ({
    status: 200,
    body: { access: "token", user: { username: "admin", role: "system_admin", facility: null } },
  });
  routes["GET /api/v1/admin/users"] = () => ({ status: 200, body: { results: [] } });
  routes["GET /api/v1/admin/facilities"] = () => ({ status: 200, body: { results: [] } });
  renderAt("/inventory");
  expect(await screen.findByText("Create a user")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Inventory" })).not.toBeInTheDocument();
  expect(calls).not.toContain("GET /api/v1/stock/balance");
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
  routes["POST /api/v1/auth/refresh"] = () => ({ status: 200, body: { access: "token", user: HCW } });
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
  renderAt("/children");
  fireEvent.change(await screen.findByLabelText(/Given name/), { target: { value: "Baraka" } });
  fireEvent.change(screen.getAllByLabelText(/Family name/)[1], { target: { value: "Otieno" } });
  fireEvent.change(screen.getAllByLabelText(/Date of birth/)[1], { target: { value: "2025-06-01" } });
  fireEvent.change(screen.getByLabelText(/Caregiver name/), { target: { value: "Rehema" } });
  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  expect(await screen.findByText(/already registered here/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Register as new anyway" }));
  await waitFor(() => expect(calls.filter((c) => c === "POST /api/v1/children")).toHaveLength(2));
});
