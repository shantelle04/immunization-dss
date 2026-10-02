import AssignmentIcon from "@mui/icons-material/AssignmentOutlined";
import ChildCareIcon from "@mui/icons-material/ChildCareOutlined";
import DarkModeIcon from "@mui/icons-material/DarkModeOutlined";
import DashboardIcon from "@mui/icons-material/DashboardOutlined";
import EventIcon from "@mui/icons-material/EventOutlined";
import HistoryIcon from "@mui/icons-material/HistoryOutlined";
import InventoryIcon from "@mui/icons-material/Inventory2Outlined";
import LightModeIcon from "@mui/icons-material/LightModeOutlined";
import LocalHospitalIcon from "@mui/icons-material/LocalHospitalOutlined";
import LogoutIcon from "@mui/icons-material/LogoutOutlined";
import MenuIcon from "@mui/icons-material/MoreHorizOutlined";
import PeopleIcon from "@mui/icons-material/PeopleAltOutlined";
import UploadIcon from "@mui/icons-material/UploadFileOutlined";
import VaccinesIcon from "@mui/icons-material/VaccinesOutlined";
import WifiOffIcon from "@mui/icons-material/WifiOffOutlined";
import {
  Alert,
  AppBar,
  Avatar,
  BottomNavigation,
  BottomNavigationAction,
  Box,
  Chip,
  Container,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Paper,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { useColorScheme } from "@mui/material/styles";
import type { ReactNode } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import type { Role } from "./api";
import { useAuth } from "./auth";
import { titleCase, useOnline } from "./ui";

export const DRAWER_WIDTH = 248;

export interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  roles: Role[];
  group: "main" | "facility";
}

const CLINICAL: Role[] = ["healthcare_worker", "facility_manager"];

export const NAV: NavItem[] = [
  { to: "/overview", label: "Overview", icon: <DashboardIcon />, roles: CLINICAL, group: "main" },
  { to: "/inventory", label: "Stock", icon: <InventoryIcon />, roles: CLINICAL, group: "main" },
  { to: "/scheduling", label: "Outreach", icon: <EventIcon />, roles: CLINICAL, group: "main" },
  { to: "/children", label: "Children", icon: <ChildCareIcon />, roles: CLINICAL, group: "main" },
  { to: "/schedule", label: "Vaccine schedule", icon: <VaccinesIcon />, roles: CLINICAL, group: "facility" },
  { to: "/imports", label: "Import data", icon: <UploadIcon />, roles: ["facility_manager"], group: "facility" },
  { to: "/audit", label: "Audit log", icon: <HistoryIcon />, roles: ["facility_manager"], group: "facility" },
  { to: "/admin", label: "System", icon: <DashboardIcon />, roles: ["system_admin"], group: "main" },
  { to: "/admin/users", label: "Users", icon: <PeopleIcon />, roles: ["system_admin"], group: "main" },
  { to: "/admin/facilities", label: "Facilities", icon: <LocalHospitalIcon />, roles: ["system_admin"], group: "main" },
  { to: "/admin/schedule", label: "Schedule", icon: <AssignmentIcon />, roles: ["system_admin"], group: "main" },
];

function isCurrent(pathname: string, item: NavItem, items: NavItem[]): boolean {
  if (pathname !== item.to && !pathname.startsWith(`${item.to}/`)) return false;
  // "/admin" must not light up while "/admin/users" is open.
  return !items.some((o) => o !== item && o.to.length > item.to.length && pathname.startsWith(o.to));
}

export function ThemeToggle() {
  const { mode, systemMode, setMode } = useColorScheme();
  const dark = (mode === "system" ? systemMode : mode) === "dark";
  return (
    <Tooltip title={dark ? "Use light theme" : "Use dark theme"}>
      <IconButton onClick={() => setMode(dark ? "light" : "dark")} aria-label={dark ? "Use light theme" : "Use dark theme"}>
        {dark ? <LightModeIcon /> : <DarkModeIcon />}
      </IconButton>
    </Tooltip>
  );
}

function NavList({ items, pathname }: { items: NavItem[]; pathname: string }) {
  const facility = items.filter((i) => i.group === "facility");
  const render = (item: NavItem) => {
    const current = isCurrent(pathname, item, items);
    return (
      <ListItemButton
        key={item.to}
        component={RouterLink}
        to={item.to}
        selected={current}
        aria-current={current ? "page" : undefined}
        sx={{ borderRadius: 2, mx: 1, mb: 0.5 }}
      >
        <ListItemIcon sx={{ minWidth: 40, color: current ? "primary.main" : "text.secondary" }}>{item.icon}</ListItemIcon>
        <ListItemText primary={item.label} primaryTypographyProps={{ fontWeight: current ? 600 : 500, fontSize: 15 }} />
      </ListItemButton>
    );
  };
  return (
    <List component="nav" aria-label="Sections" sx={{ py: 1 }}>
      {items.filter((i) => i.group === "main").map(render)}
      {facility.length > 0 && (
        <>
          <ListSubheader disableSticky sx={{ bgcolor: "transparent", lineHeight: "32px", mt: 1 }}>
            Facility
          </ListSubheader>
          {facility.map(render)}
        </>
      )}
    </List>
  );
}

export function Layout() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();
  const online = useOnline();
  if (!user) return null;
  const items = NAV.filter((i) => i.roles.includes(user.role));
  const main = items.filter((i) => i.group === "main");
  const hasMore = items.some((i) => i.group === "facility");
  const bottom = hasMore
    ? [...main, { to: "/more", label: "More", icon: <MenuIcon />, roles: user.role ? [user.role] : [], group: "main" as const }]
    : main;
  const moreOpen = pathname === "/more" || items.some((i) => i.group === "facility" && isCurrent(pathname, i, items));
  const bottomValue = moreOpen ? "/more" : (bottom.find((i) => isCurrent(pathname, i, items))?.to ?? false);
  const place = user.facility ? user.facility.name : "System administration";

  return (
    <Box sx={{ display: "flex", minHeight: "100dvh", bgcolor: "background.default" }}>
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: "none", md: "block" },
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", borderRight: 1, borderColor: "divider" },
        }}
      >
        <Box sx={{ p: 2, display: "flex", alignItems: "center", gap: 1.5 }}>
          <Avatar variant="rounded" sx={{ bgcolor: "primary.main", width: 36, height: 36 }}>
            <VaccinesIcon fontSize="small" />
          </Avatar>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 700, lineHeight: 1.2 }}>Immunization DSS</Typography>
            <Typography variant="caption" color="text.secondary" noWrap component="p">
              {place}
            </Typography>
          </Box>
        </Box>
        <Divider />
        <Box sx={{ flexGrow: 1, overflowY: "auto" }}>
          <NavList items={items} pathname={pathname} />
        </Box>
        <Divider />
        <Box sx={{ p: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
          <Avatar sx={{ width: 32, height: 32, fontSize: 14 }}>{user.username.slice(0, 2).toUpperCase()}</Avatar>
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
              {user.username}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap component="p">
              {titleCase(user.role)}
            </Typography>
          </Box>
          <ThemeToggle />
          <Tooltip title="Sign out">
            <IconButton onClick={() => void signOut()} aria-label="Sign out">
              <LogoutIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Drawer>

      <Box sx={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <AppBar
          position="sticky"
          color="inherit"
          sx={{ display: { md: "none" }, borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}
        >
          <Toolbar sx={{ gap: 1, minHeight: 56 }}>
            <Avatar variant="rounded" sx={{ bgcolor: "primary.main", width: 32, height: 32 }}>
              <VaccinesIcon fontSize="small" />
            </Avatar>
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography noWrap sx={{ fontWeight: 700, fontSize: 15, lineHeight: 1.2 }}>
                {place}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap component="p">
                {user.username}, {titleCase(user.role).toLowerCase()}
              </Typography>
            </Box>
            <ThemeToggle />
            <IconButton onClick={() => void signOut()} aria-label="Sign out" edge="end">
              <LogoutIcon />
            </IconButton>
          </Toolbar>
        </AppBar>

        {!online && (
          <Alert severity="warning" icon={<WifiOffIcon />} square role="status">
            You are offline. The last loaded data stays on screen, read-only, until the connection returns.
          </Alert>
        )}

        <Container component="main" maxWidth="lg" sx={{ py: { xs: 2, sm: 3 }, pb: { xs: 11, md: 4 }, flexGrow: 1 }}>
          <Outlet />
          <Box sx={{ mt: 2, textAlign: "center" }}>
            <Chip size="small" variant="outlined" label="All records shown are synthetic." />
          </Box>
        </Container>

        <Paper
          elevation={0}
          sx={{
            display: { md: "none" },
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: (t) => t.zIndex.appBar,
            borderTop: 1,
            borderColor: "divider",
            pb: "env(safe-area-inset-bottom)",
          }}
        >
          <BottomNavigation value={bottomValue} showLabels component="nav" aria-label="Sections" sx={{ height: 60 }}>
            {bottom.map((item) => (
              <BottomNavigationAction
                key={item.to}
                value={item.to}
                label={item.label}
                icon={item.icon}
                component={RouterLink}
                to={item.to}
                sx={{ minWidth: 0, px: 0.5 }}
              />
            ))}
          </BottomNavigation>
        </Paper>
      </Box>
    </Box>
  );
}
