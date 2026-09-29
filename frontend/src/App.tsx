import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { Layout } from "./components";
import AdminPage from "./pages/AdminPage";
import ChildPage from "./pages/ChildPage";
import ChildrenPage from "./pages/ChildrenPage";
import InventoryPage from "./pages/InventoryPage";
import LoginPage from "./pages/LoginPage";
import SchedulingPage from "./pages/SchedulingPage";
import { Home, RequireRole } from "./routes";

const theme = createTheme({ palette: { primary: { main: "#2a78d6" } } });
export const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };
const CLINICAL = ["healthcare_worker", "facility_manager"] as const;

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Home />} />
      <Route
        element={
          <RequireRole roles={[...CLINICAL, "system_admin"]}>
            <Layout />
          </RequireRole>
        }
      >
        <Route path="/inventory" element={<RequireRole roles={[...CLINICAL]}><InventoryPage /></RequireRole>} />
        <Route path="/scheduling" element={<RequireRole roles={[...CLINICAL]}><SchedulingPage /></RequireRole>} />
        <Route path="/children" element={<RequireRole roles={[...CLINICAL]}><ChildrenPage /></RequireRole>} />
        <Route path="/children/:id" element={<RequireRole roles={[...CLINICAL]}><ChildPage /></RequireRole>} />
        <Route path="/admin" element={<RequireRole roles={["system_admin"]}><AdminPage /></RequireRole>} />
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}

export default function App() {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } }),
  );
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter future={ROUTER_FUTURE}>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
