import { CssBaseline, ThemeProvider } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import type { Role } from "./api";
import { AuthProvider } from "./auth";
import { AdminFacilitiesPage, AdminOverviewPage, AdminSchedulePage, AdminUsersPage } from "./pages/AdminPage";
import ChildPage from "./pages/ChildPage";
import ChildrenPage from "./pages/ChildrenPage";
import { AuditPage, ImportPage, MorePage, SchedulePage } from "./pages/FacilityPages";
import InventoryPage from "./pages/InventoryPage";
import LoginPage from "./pages/LoginPage";
import OverviewPage from "./pages/OverviewPage";
import SchedulingPage from "./pages/SchedulingPage";
import SessionPage from "./pages/SessionPage";
import { Home, RequireRole } from "./routes";
import { Layout } from "./shell";
import { theme } from "./theme";

export const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };
const CLINICAL: Role[] = ["healthcare_worker", "facility_manager"];
const MANAGER: Role[] = ["facility_manager"];
const ADMIN: Role[] = ["system_admin"];

const PAGES: { path: string; roles: Role[]; element: ReactNode }[] = [
  { path: "/overview", roles: CLINICAL, element: <OverviewPage /> },
  { path: "/inventory", roles: CLINICAL, element: <InventoryPage /> },
  { path: "/scheduling", roles: CLINICAL, element: <SchedulingPage /> },
  { path: "/scheduling/sessions/:id", roles: CLINICAL, element: <SessionPage /> },
  { path: "/children", roles: CLINICAL, element: <ChildrenPage /> },
  { path: "/children/:id", roles: CLINICAL, element: <ChildPage /> },
  { path: "/schedule", roles: CLINICAL, element: <SchedulePage /> },
  { path: "/more", roles: CLINICAL, element: <MorePage /> },
  { path: "/imports", roles: MANAGER, element: <ImportPage /> },
  { path: "/audit", roles: MANAGER, element: <AuditPage /> },
  { path: "/admin", roles: ADMIN, element: <AdminOverviewPage /> },
  { path: "/admin/users", roles: ADMIN, element: <AdminUsersPage /> },
  { path: "/admin/facilities", roles: ADMIN, element: <AdminFacilitiesPage /> },
  { path: "/admin/schedule", roles: ADMIN, element: <AdminSchedulePage /> },
];

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Home />} />
      <Route
        element={
          <RequireRole roles={[...CLINICAL, ...ADMIN]}>
            <Layout />
          </RequireRole>
        }
      >
        {PAGES.map((p) => (
          <Route key={p.path} path={p.path} element={<RequireRole roles={p.roles}>{p.element}</RequireRole>} />
        ))}
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}

export function Providers({ children, client }: { children: ReactNode; client: QueryClient }) {
  return (
    <ThemeProvider theme={theme} defaultMode="system">
      <CssBaseline />
      <QueryClientProvider client={client}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default function App() {
  // Offline (FR-42): loaded data stays on screen from memory; nothing clinical is written to device storage.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, staleTime: 30_000, gcTime: 60 * 60_000, networkMode: "offlineFirst" },
        },
      }),
  );
  return (
    <Providers client={queryClient}>
      <BrowserRouter future={ROUTER_FUTURE}>
        <AppRoutes />
      </BrowserRouter>
    </Providers>
  );
}
