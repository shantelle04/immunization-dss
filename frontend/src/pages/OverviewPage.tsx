import AddIcon from "@mui/icons-material/Add";
import EventIcon from "@mui/icons-material/EventOutlined";
import GroupsIcon from "@mui/icons-material/GroupsOutlined";
import InventoryIcon from "@mui/icons-material/Inventory2Outlined";
import NotificationsIcon from "@mui/icons-material/NotificationsActiveOutlined";
import SearchIcon from "@mui/icons-material/Search";
import { Box, Button, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { ErrorNote, Loading, PageHeader, Section, StatTile, TileGrid, fmtDate } from "../ui";
import { AlertList } from "./InventoryPage";

interface Overview {
  as_of: string;
  children_under_two: number;
  defaulters: number;
  children_with_due_dose: number;
  doses_due_in_7_days: number;
  alerts_open: number;
  alerts_acknowledged: number;
  antigens_low_stock: number;
  antigens_out_of_stock: number;
  next_session: { id: number; date: string; kind: string; location_name: string } | null;
}

export default function OverviewPage() {
  const { user } = useAuth();
  const overview = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Overview>("/dashboard") });
  if (overview.isPending) return <Loading />;
  if (overview.isError) return <ErrorNote error={overview.error} />;
  const d = overview.data;
  return (
    <>
      <PageHeader title="Overview" subtitle={`${user?.facility?.name ?? ""}, as of ${fmtDate(d.as_of)}`} />
      <TileGrid>
        <StatTile
          label="Stock-out alerts"
          value={d.alerts_open}
          hint={`${d.alerts_acknowledged} acknowledged`}
          tone={d.alerts_open > 0 ? "critical" : "good"}
          icon={<NotificationsIcon />}
          to="/inventory"
        />
        <StatTile
          label="Vaccines low or out"
          value={d.antigens_low_stock}
          hint={`${d.antigens_out_of_stock} out of stock`}
          tone={d.antigens_out_of_stock > 0 ? "critical" : d.antigens_low_stock > 0 ? "warning" : "good"}
          icon={<InventoryIcon />}
          to="/inventory"
        />
        <StatTile
          label="Defaulters"
          value={d.defaulters}
          hint={`of ${d.children_under_two} children under 2`}
          tone={d.defaulters > 0 ? "warning" : "good"}
          icon={<GroupsIcon />}
          to="/scheduling"
        />
        <StatTile
          label="Doses due in 7 days"
          value={d.doses_due_in_7_days}
          hint={`${d.children_with_due_dose} children due now`}
          icon={<EventIcon />}
          to="/scheduling"
        />
      </TileGrid>

      <Section title="Quick actions">
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <Button component={RouterLink} to="/children?tab=register" variant="contained" startIcon={<AddIcon />}>
            Register a child
          </Button>
          <Button component={RouterLink} to="/children" variant="outlined" startIcon={<SearchIcon />}>
            Find a child
          </Button>
          <Button component={RouterLink} to="/inventory?tab=ledger" variant="outlined" startIcon={<InventoryIcon />}>
            Record stock
          </Button>
        </Stack>
      </Section>

      <Section title="Stock-out alerts">
        <AlertList compact />
      </Section>

      <Section title="Next session">
        {d.next_session ? (
          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1.5 }}>
            <Box sx={{ flexGrow: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>{d.next_session.location_name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {fmtDate(d.next_session.date)}, {d.next_session.kind} session
              </Typography>
            </Box>
            <Button component={RouterLink} to={`/scheduling/sessions/${d.next_session.id}`} variant="outlined">
              Open plan
            </Button>
          </Box>
        ) : (
          <Typography color="text.secondary">No session is planned. Sessions are created under Outreach.</Typography>
        )}
      </Section>
    </>
  );
}
