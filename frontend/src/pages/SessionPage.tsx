import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  FormControlLabel,
  FormGroup,
  Link,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { DataList, EmptyState, ErrorNote, Loading, PageHeader, Section, StatusChip, fmtDate, titleCase, useOnline } from "../ui";

interface PlanChild {
  rank: number;
  child_id: string;
  system_id: string;
  name: string;
  caregiver_name: string;
  date_of_birth: string;
  attended: boolean | null;
  doses: { dose_code: string; given: boolean }[];
}

interface Need {
  antigen: string;
  antigen_name: string;
  doses_planned: number;
  vials_planned: number;
  in_stock_doses: number;
  forecast_week_doses: number | null;
  shortfall_doses: number;
  shortfall_with_forecast_doses: number | null;
}

interface SessionDetail {
  id: number;
  date: string;
  kind: string;
  location_name: string;
  capacity: number | null;
  status: string;
  children: PlanChild[];
  needs: Need[];
}

function ChildRow({ sessionId, child }: { sessionId: number; child: PlanChild }) {
  const online = useOnline();
  const queryClient = useQueryClient();
  const pending = child.doses.filter((d) => !d.given).map((d) => d.dose_code);
  const [chosen, setChosen] = useState<string[]>(pending);
  const save = useMutation({
    mutationFn: (attended: boolean) =>
      api<SessionDetail>(`/sessions/${sessionId}/attendance`, {
        method: "POST",
        body: { child_id: child.child_id, attended, doses: attended ? chosen.filter((c) => pending.includes(c)) : [] },
      }),
    onSuccess: (detail) => {
      queryClient.setQueryData(["session", String(sessionId)], detail);
      for (const key of ["defaulters", "balance", "dashboard", "sessions"]) void queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <Paper component="li" variant="outlined" sx={{ p: 1.5 }}>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Link component={RouterLink} to={`/children/${child.child_id}`} sx={{ fontWeight: 600 }}>
            {child.rank}. {child.name}
          </Link>
          <Typography variant="caption" color="text.secondary" component="p">
            {child.system_id}; born {fmtDate(child.date_of_birth)}; caregiver {child.caregiver_name}
          </Typography>
        </Box>
        {child.attended === true && <StatusChip tone="good" label="Attended" />}
        {child.attended === false && <StatusChip tone="warning" label="Did not attend" />}
      </Box>
      <FormGroup row sx={{ mt: 0.5 }}>
        {child.doses.map((d) =>
          d.given ? (
            <Chip key={d.dose_code} size="small" color="success" variant="outlined" label={`${d.dose_code} given`} sx={{ mr: 1, my: 0.75 }} />
          ) : (
            <FormControlLabel
              key={d.dose_code}
              label={d.dose_code}
              control={
                <Checkbox
                  checked={chosen.includes(d.dose_code)}
                  onChange={(e) =>
                    setChosen(e.target.checked ? [...chosen, d.dose_code] : chosen.filter((c) => c !== d.dose_code))
                  }
                />
              }
            />
          ),
        )}
      </FormGroup>
      <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
        <Button
          size="small"
          variant="contained"
          disabled={!online || save.isPending || (pending.length === 0 && child.attended === true)}
          onClick={() => save.mutate(true)}
          aria-label={`Record attendance and doses for ${child.name}`}
        >
          Attended, save doses
        </Button>
        <Button
          size="small"
          disabled={!online || save.isPending || child.attended !== null}
          onClick={() => save.mutate(false)}
          aria-label={`Mark ${child.name} as not attended`}
        >
          Did not attend
        </Button>
      </Stack>
      {save.isError && <ErrorNote error={save.error} />}
    </Paper>
  );
}

export default function SessionPage() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const online = useOnline();
  const queryClient = useQueryClient();
  const session = useQuery({ queryKey: ["session", id], queryFn: () => api<SessionDetail>(`/sessions/${id}`) });
  const plan = useMutation({
    mutationFn: () => api<SessionDetail>(`/sessions/${id}/plan`, { method: "POST" }),
    onSuccess: (detail) => queryClient.setQueryData(["session", id], detail),
  });
  if (session.isPending) return <Loading />;
  if (session.isError) return <ErrorNote error={session.error} />;
  const s = session.data;
  const manager = user?.role === "facility_manager";
  const short = s.needs.filter((n) => n.shortfall_doses > 0);
  return (
    <>
      <Button component={RouterLink} to="/scheduling?tab=sessions" startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>
        Sessions
      </Button>
      <PageHeader
        title={s.location_name}
        subtitle={`${fmtDate(s.date)}, ${s.kind} session, ${titleCase(s.status).toLowerCase()}${s.capacity ? `, capacity ${s.capacity}` : ""}`}
        action={
          manager && s.status === "planned" ? (
            <Button variant="contained" onClick={() => plan.mutate()} disabled={!online || plan.isPending}>
              {s.children.length ? "Regenerate plan" : "Generate plan"}
            </Button>
          ) : undefined
        }
      />
      {plan.isError && <ErrorNote error={plan.error} />}

      <Section title="Vaccines needed">
        {s.needs.length === 0 ? (
          <EmptyState>No plan yet. The facility manager generates it from the ranked defaulter list.</EmptyState>
        ) : (
          <>
            {short.length > 0 && (
              <Alert severity="error" sx={{ mb: 1.5 }}>
                Not enough stock for this plan: {short.map((n) => `${n.antigen_name} (short by ${n.shortfall_doses})`).join(", ")}.
              </Alert>
            )}
            <DataList
              caption="Doses and vials the plan needs, against current stock and the forecast for that week"
              rows={s.needs}
              rowKey={(n) => n.antigen}
              columns={[
                { key: "name", label: "Vaccine", primary: true, render: (n) => n.antigen_name },
                { key: "doses", label: "Doses planned", align: "right", render: (n) => n.doses_planned },
                { key: "vials", label: "Vials", align: "right", render: (n) => n.vials_planned },
                { key: "stock", label: "In stock", align: "right", render: (n) => n.in_stock_doses },
                { key: "fc", label: "Other forecast use that week", align: "right", render: (n) => n.forecast_week_doses ?? "-" },
                {
                  key: "short",
                  label: "Shortfall",
                  align: "right",
                  render: (n) =>
                    n.shortfall_doses > 0 ? (
                      <StatusChip tone="critical" label={`${n.shortfall_doses} short`} />
                    ) : n.shortfall_with_forecast_doses ? (
                      <StatusChip tone="warning" label={`${n.shortfall_with_forecast_doses} with forecast`} />
                    ) : (
                      <StatusChip tone="good" label="Covered" />
                    ),
                },
              ]}
            />
          </>
        )}
      </Section>

      <Section title={`Children planned (${s.children.length})`}>
        {s.children.length === 0 ? (
          <EmptyState>No child is planned for this session.</EmptyState>
        ) : (
          <Stack component="ul" spacing={1} sx={{ listStyle: "none", p: 0, m: 0 }} aria-label="Children planned, in priority order">
            {s.children.map((c) => (
              <ChildRow key={`${c.child_id}-${c.doses.filter((d) => d.given).length}`} sessionId={s.id} child={c} />
            ))}
          </Stack>
        )}
      </Section>
    </>
  );
}
