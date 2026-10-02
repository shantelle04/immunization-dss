import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/FileDownloadOutlined";
import { Alert, Avatar, Box, Button, MenuItem, Paper, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { api } from "../api";
import { DataList, ErrorNote, Loading, PageHeader, Section, StatusChip, fmtDate, useOnline, type Tone } from "../ui";
import type { ChildSummary } from "./ChildrenPage";

type State = "given" | "not_yet" | "due" | "overdue" | "closed";

interface DoseRow {
  dose_code: string;
  antigen: string;
  state: State;
  due_date: string;
  closes_on: string;
  days_overdue: number;
}

interface ChildRecord {
  as_of: string;
  read_only: boolean;
  child: ChildSummary & { caregiver_name: string };
  history: { dose_code: string; given_on: string; facility: string; lot_number: string | null }[];
  doses: DoseRow[];
  schedule?: { dose_code: string; antigen: string; state: State; due_date: string; given_on: string | null }[];
}

const STATE: Record<State, { label: string; tone: Tone }> = {
  given: { label: "Given", tone: "good" },
  overdue: { label: "Overdue", tone: "critical" },
  due: { label: "Due", tone: "warning" },
  not_yet: { label: "Not yet due", tone: "default" },
  closed: { label: "Missed (age limit passed)", tone: "default" },
};

export default function ChildPage() {
  const { id = "" } = useParams();
  const online = useOnline();
  const queryClient = useQueryClient();
  const record = useQuery({
    queryKey: ["child", id],
    queryFn: () => api<ChildRecord>(`/children/${id}/immunizations`),
  });
  const [dose, setDose] = useState("");
  const [givenOn, setGivenOn] = useState("");
  const save = useMutation({
    mutationFn: () =>
      api(`/children/${id}/immunizations`, {
        method: "POST",
        body: { dose_code: dose, given_on: givenOn || record.data?.as_of },
      }),
    onSuccess: () => {
      setDose("");
      for (const key of ["defaulters", "balance", "dashboard"]) void queryClient.invalidateQueries({ queryKey: [key] });
      void queryClient.invalidateQueries({ queryKey: ["child", id] });
    },
  });
  const exportFhir = useMutation({
    mutationFn: async () => {
      const bundle = await api<unknown>(`/children/${id}/fhir`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/fhir+json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `${record.data?.child.system_id ?? "child"}.fhir.json`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  if (record.isPending) return <Loading />;
  if (record.isError) return <ErrorNote error={record.error} />;
  const { child, history, doses, read_only, as_of } = record.data;
  const open = doses.filter((d) => d.state === "due" || d.state === "overdue");
  const overdue = doses.filter((d) => d.state === "overdue").length;
  const timeline =
    record.data.schedule ?? doses.map((d) => ({ ...d, given_on: null as string | null }));

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <>
      <Button component={RouterLink} to="/children" startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>
        Children
      </Button>
      <PageHeader
        title={`${child.given_name} ${child.family_name}`}
        subtitle={`System ID ${child.system_id}`}
        action={
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={() => exportFhir.mutate()}
            disabled={!online || exportFhir.isPending}
          >
            Export FHIR record
          </Button>
        }
      />
      {exportFhir.isError && <ErrorNote error={exportFhir.error} />}
      <Paper variant="outlined" sx={{ p: 2, mb: { xs: 2, sm: 3 }, display: "flex", gap: 2, flexWrap: "wrap", alignItems: "center" }}>
        <Avatar sx={{ bgcolor: "secondary.main", width: 48, height: 48 }}>
          {child.given_name.charAt(0)}
          {child.family_name.charAt(0)}
        </Avatar>
        <Box
          component="dl"
          sx={{
            m: 0,
            flexGrow: 1,
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: { xs: "repeat(2, 1fr)", md: "repeat(4, 1fr)" },
            "& dt": { fontSize: 12, color: "text.secondary" },
            "& dd": { m: 0, fontWeight: 600 },
          }}
        >
          <div>
            <dt>Born</dt>
            <dd>{fmtDate(child.date_of_birth)}</dd>
          </div>
          <div>
            <dt>Sex</dt>
            <dd>{child.sex === "F" ? "Female" : "Male"}</dd>
          </div>
          <div>
            <dt>Caregiver</dt>
            <dd>{child.caregiver_name}</dd>
          </div>
          <div>
            <dt>Registered at</dt>
            <dd>{child.registration_facility}</dd>
          </div>
        </Box>
        {overdue > 0 && <StatusChip tone="critical" label={`${overdue} overdue`} />}
      </Paper>
      {read_only && (
        <Alert severity="info" sx={{ mb: 2 }}>
          This child is registered at another facility. The record is read-only here, and this look-up is logged.
        </Alert>
      )}

      {!read_only && (
        <Section title="Record a dose">
          {open.length === 0 ? (
            <Typography color="text.secondary">No dose is due today.</Typography>
          ) : (
            <Box
              component="form"
              onSubmit={submit}
              sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" } }}
            >
              <TextField select label="Dose" value={dose} onChange={(e) => setDose(e.target.value)} required>
                {open.map((d) => (
                  <MenuItem key={d.dose_code} value={d.dose_code}>
                    {d.dose_code}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                label="Date given"
                type="date"
                value={givenOn || as_of}
                onChange={(e) => setGivenOn(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <Button type="submit" variant="contained" disabled={!dose || !online || save.isPending}>
                Save dose
              </Button>
            </Box>
          )}
          {save.isError && <ErrorNote error={save.error} />}
          {save.isSuccess && (
            <Alert severity="success" sx={{ mt: 1.5 }}>
              Dose recorded and issued from stock.
            </Alert>
          )}
        </Section>
      )}

      <Section title={`Schedule (as of ${fmtDate(as_of)})`}>
        <DataList
          caption="Every scheduled dose with its state for this child"
          rows={timeline}
          rowKey={(d) => d.dose_code}
          columns={[
            { key: "dose", label: "Dose", primary: true, render: (d) => d.dose_code },
            {
              key: "state",
              label: "State",
              render: (d) => {
                const late = doses.find((x) => x.dose_code === d.dose_code)?.days_overdue;
                return <StatusChip tone={STATE[d.state].tone} label={STATE[d.state].label + (late ? ` by ${late} days` : "")} />;
              },
            },
            { key: "due", label: "Due", render: (d) => fmtDate(d.due_date) },
            { key: "given", label: "Given", render: (d) => fmtDate(d.given_on) },
          ]}
        />
      </Section>

      <Section title={`Immunization history (${history.length})`}>
        <DataList
          caption="Doses received, at any facility"
          rows={history}
          rowKey={(h) => h.dose_code}
          empty="No dose has been recorded yet."
          columns={[
            { key: "dose", label: "Dose", primary: true, render: (h) => h.dose_code },
            { key: "date", label: "Date given", render: (h) => fmtDate(h.given_on) },
            { key: "facility", label: "Facility", render: (h) => h.facility },
            { key: "lot", label: "Lot", render: (h) => h.lot_number ?? "-" },
          ]}
        />
      </Section>
    </>
  );
}
