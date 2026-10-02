import AddIcon from "@mui/icons-material/Add";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { DataList, ErrorNote, Loading, PageHeader, Section, StatTile, StatusChip, TileGrid, fmtDate, titleCase } from "../ui";

interface AdminUser {
  id: number;
  username: string;
  role: string;
  facility: string | null;
  is_active: boolean;
}

interface Facility {
  id: number;
  code: string;
  name: string;
  keph_level: string;
  ownership: string;
  county: string;
  sub_county: string;
}

interface Overview {
  users_by_role: Record<string, number>;
  users_inactive: number;
  users_locked: number;
  facilities: number;
  logins_7_days: number;
  failed_logins_7_days: number;
  lockouts_7_days: number;
  forecast_run: { run_at: string; source: string; as_of: string; series: number; models: Record<string, number> } | null;
}

interface Dose {
  dose_code: string;
  antigen: string;
  dose_number: number;
  recommended_age_days: number;
  min_age_days: number;
  max_age_days: number;
  min_interval_days: number;
}

const ROLES = ["healthcare_worker", "facility_manager", "system_admin"];
const LEVELS = ["dispensary", "health_centre", "sub_county_hospital"];
const GRID = { display: "grid", gap: 2, pt: "8px !important" };

export function AdminOverviewPage() {
  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: () => api<Overview>("/admin/overview") });
  if (overview.isPending) return <Loading />;
  if (overview.isError) return <ErrorNote error={overview.error} />;
  const d = overview.data;
  const users = Object.values(d.users_by_role).reduce((a, b) => a + b, 0);
  const run = d.forecast_run;
  return (
    <>
      <PageHeader title="System" subtitle="Accounts, facilities and the forecast job. Administrators do not see clinical records." />
      <TileGrid>
        <StatTile label="Users" value={users} hint={`${d.users_inactive} inactive`} to="/admin/users" />
        <StatTile label="Facilities" value={d.facilities} to="/admin/facilities" />
        <StatTile
          label="Locked accounts"
          value={d.users_locked}
          hint={`${d.lockouts_7_days} lockouts in 7 days`}
          tone={d.users_locked > 0 ? "warning" : "good"}
          to="/admin/users"
        />
        <StatTile label="Failed sign-ins" value={d.failed_logins_7_days} hint={`${d.logins_7_days} sign-ins in 7 days`} />
      </TileGrid>
      <Section title="Users by role">
        <DataList
          caption="Number of accounts per role"
          rows={ROLES.map((r) => ({ role: r, n: d.users_by_role[r] ?? 0 }))}
          rowKey={(r) => r.role}
          columns={[
            { key: "role", label: "Role", primary: true, render: (r) => titleCase(r.role) },
            { key: "n", label: "Accounts", align: "right", render: (r) => r.n },
          ]}
        />
      </Section>
      <Section title="Forecast job">
        {run ? (
          <Typography>
            Last run {new Date(run.run_at).toLocaleString("en-GB")} for {fmtDate(run.as_of)}: {run.series} series,{" "}
            {Object.entries(run.models)
              .map(([m, n]) => `${n} ${titleCase(m).toLowerCase()}`)
              .join(", ")}
            {run.source === "baselines" ? " (baseline methods; trained models not yet imported)" : " (imported trained models)"}.
          </Typography>
        ) : (
          <Typography color="text.secondary">The forecast job has not run yet.</Typography>
        )}
      </Section>
    </>
  );
}

export function AdminUsersPage() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => api<{ results: AdminUser[] }>("/admin/users", { query: { limit: "200" } }),
  });
  const facilities = useQuery({
    queryKey: ["facilities"],
    queryFn: () => api<{ results: Facility[] }>("/admin/facilities", { query: { limit: "200" } }),
  });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ username: "", role: "healthcare_worker", facility: "", password: "" });
  const [reset, setReset] = useState<AdminUser | null>(null);
  const [password, setPassword] = useState("");
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["users"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
  };
  const create = useMutation({
    mutationFn: () =>
      api("/admin/users", { method: "POST", body: { ...form, facility: form.role === "system_admin" ? null : form.facility } }),
    onSuccess: () => {
      setForm({ ...form, username: "", password: "" });
      setOpen(false);
      refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api(`/admin/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      setReset(null);
      setPassword("");
      refresh();
    },
  });

  if (users.isPending || facilities.isPending) return <Loading />;
  if (users.isError) return <ErrorNote error={users.error} />;
  if (facilities.isError) return <ErrorNote error={facilities.error} />;

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Accounts are created here; there is no self-registration"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
            Create a user
          </Button>
        }
      />
      {create.isSuccess && (
        <Alert severity="success" sx={{ mb: 2 }}>
          User created.
        </Alert>
      )}
      {update.isError && <ErrorNote error={update.error} />}
      <Section title={`Users (${users.data.results.length})`}>
        <DataList
          caption="All accounts. Administrators have no facility and no access to clinical records."
          rows={users.data.results}
          rowKey={(u) => u.id}
          maxHeight={640}
          columns={[
            { key: "name", label: "Username", primary: true, render: (u) => u.username },
            { key: "role", label: "Role", render: (u) => titleCase(u.role) },
            { key: "facility", label: "Facility", render: (u) => u.facility ?? "-" },
            { key: "active", label: "Status", render: (u) => <StatusChip tone={u.is_active ? "good" : "default"} label={u.is_active ? "Active" : "Inactive"} /> },
            {
              key: "actions",
              label: "",
              render: (u) => (
                <Box sx={{ display: "flex", gap: 0.5, justifyContent: "flex-end" }}>
                  <Button size="small" onClick={() => setReset(u)} aria-label={`Set a new password for ${u.username}`}>
                    New password
                  </Button>
                  <Button
                    size="small"
                    color={u.is_active ? "error" : "primary"}
                    disabled={u.username === me?.username || update.isPending}
                    onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}
                    aria-label={`${u.is_active ? "Deactivate" : "Activate"} ${u.username}`}
                  >
                    {u.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </Box>
              ),
            },
          ]}
        />
      </Section>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="xs">
        <Box
          component="form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <DialogTitle>Create a user</DialogTitle>
          <DialogContent sx={GRID}>
            <TextField label="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            <TextField select label="Role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {ROLES.map((r) => (
                <MenuItem key={r} value={r}>
                  {titleCase(r)}
                </MenuItem>
              ))}
            </TextField>
            {form.role !== "system_admin" && (
              <TextField select label="Facility" value={form.facility} onChange={(e) => setForm({ ...form, facility: e.target.value })} required>
                {facilities.data.results.map((f) => (
                  <MenuItem key={f.code} value={f.code}>
                    {f.name}
                  </MenuItem>
                ))}
              </TextField>
            )}
            <TextField
              label="Initial password (12+ characters)"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              autoComplete="new-password"
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

      <Dialog open={reset !== null} onClose={() => setReset(null)} fullWidth maxWidth="xs">
        {reset && (
          <Box
            component="form"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              update.mutate({ id: reset.id, body: { password } });
            }}
          >
            <DialogTitle>New password for {reset.username}</DialogTitle>
            <DialogContent sx={GRID}>
              <TextField
                label="New password (12+ characters)"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              <Typography variant="body2" color="text.secondary">
                This also clears any lockout on the account.
              </Typography>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setReset(null)}>Cancel</Button>
              <Button type="submit" variant="contained" disabled={update.isPending}>
                Save
              </Button>
            </DialogActions>
          </Box>
        )}
      </Dialog>
    </>
  );
}

export function AdminFacilitiesPage() {
  const queryClient = useQueryClient();
  const facilities = useQuery({
    queryKey: ["facilities"],
    queryFn: () => api<{ results: Facility[] }>("/admin/facilities", { query: { limit: "200" } }),
  });
  const empty = { code: "", name: "", keph_level: "dispensary", ownership: "public", county: "", sub_county: "" };
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const create = useMutation({
    mutationFn: () => api("/admin/facilities", { method: "POST", body: form }),
    onSuccess: () => {
      setOpen(false);
      setForm(empty);
      void queryClient.invalidateQueries({ queryKey: ["facilities"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
  });
  if (facilities.isPending) return <Loading />;
  if (facilities.isError) return <ErrorNote error={facilities.error} />;
  const field = (name: keyof typeof empty, label: string) => (
    <TextField label={label} value={form[name]} onChange={(e) => setForm({ ...form, [name]: e.target.value })} required />
  );
  return (
    <>
      <PageHeader
        title="Facilities"
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
            Add a facility
          </Button>
        }
      />
      <Section title={`Facilities (${facilities.data.results.length})`}>
        <DataList
          caption="All facilities in the system"
          rows={facilities.data.results}
          rowKey={(f) => f.code}
          columns={[
            { key: "name", label: "Facility", primary: true, render: (f) => f.name },
            { key: "code", label: "Code", render: (f) => f.code },
            { key: "level", label: "Level", render: (f) => titleCase(f.keph_level) },
            { key: "where", label: "Sub-county", render: (f) => f.sub_county },
          ]}
        />
      </Section>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="xs">
        <Box
          component="form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <DialogTitle>Add a facility</DialogTitle>
          <DialogContent sx={GRID}>
            {field("code", "Code")}
            {field("name", "Name")}
            <TextField select label="Level" value={form.keph_level} onChange={(e) => setForm({ ...form, keph_level: e.target.value })}>
              {LEVELS.map((l) => (
                <MenuItem key={l} value={l}>
                  {titleCase(l)}
                </MenuItem>
              ))}
            </TextField>
            {field("ownership", "Ownership")}
            {field("county", "County")}
            {field("sub_county", "Sub-county")}
            {create.isError && <ErrorNote error={create.error} />}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={create.isPending}>
              Add
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </>
  );
}

export function AdminSchedulePage() {
  const queryClient = useQueryClient();
  const schedule = useQuery({ queryKey: ["admin-schedule"], queryFn: () => api<Dose[]>("/admin/schedule") });
  const [editing, setEditing] = useState<Dose | null>(null);
  const save = useMutation({
    mutationFn: (d: Dose) =>
      api(`/admin/schedule/${d.dose_code}`, {
        method: "PATCH",
        body: {
          recommended_age_days: d.recommended_age_days,
          min_age_days: d.min_age_days,
          max_age_days: d.max_age_days,
          min_interval_days: d.min_interval_days,
        },
      }),
    onSuccess: () => {
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ["admin-schedule"] });
    },
  });
  if (schedule.isPending) return <Loading />;
  if (schedule.isError) return <ErrorNote error={schedule.error} />;
  const number = (name: keyof Dose, label: string) =>
    editing && (
      <TextField
        label={label}
        type="number"
        value={editing[name]}
        onChange={(e) => setEditing({ ...editing, [name]: Number(e.target.value) })}
        slotProps={{ htmlInput: { min: 0, max: 3650 } }}
        required
      />
    );
  return (
    <>
      <PageHeader title="Schedule" subtitle="Ages are in days. A change applies to every facility from the next request." />
      <Section>
        <DataList
          caption="Vaccine schedule: age window and minimum interval per dose"
          rows={schedule.data}
          rowKey={(d) => d.dose_code}
          columns={[
            { key: "dose", label: "Dose", primary: true, render: (d) => d.dose_code },
            { key: "rec", label: "Recommended age", align: "right", render: (d) => d.recommended_age_days },
            { key: "min", label: "Minimum age", align: "right", render: (d) => d.min_age_days },
            { key: "max", label: "Maximum age", align: "right", render: (d) => d.max_age_days },
            { key: "gap", label: "Minimum interval", align: "right", render: (d) => d.min_interval_days },
            {
              key: "edit",
              label: "",
              render: (d) => (
                <Button size="small" onClick={() => setEditing({ ...d })} aria-label={`Edit ${d.dose_code}`}>
                  Edit
                </Button>
              ),
            },
          ]}
        />
      </Section>
      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="xs">
        {editing && (
          <Box
            component="form"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              save.mutate(editing);
            }}
          >
            <DialogTitle>{editing.dose_code}</DialogTitle>
            <DialogContent sx={GRID}>
              {number("recommended_age_days", "Recommended age (days)")}
              {number("min_age_days", "Minimum age (days)")}
              {number("max_age_days", "Maximum age (days)")}
              {number("min_interval_days", "Minimum interval after the previous dose (days)")}
              {save.isError && <ErrorNote error={save.error} />}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setEditing(null)}>Cancel</Button>
              <Button type="submit" variant="contained" disabled={save.isPending}>
                Save
              </Button>
            </DialogActions>
          </Box>
        )}
      </Dialog>
    </>
  );
}
