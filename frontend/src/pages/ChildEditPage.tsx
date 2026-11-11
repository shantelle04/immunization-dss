import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorNote, Loading, PageHeader, SEXES, Section, ageInFull, useOnline } from "../ui";
import type { ChildSummary } from "./ChildrenPage";

type ChildDetail = ChildSummary & { caregiver_name: string; read_only: boolean };
type Form = Pick<ChildDetail, "given_name" | "family_name" | "sex" | "date_of_birth" | "caregiver_name">;

const FIELDS: (keyof Form)[] = ["given_name", "family_name", "sex", "date_of_birth", "caregiver_name"];

export default function ChildEditPage() {
  const { id = "" } = useParams();
  const child = useQuery({ queryKey: ["child-detail", id], queryFn: () => api<ChildDetail>(`/children/${id}`) });
  if (child.isPending) return <Loading />;
  if (child.isError) return <ErrorNote error={child.error} />;
  return <EditForm child={child.data} />;
}

function EditForm({ child }: { child: ChildDetail }) {
  const navigate = useNavigate();
  const online = useOnline();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Form>(() => ({
    given_name: child.given_name,
    family_name: child.family_name,
    sex: child.sex,
    date_of_birth: child.date_of_birth,
    caregiver_name: child.caregiver_name,
  }));
  const changes = Object.fromEntries(FIELDS.filter((f) => form[f] !== child[f]).map((f) => [f, form[f]]));
  const save = useMutation({
    mutationFn: () => api<ChildDetail>(`/children/${child.id}`, { method: "PATCH", body: changes }),
    onSuccess: () => {
      for (const key of ["child", "child-detail", "children", "defaulters"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      navigate(`/children/${child.id}`, { state: { saved: true } });
    },
  });
  const back = `/children/${child.id}`;
  const set = (field: keyof Form) => (e: { target: { value: string } }) => {
    save.reset();
    setForm({ ...form, [field]: e.target.value });
  };

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <>
      <Button component={RouterLink} to={back} startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>
        Back to the record
      </Button>
      <PageHeader title="Edit child details" subtitle={`${child.given_name} ${child.family_name}, ${child.system_id}`} />
      {child.read_only ? (
        <Alert severity="info">
          This child is registered at another facility. Only that facility can correct the details.
        </Alert>
      ) : (
        <Section title="Details">
          <Box
            component="form"
            onSubmit={submit}
            sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)" } }}
          >
            <TextField label="Given name" value={form.given_name} onChange={set("given_name")} required />
            <TextField label="Family name" value={form.family_name} onChange={set("family_name")} required />
            <TextField select label="Sex" value={form.sex} onChange={set("sex")}>
              {SEXES.map((s) => (
                <MenuItem key={s.code} value={s.code}>
                  {s.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Date of birth"
              type="date"
              value={form.date_of_birth}
              onChange={set("date_of_birth")}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText={
                form.date_of_birth === child.date_of_birth
                  ? `Age today: ${ageInFull(child.age_days)}`
                  : "Recorded doses must still fit the schedule's age limits."
              }
              required
            />
            <TextField
              label="Caregiver name"
              value={form.caregiver_name}
              onChange={set("caregiver_name")}
              required
              sx={{ gridColumn: { sm: "1 / -1" } }}
            />
            <Stack direction="row" spacing={1} sx={{ gridColumn: "1 / -1" }}>
              <Button
                type="submit"
                variant="contained"
                disabled={!online || save.isPending || Object.keys(changes).length === 0}
              >
                Save changes
              </Button>
              <Button component={RouterLink} to={back}>
                Cancel
              </Button>
            </Stack>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            The system ID and registration facility cannot change. Every correction is recorded in the audit log.
          </Typography>
          {save.isError && <ErrorNote error={save.error} />}
        </Section>
      )}
    </>
  );
}
