import {
  Alert,
  Box,
  Button,
  Link,
  List,
  ListItem,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { ErrorNote, Section } from "../components";

export interface ChildSummary {
  id: string;
  system_id: string;
  given_name: string;
  family_name: string;
  sex: string;
  date_of_birth: string;
  registration_facility: string;
}

const EMPTY = { given_name: "", family_name: "", sex: "F", date_of_birth: "", caregiver_name: "" };

export default function ChildrenPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState({ system_id: "", family_name: "", date_of_birth: "" });
  const [form, setForm] = useState(EMPTY);
  const [candidates, setCandidates] = useState<ChildSummary[]>([]);

  const search = useMutation({
    mutationFn: () =>
      api<ChildSummary[]>("/children/search", {
        query: Object.fromEntries(Object.entries(query).filter(([, v]) => v)),
      }),
  });
  const register = useMutation({
    mutationFn: (confirmNew: boolean) =>
      api<ChildSummary>("/children", { method: "POST", body: { ...form, confirm_new: confirmNew } }),
    onSuccess: (child) => navigate(`/children/${child.id}`),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setCandidates((error.data as { candidates: ChildSummary[] }).candidates);
      }
    },
  });

  function doSearch(event: FormEvent) {
    event.preventDefault();
    search.mutate();
  }
  function doRegister(event: FormEvent) {
    event.preventDefault();
    setCandidates([]);
    register.mutate(false);
  }

  return (
    <>
      <Section title="Find a child">
        <Box component="form" onSubmit={doSearch} sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
          <TextField
            label="System ID"
            value={query.system_id}
            onChange={(e) => setQuery({ ...query, system_id: e.target.value })}
          />
          <TextField
            label="Family name"
            value={query.family_name}
            onChange={(e) => setQuery({ ...query, family_name: e.target.value })}
          />
          <TextField
            label="Date of birth"
            type="date"
            value={query.date_of_birth}
            onChange={(e) => setQuery({ ...query, date_of_birth: e.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <Button type="submit" variant="contained">
            Search
          </Button>
        </Box>
        <Alert severity="info" sx={{ mt: 2 }}>
          Search covers every facility. Records from other facilities open read-only, and each look-up is logged.
        </Alert>
        {search.isError && <ErrorNote error={search.error} />}
        {search.isSuccess && (
          <TableContainer sx={{ mt: 2 }}>
            <Table size="small">
              <caption>{search.data.length} matching children</caption>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>System ID</TableCell>
                  <TableCell>Date of birth</TableCell>
                  <TableCell>Registered at</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {search.data.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <Link component={RouterLink} to={`/children/${c.id}`}>
                        {c.given_name} {c.family_name}
                      </Link>
                    </TableCell>
                    <TableCell>{c.system_id}</TableCell>
                    <TableCell>{c.date_of_birth}</TableCell>
                    <TableCell>{c.registration_facility}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Section>

      <Section title="Register a new child">
        <Box component="form" onSubmit={doRegister} sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
          <TextField
            label="Given name"
            value={form.given_name}
            onChange={(e) => setForm({ ...form, given_name: e.target.value })}
            required
          />
          <TextField
            label="Family name"
            value={form.family_name}
            onChange={(e) => setForm({ ...form, family_name: e.target.value })}
            required
          />
          <TextField
            select
            label="Sex"
            value={form.sex}
            onChange={(e) => setForm({ ...form, sex: e.target.value })}
            sx={{ minWidth: 110 }}
          >
            <MenuItem value="F">Female</MenuItem>
            <MenuItem value="M">Male</MenuItem>
          </TextField>
          <TextField
            label="Date of birth"
            type="date"
            value={form.date_of_birth}
            onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
            required
          />
          <TextField
            label="Caregiver name"
            value={form.caregiver_name}
            onChange={(e) => setForm({ ...form, caregiver_name: e.target.value })}
            required
          />
          <Button type="submit" variant="contained" disabled={register.isPending}>
            Register
          </Button>
        </Box>
        {candidates.length > 0 && (
          <Alert
            severity="warning"
            sx={{ mt: 2 }}
            action={
              <Button color="inherit" size="small" onClick={() => register.mutate(true)}>
                Register as new anyway
              </Button>
            }
          >
            A child with this family name and date of birth is already registered here:
            <List dense>
              {candidates.map((c) => (
                <ListItem key={c.id} disableGutters>
                  <Link component={RouterLink} to={`/children/${c.id}`}>
                    {c.given_name} {c.family_name} ({c.system_id})
                  </Link>
                </ListItem>
              ))}
            </List>
          </Alert>
        )}
        {register.isError && !(register.error instanceof ApiError && register.error.status === 409) && (
          <ErrorNote error={register.error} />
        )}
      </Section>
    </>
  );
}
