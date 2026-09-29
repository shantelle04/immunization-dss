import {
  Alert,
  Box,
  Button,
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

interface AdminUser {
  id: number;
  username: string;
  role: string;
  facility: string | null;
  is_active: boolean;
}

interface Facility {
  code: string;
  name: string;
  keph_level: string;
}

const ROLES = ["healthcare_worker", "facility_manager", "system_admin"];

export default function AdminPage() {
  const queryClient = useQueryClient();
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => api<{ results: AdminUser[] }>("/admin/users", { query: { limit: "200" } }),
  });
  const facilities = useQuery({
    queryKey: ["facilities"],
    queryFn: () => api<{ results: Facility[] }>("/admin/facilities"),
  });
  const [form, setForm] = useState({ username: "", role: "healthcare_worker", facility: "", password: "" });
  const create = useMutation({
    mutationFn: () =>
      api("/admin/users", {
        method: "POST",
        body: { ...form, facility: form.role === "system_admin" ? null : form.facility },
      }),
    onSuccess: () => {
      setForm({ ...form, username: "", password: "" });
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  if (users.isPending || facilities.isPending) return <Loading />;
  if (users.isError) return <ErrorNote error={users.error} />;
  if (facilities.isError) return <ErrorNote error={facilities.error} />;

  return (
    <>
      <Section title="Create a user">
        <Box component="form" onSubmit={submit} sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
          <TextField
            label="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
          />
          <TextField
            select
            label="Role"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            sx={{ minWidth: 200 }}
          >
            {ROLES.map((r) => (
              <MenuItem key={r} value={r}>
                {r.replace(/_/g, " ")}
              </MenuItem>
            ))}
          </TextField>
          {form.role !== "system_admin" && (
            <TextField
              select
              label="Facility"
              value={form.facility}
              onChange={(e) => setForm({ ...form, facility: e.target.value })}
              sx={{ minWidth: 220 }}
              required
            >
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
          <Button type="submit" variant="contained" disabled={create.isPending}>
            Create
          </Button>
        </Box>
        {create.isError && <ErrorNote error={create.error} />}
        {create.isSuccess && <Alert severity="success">User created.</Alert>}
      </Section>

      <Section title={`Users (${users.data.results.length})`}>
        <TableContainer sx={{ maxHeight: 480 }}>
          <Table size="small" stickyHeader>
            <caption>All accounts. Administrators have no facility and no access to clinical records.</caption>
            <TableHead>
              <TableRow>
                <TableCell>Username</TableCell>
                <TableCell>Role</TableCell>
                <TableCell>Facility</TableCell>
                <TableCell>Active</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.data.results.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{u.username}</TableCell>
                  <TableCell>{u.role.replace(/_/g, " ")}</TableCell>
                  <TableCell>{u.facility ?? "-"}</TableCell>
                  <TableCell>{u.is_active ? "Yes" : "No"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>
    </>
  );
}
