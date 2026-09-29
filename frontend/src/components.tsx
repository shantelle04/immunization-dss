import {
  Alert,
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  Paper,
  Tab,
  Tabs,
  Toolbar,
  Typography,
} from "@mui/material";
import type { ReactNode } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./auth";

const CLINICAL_TABS = [
  { to: "/inventory", label: "Inventory" },
  { to: "/scheduling", label: "Scheduling" },
  { to: "/children", label: "Children" },
];

export function Layout() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();
  const tabs = user?.role === "system_admin" ? [{ to: "/admin", label: "Administration" }] : CLINICAL_TABS;
  const current = tabs.find((t) => pathname.startsWith(t.to))?.to ?? false;
  return (
    <>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar sx={{ flexWrap: "wrap", gap: 1 }}>
          <Typography variant="h6" component="p" sx={{ flexGrow: 1, fontSize: { xs: 16, sm: 20 } }}>
            {user?.facility ? user.facility.name : "Immunization DSS"}
          </Typography>
          <Typography variant="body2" sx={{ mr: 1 }}>
            {user?.username} ({user?.role.replace(/_/g, " ")})
          </Typography>
          <Button variant="outlined" size="small" onClick={() => void signOut()}>
            Sign out
          </Button>
        </Toolbar>
        <Tabs value={current} variant="scrollable" allowScrollButtonsMobile aria-label="Sections">
          {tabs.map((t) => (
            <Tab key={t.to} value={t.to} label={t.label} component={RouterLink} to={t.to} />
          ))}
        </Tabs>
      </AppBar>
      <Container component="main" maxWidth="lg" sx={{ py: 3 }}>
        <Alert severity="info" sx={{ mb: 2 }}>
          All records shown are synthetic.
        </Alert>
        <Outlet />
      </Container>
    </>
  );
}

export function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 1, mb: 1 }}>
        <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
          {title}
        </Typography>
        {action}
      </Box>
      {children}
    </Paper>
  );
}

export function Loading() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
      <CircularProgress aria-label="Loading" />
    </Box>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return <Alert severity="error">{error instanceof Error ? error.message : "Something went wrong."}</Alert>;
}
