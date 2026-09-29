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
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { ErrorNote, Loading, Section } from "../components";

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

const KINDS = ["receipt", "issue", "wastage", "loss", "adjustment"];

function StockStatus({ weeks }: { weeks: number | null }) {
  if (weeks === null) return <Chip size="small" label="No recent use" variant="outlined" />;
  if (weeks < 2) return <Chip size="small" color="error" label="Low: under 2 weeks" />;
  return <Chip size="small" label="OK" variant="outlined" />;
}

export default function InventoryPage() {
  const queryClient = useQueryClient();
  const balance = useQuery({
    queryKey: ["balance"],
    queryFn: () => api<{ as_of: string; rows: BalanceRow[] }>("/stock/balance"),
  });
  const ledger = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api<{ results: Transaction[] }>("/stock/transactions", { query: { limit: "15" } }),
  });
  const [form, setForm] = useState({ antigen: "", kind: "receipt", quantity_doses: "", occurred_on: "" });
  const record = useMutation({
    mutationFn: () =>
      api("/stock/transactions", {
        method: "POST",
        body: { ...form, quantity_doses: Number(form.quantity_doses) },
      }),
    onSuccess: () => {
      setForm({ ...form, quantity_doses: "" });
      void queryClient.invalidateQueries({ queryKey: ["balance"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    record.mutate();
  }

  if (balance.isPending) return <Loading />;
  if (balance.isError) return <ErrorNote error={balance.error} />;
  const rows = balance.data.rows;

  return (
    <>
      <Section title={`Current stock (as of ${balance.data.as_of})`}>
        <TableContainer>
          <Table size="small">
            <caption>Stock per vaccine from the stock ledger; weeks left use the last 12 weeks of use.</caption>
            <TableHead>
              <TableRow>
                <TableCell>Vaccine</TableCell>
                <TableCell align="right">Doses in stock</TableCell>
                <TableCell align="right">Use per week</TableCell>
                <TableCell align="right">Weeks left</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.antigen}>
                  <TableCell>{r.antigen_name}</TableCell>
                  <TableCell align="right">{r.balance_doses}</TableCell>
                  <TableCell align="right">{r.weekly_use_doses}</TableCell>
                  <TableCell align="right">{r.weeks_left ?? "-"}</TableCell>
                  <TableCell>
                    <StockStatus weeks={r.weeks_left} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>

      <Section title="Record a stock transaction">
        <Box component="form" onSubmit={submit} sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
          <TextField
            select
            label="Vaccine"
            value={form.antigen}
            onChange={(e) => setForm({ ...form, antigen: e.target.value })}
            sx={{ minWidth: 180 }}
            required
          >
            {rows.map((r) => (
              <MenuItem key={r.antigen} value={r.antigen}>
                {r.antigen_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Kind"
            value={form.kind}
            onChange={(e) => setForm({ ...form, kind: e.target.value })}
            sx={{ minWidth: 140 }}
          >
            {KINDS.map((k) => (
              <MenuItem key={k} value={k}>
                {k}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Doses"
            type="number"
            value={form.quantity_doses}
            onChange={(e) => setForm({ ...form, quantity_doses: e.target.value })}
            slotProps={{ htmlInput: { min: 1 } }}
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
          <Button type="submit" variant="contained" disabled={record.isPending}>
            Save
          </Button>
        </Box>
        {record.isError && <ErrorNote error={record.error} />}
        {record.isSuccess && <Alert severity="success">Saved.</Alert>}
      </Section>

      <Section title="Recent transactions">
        {ledger.isPending ? (
          <Loading />
        ) : ledger.isError ? (
          <ErrorNote error={ledger.error} />
        ) : (
          <TableContainer>
            <Table size="small">
              <caption>The latest 15 entries in this facility's stock ledger.</caption>
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Vaccine</TableCell>
                  <TableCell>Kind</TableCell>
                  <TableCell align="right">Doses</TableCell>
                  <TableCell>Lot</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {ledger.data.results.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>{t.occurred_on}</TableCell>
                    <TableCell>{t.antigen}</TableCell>
                    <TableCell>{t.kind}</TableCell>
                    <TableCell align="right">{t.quantity_doses}</TableCell>
                    <TableCell>{t.lot_number ?? "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Section>
    </>
  );
}
