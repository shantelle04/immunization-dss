import CheckIcon from "@mui/icons-material/Check";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, lazy, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import {
  DataList,
  EmptyState,
  ErrorNote,
  Loading,
  PageHeader,
  Section,
  StatTile,
  StatusChip,
  TileGrid,
  fmtDate,
  titleCase,
  useOnline,
  type Tone,
} from "../ui";
import type { ForecastSeries } from "./ForecastChart";

// The chart library is the largest dependency; it loads only when a forecast is opened.
const ForecastChart = lazy(() => import("./ForecastChart"));

interface BalanceRow {
  antigen: string;
  antigen_name: string;
  balance_doses: number;
  weekly_use_doses: number;
  weeks_left: number | null;
}

interface Transaction {
  id: number;
  occurred_on: string;
  antigen: string;
  kind: string;
  quantity_doses: number;
  lot_number: string | null;
}

interface StockAlert {
  id: number;
  antigen: string;
  antigen_name: string;
  raised_on: string;
  projected_breach_week: string;
  projected_doses: string;
  safety_minimum: string;
  status: "open" | "acknowledged" | "resolved";
  acknowledged_by: string | null;
}

interface Policy {
  antigen: string;
  antigen_name: string;
  cycle_weeks: number;
  safety_buffer: string;
}

interface ForecastData {
  run: { run_at: string; source: string; as_of: string; data_sha256: string } | null;
  antigens: ForecastSeries[];
}

const KINDS = ["receipt", "issue", "wastage", "loss", "adjustment"];
const MODEL_LABEL: Record<string, string> = {
  seasonal_naive: "Seasonal naive (same week last year)",
  moving_average: "Moving average (last 4 weeks)",
  sarima: "SARIMA",
  gru: "GRU neural network",
  population: "Population estimate",
};

function stockStatus(row: BalanceRow): { tone: Tone; label: string } {
  if (row.balance_doses <= 0) return { tone: "critical", label: "Out of stock" };
  if (row.weeks_left === null) return { tone: "default", label: "No recent use" };
  if (row.weeks_left < 2) return { tone: "critical", label: "Low: under 2 weeks" };
  if (row.weeks_left < 4) return { tone: "warning", label: "Under 4 weeks" };
  return { tone: "good", label: "OK" };
}

export function AlertList({ compact = false }: { compact?: boolean }) {
  const { user } = useAuth();
  const online = useOnline();
  const queryClient = useQueryClient();
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: () => api<{ results: StockAlert[] }>("/alerts") });
  const acknowledge = useMutation({
    mutationFn: (id: number) => api(`/alerts/${id}/acknowledge`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  if (alerts.isPending) return <Loading />;
  if (alerts.isError) return <ErrorNote error={alerts.error} />;
  const rows = alerts.data.results;
  if (rows.length === 0)
    return <Typography color="text.secondary">No vaccine is projected to fall below its safety minimum.</Typography>;
  const shown = compact ? rows.slice(0, 4) : rows;
  return (
    <Stack spacing={1}>
      {shown.map((a) => {
        const out = Number(a.projected_doses) <= 0;
        return (
          <Alert
            key={a.id}
            severity={out ? "error" : "warning"}
            action={
              a.status === "open" && user?.role === "facility_manager" ? (
                <Button
                  color="inherit"
                  size="small"
                  startIcon={<CheckIcon />}
                  disabled={!online || acknowledge.isPending}
                  onClick={() => acknowledge.mutate(a.id)}
                  aria-label={`Acknowledge ${a.antigen_name} alert`}
                >
                  Acknowledge
                </Button>
              ) : undefined
            }
          >
            <strong>{a.antigen_name}</strong>:{" "}
            {out ? "projected to run out" : "projected below the safety minimum"} in the week of{" "}
            {fmtDate(a.projected_breach_week)} ({Math.round(Number(a.projected_doses))} doses projected, minimum{" "}
            {Math.round(Number(a.safety_minimum))}).
            {a.status === "acknowledged" && <> Acknowledged by {a.acknowledged_by}.</>}
          </Alert>
        );
      })}
      {compact && rows.length > shown.length && (
        <Typography variant="body2" color="text.secondary">
          And {rows.length - shown.length} more under Stock.
        </Typography>
      )}
      {acknowledge.isError && <ErrorNote error={acknowledge.error} />}
    </Stack>
  );
}

function StockTab({ rows, asOf }: { rows: BalanceRow[]; asOf: string }) {
  return (
    <>
      <Section title="Stock-out alerts">
        <AlertList />
      </Section>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Current stock as of {fmtDate(asOf)}, from the stock ledger. Weeks left use the last 12 weeks of doses
        issued and wasted.
      </Typography>
      <Box
        component="ul"
        aria-label="Current stock per vaccine"
        sx={{
          listStyle: "none",
          p: 0,
          m: 0,
          mb: 3,
          display: "grid",
          gap: { xs: 1.5, sm: 2 },
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" },
        }}
      >
        {rows.map((r) => {
          const status = stockStatus(r);
          const meter = r.weeks_left === null ? 0 : Math.min(100, (r.weeks_left / 8) * 100);
          return (
            <Card component="li" variant="outlined" key={r.antigen} sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{r.antigen_name}</Typography>
                <StatusChip tone={status.tone} label={status.label} />
              </Box>
              <Typography sx={{ fontSize: 28, fontWeight: 700, lineHeight: 1.1 }}>
                {r.balance_doses}
                <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 0.75 }}>
                  doses in stock
                </Typography>
              </Typography>
              <LinearProgress
                variant="determinate"
                value={meter}
                color={status.tone === "critical" ? "error" : status.tone === "warning" ? "warning" : "primary"}
                sx={{ my: 1.25, height: 6, borderRadius: 3 }}
                aria-label={`${r.antigen_name} weeks of stock left`}
              />
              <Typography variant="body2" color="text.secondary">
                {r.weekly_use_doses} doses used per week;{" "}
                {r.weeks_left === null ? "no recent use" : `${r.weeks_left} weeks left`}
              </Typography>
            </Card>
          );
        })}
      </Box>
    </>
  );
}

function ForecastTab() {
  const forecasts = useQuery({ queryKey: ["forecasts"], queryFn: () => api<ForecastData>("/forecasts") });
  const [antigen, setAntigen] = useState("");
  const [view, setView] = useState<"chart" | "table">("chart");
  if (forecasts.isPending) return <Loading />;
  if (forecasts.isError) return <ErrorNote error={forecasts.error} />;
  const { run, antigens } = forecasts.data;
  if (!run || antigens.length === 0)
    return (
      <Section>
        <EmptyState>No forecast has been run yet. Forecasts are produced by the scheduled forecast job.</EmptyState>
      </Section>
    );
  const series = antigens.find((a) => a.antigen === antigen) ?? antigens[0];
  const acc = series.accuracy;
  return (
    <>
      <Box sx={{ display: "flex", gap: 1, overflowX: "auto", pb: 1, mb: 1 }} role="group" aria-label="Vaccine">
        {antigens.map((a) => (
          <Chip
            key={a.antigen}
            label={a.antigen_name}
            color={a.antigen === series.antigen ? "primary" : "default"}
            variant={a.antigen === series.antigen ? "filled" : "outlined"}
            onClick={() => setAntigen(a.antigen)}
            aria-pressed={a.antigen === series.antigen}
          />
        ))}
      </Box>
      <Section
        title={`${series.antigen_name}: weekly doses, next 4 weeks`}
        action={
          <ToggleButtonGroup
            size="small"
            exclusive
            value={view}
            onChange={(_, v: "chart" | "table" | null) => v && setView(v)}
            aria-label="Show as"
          >
            <ToggleButton value="chart">Chart</ToggleButton>
            <ToggleButton value="table">Table</ToggleButton>
          </ToggleButtonGroup>
        }
      >
        {view === "chart" ? (
          <Suspense fallback={<Loading />}>
            <ForecastChart series={series} />
          </Suspense>
        ) : (
          <DataList
            caption={`Forecast of weekly ${series.antigen_name} doses with the 80% interval`}
            rows={series.forecast}
            rowKey={(f) => f.week_start}
            columns={[
              { key: "week", label: "Week of", primary: true, render: (f) => fmtDate(f.week_start) },
              { key: "yhat", label: "Forecast doses", align: "right", render: (f) => f.yhat },
              { key: "lo", label: "Low (80%)", align: "right", render: (f) => f.lo80 },
              { key: "hi", label: "High (80%)", align: "right", render: (f) => f.hi80 },
            ]}
          />
        )}
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
          Model: {MODEL_LABEL[series.model] ?? series.model}. Run for {fmtDate(run.as_of)}
          {run.source === "baselines" ? "; baseline methods only, trained models not yet imported" : ""}.
        </Typography>
      </Section>
      {acc && (
        <>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Accuracy of this model in the latest backtest (last 24 weeks)
          </Typography>
          <TileGrid>
            <StatTile
              label="MASE"
              value={acc.mase === null ? "-" : acc.mase.toFixed(2)}
              hint="Under 1 beats seasonal naive"
              tone={acc.mase !== null && acc.mase < 1 ? "good" : "default"}
            />
            <StatTile label="Mean absolute error" value={acc.mae.toFixed(1)} hint="Doses per week" />
            <StatTile label="sMAPE" value={`${Math.round(acc.smape * 100)}%`} hint="Symmetric percentage error" />
            <StatTile label="Interval coverage" value={`${Math.round(acc.coverage80 * 100)}%`} hint="Target 80%" />
          </TileGrid>
        </>
      )}
    </>
  );
}

function LedgerTab({ rows }: { rows: BalanceRow[] }) {
  const queryClient = useQueryClient();
  const online = useOnline();
  const ledger = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api<{ results: Transaction[] }>("/stock/transactions", { query: { limit: "25" } }),
  });
  const [form, setForm] = useState({ antigen: "", kind: "receipt", quantity_doses: "", occurred_on: "", lot_number: "" });
  const record = useMutation({
    mutationFn: () =>
      api("/stock/transactions", { method: "POST", body: { ...form, quantity_doses: Number(form.quantity_doses) } }),
    onSuccess: () => {
      setForm({ ...form, quantity_doses: "", lot_number: "" });
      for (const key of ["balance", "transactions", "dashboard"]) void queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    record.mutate();
  }
  return (
    <>
      <Section title="Record a stock transaction">
        <Box
          component="form"
          onSubmit={submit}
          sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" } }}
        >
          <TextField select label="Vaccine" value={form.antigen} onChange={(e) => setForm({ ...form, antigen: e.target.value })} required>
            {rows.map((r) => (
              <MenuItem key={r.antigen} value={r.antigen}>
                {r.antigen_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Kind" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            {KINDS.map((k) => (
              <MenuItem key={k} value={k}>
                {titleCase(k)}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Doses"
            type="number"
            value={form.quantity_doses}
            onChange={(e) => setForm({ ...form, quantity_doses: e.target.value })}
            slotProps={{ htmlInput: { min: 1, inputMode: "numeric" } }}
            required
          />
          <TextField
            label="Date"
            type="date"
            value={form.occurred_on}
            onChange={(e) => setForm({ ...form, occurred_on: e.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
            required
          />
          <TextField
            label="Lot number (optional)"
            value={form.lot_number}
            onChange={(e) => setForm({ ...form, lot_number: e.target.value })}
          />
          <Button type="submit" variant="contained" disabled={!online || record.isPending}>
            Save transaction
          </Button>
        </Box>
        {record.isError && <ErrorNote error={record.error} />}
        {record.isSuccess && (
          <Alert severity="success" sx={{ mt: 1.5 }}>
            Saved.
          </Alert>
        )}
      </Section>
      <Section title="Recent transactions">
        {ledger.isPending ? (
          <Loading />
        ) : ledger.isError ? (
          <ErrorNote error={ledger.error} />
        ) : (
          <DataList
            caption="The latest 25 entries in this facility's stock ledger"
            rows={ledger.data.results}
            rowKey={(t) => t.id}
            columns={[
              { key: "what", label: "Vaccine", primary: true, render: (t) => `${t.antigen}, ${titleCase(t.kind).toLowerCase()}` },
              { key: "date", label: "Date", render: (t) => fmtDate(t.occurred_on) },
              { key: "qty", label: "Doses", align: "right", render: (t) => (t.quantity_doses > 0 ? `+${t.quantity_doses}` : t.quantity_doses) },
              { key: "lot", label: "Lot", render: (t) => t.lot_number ?? "-" },
            ]}
          />
        )}
      </Section>
    </>
  );
}

function PolicyTab() {
  const { user } = useAuth();
  const online = useOnline();
  const queryClient = useQueryClient();
  const manager = user?.role === "facility_manager";
  const policies = useQuery({ queryKey: ["policies"], queryFn: () => api<Policy[]>("/stock/policies") });
  const [editing, setEditing] = useState<Policy | null>(null);
  const save = useMutation({
    mutationFn: (p: Policy) =>
      api(`/stock/policies/${p.antigen}`, {
        method: "PUT",
        body: { cycle_weeks: Number(p.cycle_weeks), safety_buffer: p.safety_buffer },
      }),
    onSuccess: () => {
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });
  if (policies.isPending) return <Loading />;
  if (policies.isError) return <ErrorNote error={policies.error} />;
  return (
    <Section title="Replenishment and safety buffer">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        An alert is raised when projected stock falls below the safety minimum before the next delivery: average
        weekly use, times the weeks still to cover, times one plus the buffer.
        {manager ? "" : " Only the facility manager can change these settings."}
      </Typography>
      <DataList
        caption="Stock policy per vaccine"
        rows={policies.data}
        rowKey={(p) => p.antigen}
        columns={[
          { key: "name", label: "Vaccine", primary: true, render: (p) => p.antigen_name },
          { key: "cycle", label: "Delivery every", align: "right", render: (p) => `${p.cycle_weeks} weeks` },
          { key: "buffer", label: "Safety buffer", align: "right", render: (p) => `${Math.round(Number(p.safety_buffer) * 100)}%` },
          ...(manager
            ? [
                {
                  key: "edit",
                  label: "",
                  render: (p: Policy) => (
                    <Button size="small" onClick={() => setEditing({ ...p })} aria-label={`Edit ${p.antigen_name} policy`}>
                      Edit
                    </Button>
                  ),
                },
              ]
            : []),
        ]}
      />
      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="xs">
        {editing && (
          <Box
            component="form"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              save.mutate(editing);
            }}
          >
            <DialogTitle>{editing.antigen_name}</DialogTitle>
            <DialogContent sx={{ display: "grid", gap: 2, pt: "8px !important" }}>
              <TextField
                label="Weeks between deliveries"
                type="number"
                value={editing.cycle_weeks}
                onChange={(e) => setEditing({ ...editing, cycle_weeks: Number(e.target.value) })}
                slotProps={{ htmlInput: { min: 1, max: 12 } }}
                required
              />
              <TextField
                label="Safety buffer (0.25 means 25%)"
                type="number"
                value={editing.safety_buffer}
                onChange={(e) => setEditing({ ...editing, safety_buffer: e.target.value })}
                slotProps={{ htmlInput: { min: 0, max: 2, step: 0.05 } }}
                required
              />
              {save.isError && <ErrorNote error={save.error} />}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setEditing(null)}>Cancel</Button>
              <Button type="submit" variant="contained" disabled={!online || save.isPending}>
                Save
              </Button>
            </DialogActions>
          </Box>
        )}
      </Dialog>
    </Section>
  );
}

const TABS = [
  { value: "stock", label: "Stock" },
  { value: "forecast", label: "Forecast" },
  { value: "ledger", label: "Ledger" },
  { value: "settings", label: "Settings" },
];

export default function InventoryPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.value === params.get("tab")) ? (params.get("tab") as string) : "stock";
  const balance = useQuery({
    queryKey: ["balance"],
    queryFn: () => api<{ as_of: string; rows: BalanceRow[] }>("/stock/balance"),
  });
  if (balance.isPending) return <Loading />;
  if (balance.isError) return <ErrorNote error={balance.error} />;
  return (
    <>
      <PageHeader title="Stock" subtitle="Vaccine stock, demand forecast and stock-out alerts" />
      <Tabs
        value={tab}
        onChange={(_, v: string) => setParams(v === "stock" ? {} : { tab: v }, { replace: true })}
        variant="scrollable"
        allowScrollButtonsMobile
        aria-label="Stock sections"
        sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}
      >
        {TABS.map((t) => (
          <Tab key={t.value} value={t.value} label={t.label} />
        ))}
      </Tabs>
      {tab === "stock" && <StockTab rows={balance.data.rows} asOf={balance.data.as_of} />}
      {tab === "forecast" && <ForecastTab />}
      {tab === "ledger" && <LedgerTab rows={balance.data.rows} />}
      {tab === "settings" && <PolicyTab />}
    </>
  );
}
