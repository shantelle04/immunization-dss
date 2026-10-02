import { Alert, Box, Button, FormControlLabel, List, ListItemButton, ListItemIcon, ListItemText, MenuItem, Paper, Switch, TextField, Typography } from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { NAV } from "../shell";
import { DataList, ErrorNote, Loading, PageHeader, Section, fmtDate, titleCase, useOnline } from "../ui";

interface ScheduleRow {
  dose_code: string;
  antigen__code: string;
  recommended_age_days: number;
  min_age_days: number;
  max_age_days: number;
  min_interval_days: number;
}

function age(days: number): string {
  if (days === 0) return "Birth";
  if (days < 180) return `${Math.round(days / 7)} weeks`;
  return `${Math.round(days / 30.44)} months`;
}

export function SchedulePage() {
  const schedule = useQuery({ queryKey: ["schedule"], queryFn: () => api<ScheduleRow[]>("/schedule") });
  if (schedule.isPending) return <Loading />;
  if (schedule.isError) return <ErrorNote error={schedule.error} />;
  return (
    <>
      <PageHeader title="Vaccine schedule" subtitle="The schedule the system uses to decide which doses are due, overdue or closed" />
      <Section>
        <DataList
          caption="Scheduled doses with recommended age and the age window in which each may be given"
          rows={schedule.data}
          rowKey={(d) => d.dose_code}
          columns={[
            { key: "dose", label: "Dose", primary: true, render: (d) => d.dose_code },
            { key: "rec", label: "Recommended at", render: (d) => age(d.recommended_age_days) },
            { key: "max", label: "Latest age", render: (d) => age(d.max_age_days) },
            { key: "gap", label: "Minimum gap", align: "right", render: (d) => (d.min_interval_days ? `${d.min_interval_days} days` : "-") },
          ]}
        />
      </Section>
    </>
  );
}

interface AuditEntry {
  at: string;
  user: string | null;
  action: string;
  entity: string;
  entity_id: string;
  cross_facility: boolean;
}

export function AuditPage() {
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<{ count: number; results: AuditEntry[] }>("/audit", { query: { limit: "100" } }),
  });
  if (audit.isPending) return <Loading />;
  if (audit.isError) return <ErrorNote error={audit.error} />;
  return (
    <>
      <PageHeader title="Audit log" subtitle={`Who created, changed, exported or read records at this facility (${audit.data.count} entries)`} />
      <Section>
        <DataList
          caption="The latest 100 audit entries"
          rows={audit.data.results}
          rowKey={(e) => `${e.at}-${e.entity}-${e.entity_id}-${e.action}`}
          maxHeight={640}
          columns={[
            { key: "what", label: "Action", primary: true, render: (e) => `${titleCase(e.action)} ${e.entity.replace(/_/g, " ")}` },
            { key: "who", label: "User", render: (e) => e.user ?? "-" },
            { key: "when", label: "When", render: (e) => new Date(e.at).toLocaleString("en-GB") },
            { key: "cross", label: "Other facility's record", render: (e) => (e.cross_facility ? "Yes" : "No") },
          ]}
        />
      </Section>
    </>
  );
}

interface ImportResult {
  dry_run: boolean;
  rows_total: number;
  rows_rejected: number;
  errors: { row_index: number; defect_code: string; message: string }[];
}

export function ImportPage() {
  const online = useOnline();
  const [kind, setKind] = useState("immunizations");
  const [dryRun, setDryRun] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const run = useMutation({
    mutationFn: () => {
      const body = new FormData();
      body.append("kind", kind);
      body.append("dry_run", String(dryRun));
      if (file) body.append("file", file);
      return api<ImportResult>("/imports", { method: "POST", body });
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    run.mutate();
  }
  return (
    <>
      <PageHeader title="Import data" subtitle="Bulk CSV import with a check of every row before anything is saved" />
      <Section title="Upload a CSV file">
        <Box component="form" onSubmit={submit} sx={{ display: "grid", gap: 2, maxWidth: 520 }}>
          <TextField select label="Kind of file" value={kind} onChange={(e) => setKind(e.target.value)}>
            <MenuItem value="immunizations">Immunization records</MenuItem>
            <MenuItem value="stock">Stock transactions</MenuItem>
          </TextField>
          <Button variant="outlined" component="label">
            {file ? file.name : "Choose a CSV file (up to 2 MB)"}
            <input type="file" accept=".csv,text/csv" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Button>
          <FormControlLabel
            control={<Switch checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />}
            label="Check only (dry run): report problems, save nothing"
          />
          <Button type="submit" variant="contained" disabled={!file || !online || run.isPending}>
            {dryRun ? "Check file" : "Import file"}
          </Button>
        </Box>
        {run.isError && <ErrorNote error={run.error} />}
      </Section>
      {run.isSuccess && (
        <Section title="Result">
          <Alert severity={run.data.rows_rejected ? "warning" : "success"} sx={{ mb: 1.5 }}>
            {run.data.rows_total} rows read, {run.data.rows_rejected} rejected.{" "}
            {run.data.dry_run ? "Nothing was saved (dry run)." : "Accepted rows were saved."}
          </Alert>
          <DataList
            caption="Rejected rows and the reason for each"
            rows={run.data.errors}
            rowKey={(e) => `${e.row_index}-${e.defect_code}`}
            empty="No row was rejected."
            maxHeight={480}
            columns={[
              { key: "row", label: "Row", primary: true, render: (e) => `Row ${e.row_index + 1}` },
              { key: "code", label: "Problem", render: (e) => titleCase(e.defect_code.toLowerCase()) },
              { key: "msg", label: "Detail", render: (e) => e.message },
            ]}
          />
        </Section>
      )}
    </>
  );
}

/** Phone only: the sections that do not fit in the bottom bar. */
export function MorePage() {
  const { user } = useAuth();
  const items = NAV.filter((i) => i.group === "facility" && user && i.roles.includes(user.role));
  return (
    <>
      <PageHeader title="More" subtitle={user?.facility ? `${user.facility.name}, ${titleCase(user.facility.level).toLowerCase()}` : undefined} />
      <Paper variant="outlined">
        <List disablePadding>
          {items.map((item) => (
            <ListItemButton key={item.to} component={RouterLink} to={item.to} divider>
              <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Paper>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
        Signed in as {user?.username} on {fmtDate(new Date().toISOString())}.
      </Typography>
    </>
  );
}
