import {
  Alert,
  Box,
  Button,
  Chip,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorNote, Loading, Section } from "../components";
import type { ChildSummary } from "./ChildrenPage";

interface DoseRow {
  dose_code: string;
  state: "not_yet" | "due" | "overdue" | "closed";
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
}

const STATE_LABEL: { [k in DoseRow["state"]]: { label: string; color: "default" | "error" | "warning" } } = {
  overdue: { label: "Overdue", color: "error" },
  due: { label: "Due", color: "warning" },
  not_yet: { label: "Not yet due", color: "default" },
  closed: { label: "Closed (age limit)", color: "default" },
};

export default function ChildPage() {
  const { id = "" } = useParams();
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
      void queryClient.invalidateQueries({ queryKey: ["child", id] });
      void queryClient.invalidateQueries({ queryKey: ["defaulters"] });
      void queryClient.invalidateQueries({ queryKey: ["balance"] });
    },
  });

  if (record.isPending) return <Loading />;
  if (record.isError) return <ErrorNote error={record.error} />;
  const { child, history, doses, read_only, as_of } = record.data;
  const open = doses.filter((d) => d.state === "due" || d.state === "overdue");

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <>
      <Section title={`${child.given_name} ${child.family_name}`}>
        <Typography>
          System ID {child.system_id}; born {child.date_of_birth}; registered at {child.registration_facility};
          caregiver {child.caregiver_name}.
        </Typography>
        {read_only && (
          <Alert severity="info" sx={{ mt: 1 }}>
            This child is registered at another facility. The record is read-only here, and this look-up is logged.
          </Alert>
        )}
      </Section>

      <Section title={`Doses not yet given (as of ${as_of})`}>
        <TableContainer>
          <Table size="small">
            <caption>Schedule status of every dose the child has not received.</caption>
            <TableHead>
              <TableRow>
                <TableCell>Dose</TableCell>
                <TableCell>Due</TableCell>
                <TableCell>State</TableCell>
                <TableCell>Closes on</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {doses.map((d) => (
                <TableRow key={d.dose_code}>
                  <TableCell>{d.dose_code}</TableCell>
                  <TableCell>{d.due_date}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={
                        STATE_LABEL[d.state].label + (d.days_overdue ? ` by ${d.days_overdue} days` : "")
                      }
                      color={STATE_LABEL[d.state].color}
                      variant={d.state === "overdue" ? "filled" : "outlined"}
                    />
                  </TableCell>
                  <TableCell>{d.closes_on}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>

      {!read_only && (
        <Section title="Record a dose">
          <Box component="form" onSubmit={submit} sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
            <TextField
              select
              label="Dose"
              value={dose}
              onChange={(e) => setDose(e.target.value)}
              sx={{ minWidth: 160 }}
              required
            >
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
            <Button type="submit" variant="contained" disabled={!dose || save.isPending}>
              Save dose
            </Button>
          </Box>
          {save.isError && <ErrorNote error={save.error} />}
          {save.isSuccess && <Alert severity="success">Dose recorded and issued from stock.</Alert>}
        </Section>
      )}

      <Section title={`Immunization history (${history.length})`}>
        <TableContainer>
          <Table size="small">
            <caption>Doses received, at any facility.</caption>
            <TableHead>
              <TableRow>
                <TableCell>Dose</TableCell>
                <TableCell>Date given</TableCell>
                <TableCell>Facility</TableCell>
                <TableCell>Lot</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map((h) => (
                <TableRow key={h.dose_code}>
                  <TableCell>{h.dose_code}</TableCell>
                  <TableCell>{h.given_on}</TableCell>
                  <TableCell>{h.facility}</TableCell>
                  <TableCell>{h.lot_number ?? "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>
    </>
  );
}
