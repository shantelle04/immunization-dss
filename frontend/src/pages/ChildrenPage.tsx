import {
  Alert,
  Box,
  Button,
  Link,
  List,
  ListItem,
  MenuItem,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { DataList, ErrorNote, Loading, PageHeader, Section, fmtDate, useOnline, type Column } from "../ui";

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
const FORM_GRID = { display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" } };

const COLUMNS: Column<ChildSummary>[] = [
  {
    key: "name",
    label: "Name",
    primary: true,
    render: (c) => (
      <Link component={RouterLink} to={`/children/${c.id}`}>
        {c.given_name} {c.family_name}
      </Link>
    ),
  },
  { key: "id", label: "System ID", render: (c) => c.system_id },
  { key: "dob", label: "Date of birth", render: (c) => fmtDate(c.date_of_birth) },
  { key: "facility", label: "Registered at", render: (c) => c.registration_facility },
];

function Find() {
  const [query, setQuery] = useState({ system_id: "", family_name: "", date_of_birth: "" });
  const search = useMutation({
    mutationFn: () =>
      api<ChildSummary[]>("/children/search", {
        query: Object.fromEntries(Object.entries(query).filter(([, v]) => v)),
      }),
  });
  const recent = useQuery({
    queryKey: ["children"],
    queryFn: () => api<{ results: ChildSummary[] }>("/children", { query: { limit: "10" } }),
  });
  function doSearch(event: FormEvent) {
    event.preventDefault();
    search.mutate();
  }
  return (
    <>
      <Section title="Find a child">
        <Box component="form" onSubmit={doSearch} sx={FORM_GRID}>
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
          <Button type="submit" variant="contained" disabled={search.isPending}>
            Search
          </Button>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
          Give the exact system ID, or the family name with the date of birth. Search covers every facility;
          records from other facilities open read-only, and each look-up is logged.
        </Typography>
        {search.isError && <ErrorNote error={search.error} />}
        {search.isSuccess && (
          <Box sx={{ mt: 2 }}>
            <DataList
              caption={`${search.data.length} matching children`}
              rows={search.data}
              rowKey={(c) => c.id}
              columns={COLUMNS}
              empty="No child matches. Check the spelling, or register the child."
            />
          </Box>
        )}
      </Section>
      <Section title="Recently registered here">
        {recent.isPending ? (
          <Loading />
        ) : recent.isError ? (
          <ErrorNote error={recent.error} />
        ) : (
          <DataList
            caption="The 10 children most recently registered at this facility"
            rows={recent.data.results}
            rowKey={(c) => c.id}
            columns={COLUMNS.slice(0, 3)}
          />
        )}
      </Section>
    </>
  );
}

function Register() {
  const navigate = useNavigate();
  const online = useOnline();
  const [form, setForm] = useState(EMPTY);
  const [candidates, setCandidates] = useState<ChildSummary[]>([]);
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
  function doRegister(event: FormEvent) {
    event.preventDefault();
    setCandidates([]);
    register.mutate(false);
  }
  return (
    <Section title="Register a new child">
      <Box component="form" onSubmit={doRegister} sx={FORM_GRID}>
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
        <TextField select label="Sex" value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value })}>
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
        <Button type="submit" variant="contained" disabled={!online || register.isPending}>
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
  );
}

export default function ChildrenPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "register" ? "register" : "find";
  return (
    <>
      <PageHeader title="Children" subtitle="Health passport: find a record at any facility, or register a child" />
      <Tabs
        value={tab}
        onChange={(_, v: string) => setParams(v === "find" ? {} : { tab: v }, { replace: true })}
        aria-label="Children sections"
        sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}
      >
        <Tab value="find" label="Find" />
        <Tab value="register" label="Register" />
      </Tabs>
      {tab === "find" ? <Find /> : <Register />}
    </>
  );
}
