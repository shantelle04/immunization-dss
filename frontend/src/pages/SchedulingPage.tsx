import AddIcon from "@mui/icons-material/Add";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import {
  AGE_BANDS,
  DataList,
  ErrorNote,
  Loading,
  PageHeader,
  SEXES,
  Section,
  StatusChip,
  ageBand,
  ageInFull,
  fmtDate,
  sexLabel,
  titleCase,
  useOnline,
} from "../ui";

interface Defaulter {
  rank: number;
  child_id: string;
  system_id: string;
  name: string;
  sex: string;
  age_days: number;
  overdue_count: number;
  overdue: string[];
  days_to_nearest_max_age: number;
}

export interface SessionRow {
  id: number;
  date: string;
  kind: string;
  location_name: string;
  capacity: number | null;
  status: string;
}

function Profile({ results }: { results: Defaulter[] }) {
  const bySex = SEXES.map((s) => ({ ...s, count: results.filter((d) => d.sex === s.code).length }));
  const byAge = AGE_BANDS.map((b) => ({ ...b, count: results.filter((d) => ageBand(d.age_days).key === b.key) }));
  const share = (n: number) => (results.length ? `${Math.round((100 * n) / results.length)}%` : "-");
  return (
    <Section title="Who is overdue">
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "1fr 2fr" } }}>
        <DataList
          caption="Defaulters by sex"
          rows={bySex}
          rowKey={(r) => r.code}
          columns={[
            { key: "sex", label: "Sex", primary: true, render: (r) => r.label },
            { key: "n", label: "Children", align: "right", render: (r) => r.count },
            { key: "pct", label: "Share", align: "right", render: (r) => share(r.count) },
          ]}
        />
        <DataList
          caption="Defaulters by age group"
          rows={byAge.filter((b) => b.key !== "24+")}
          rowKey={(r) => r.key}
          columns={[
            { key: "age", label: "Age group", primary: true, render: (r) => r.label },
            { key: "n", label: "Children", align: "right", render: (r) => r.count.length },
            { key: "pct", label: "Share", align: "right", render: (r) => share(r.count.length) },
            {
              key: "female",
              label: "Female / male",
              align: "right",
              render: (r) =>
                `${r.count.filter((d) => d.sex === "F").length} / ${r.count.filter((d) => d.sex === "M").length}`,
            },
          ]}
        />
      </Box>
    </Section>
  );
}

function Defaulters() {
  const [filter, setFilter] = useState("");
  const [sex, setSex] = useState("");
  const [band, setBand] = useState("");
  const list = useQuery({
    queryKey: ["defaulters"],
    queryFn: () => api<{ as_of: string; count: number; results: Defaulter[] }>("/defaulters"),
  });
  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorNote error={list.error} />;
  const { as_of, count, results } = list.data;
  const needle = filter.trim().toLowerCase();
  const rows = results.filter(
    (d) =>
      (!needle || d.name.toLowerCase().includes(needle) || d.system_id.toLowerCase().includes(needle)) &&
      (!sex || d.sex === sex) &&
      (!band || ageBand(d.age_days).key === band),
  );
  return (
    <>
    <Profile results={results} />
    <Section title={`Defaulters (${count}) as of ${fmtDate(as_of)}`}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Children under 2 with a dose more than 28 days past its due date. Order: most overdue doses first, then
        the child closest to a vaccine's upper age limit.
      </Typography>
      <Box sx={{ display: "grid", gap: 2, mb: 2, gridTemplateColumns: { xs: "1fr", sm: "2fr 1fr 1fr" }, maxWidth: 760 }}>
        <TextField label="Filter by name or system ID" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <TextField select label="Sex" value={sex} onChange={(e) => setSex(e.target.value)}>
          <MenuItem value="">All</MenuItem>
          {SEXES.map((s) => (
            <MenuItem key={s.code} value={s.code}>
              {s.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField select label="Age group" value={band} onChange={(e) => setBand(e.target.value)}>
          <MenuItem value="">All</MenuItem>
          {AGE_BANDS.filter((b) => b.key !== "24+").map((b) => (
            <MenuItem key={b.key} value={b.key}>
              {b.label}
            </MenuItem>
          ))}
        </TextField>
      </Box>
      {rows.length !== results.length && (
        <Typography variant="body2" sx={{ mb: 1 }}>
          {rows.length} of {count} shown; the rank is still the rank in the full list.
        </Typography>
      )}
      <DataList
        caption="Prioritised defaulter list for outreach planning"
        rows={rows.slice(0, 200)}
        rowKey={(d) => d.child_id}
        maxHeight={640}
        empty="No child matches."
        columns={[
          {
            key: "child",
            label: "Child",
            primary: true,
            render: (d) => (
              <>
                <Link component={RouterLink} to={`/children/${d.child_id}`}>
                  {d.rank}. {d.name}
                </Link>
                <Typography variant="caption" display="block" color="text.secondary">
                  {d.system_id}
                </Typography>
              </>
            ),
          },
          { key: "sex", label: "Sex", render: (d) => sexLabel(d.sex) },
          { key: "age", label: "Age", render: (d) => ageInFull(d.age_days) },
          {
            key: "count",
            label: "Overdue doses",
            align: "right",
            render: (d) => <StatusChip tone={d.overdue_count >= 3 ? "critical" : "warning"} label={String(d.overdue_count)} />,
          },
          { key: "doses", label: "Doses", render: (d) => d.overdue.join(", ") },
          { key: "limit", label: "Days to age limit", align: "right", render: (d) => d.days_to_nearest_max_age },
        ]}
      />
      {rows.length > 200 && (
        <Typography variant="caption" color="text.secondary">
          Showing the first 200 of {rows.length}; use the filters to narrow the list.
        </Typography>
      )}
    </Section>
    </>
  );
}

function Sessions() {
  const { user } = useAuth();
  const online = useOnline();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const manager = user?.role === "facility_manager";
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api<{ results: SessionRow[] }>("/sessions", { query: { limit: "30" } }),
  });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ date: "", kind: "outreach", location_name: "", capacity: "30" });
  const create = useMutation({
    mutationFn: () => api<SessionRow>("/sessions", { method: "POST", body: { ...form, capacity: Number(form.capacity) } }),
    onSuccess: (session) => {
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      navigate(`/scheduling/sessions/${session.id}`);
    },
  });
  return (
    <Section
      title="Sessions"
      action={
        manager ? (
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)} disabled={!online}>
            New session
          </Button>
        ) : undefined
      }
    >
      {sessions.isPending ? (
        <Loading />
      ) : sessions.isError ? (
        <ErrorNote error={sessions.error} />
      ) : (
        <DataList
          caption="The latest 30 sessions of this facility"
          rows={sessions.data.results}
          rowKey={(s) => s.id}
          empty="No session yet."
          columns={[
            {
              key: "where",
              label: "Session",
              primary: true,
              render: (s) => (
                <Link component={RouterLink} to={`/scheduling/sessions/${s.id}`}>
                  {s.location_name}
                </Link>
              ),
            },
            { key: "date", label: "Date", render: (s) => fmtDate(s.date) },
            { key: "kind", label: "Kind", render: (s) => titleCase(s.kind) },
            { key: "status", label: "Status", render: (s) => <StatusChip tone={s.status === "held" ? "good" : "default"} label={titleCase(s.status)} /> },
          ]}
        />
      )}
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="xs">
        <Box
          component="form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <DialogTitle>New session</DialogTitle>
          <DialogContent sx={{ display: "grid", gap: 2, pt: "8px !important" }}>
            <TextField
              label="Date"
              type="date"
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
              slotProps={{ inputLabel: { shrink: true } }}
              required
            />
            <TextField select label="Kind" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <MenuItem value="outreach">Outreach</MenuItem>
              <MenuItem value="fixed">Fixed (at the facility)</MenuItem>
            </TextField>
            <TextField
              label="Location"
              value={form.location_name}
              onChange={(e) => setForm({ ...form, location_name: e.target.value })}
              required
            />
            <TextField
              label="Capacity (children)"
              type="number"
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: e.target.value })}
              slotProps={{ htmlInput: { min: 1, max: 500 } }}
              required
            />
            {create.isError && <ErrorNote error={create.error} />}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={create.isPending}>
              Create
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Section>
  );
}

export default function SchedulingPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "sessions" ? "sessions" : "defaulters";
  return (
    <Stack>
      <PageHeader title="Outreach" subtitle="Defaulter tracking and session planning" />
      <Tabs
        value={tab}
        onChange={(_, v: string) => setParams(v === "defaulters" ? {} : { tab: v }, { replace: true })}
        aria-label="Outreach sections"
        sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}
      >
        <Tab value="defaulters" label="Defaulters" />
        <Tab value="sessions" label="Sessions" />
      </Tabs>
      {tab === "defaulters" ? <Defaulters /> : <Sessions />}
    </Stack>
  );
}
