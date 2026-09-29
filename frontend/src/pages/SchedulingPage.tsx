import { Link, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";
import { api } from "../api";
import { ErrorNote, Loading, Section } from "../components";

interface Defaulter {
  rank: number;
  child_id: string;
  system_id: string;
  name: string;
  age_days: number;
  overdue_count: number;
  overdue: string[];
  days_to_nearest_max_age: number;
}

function months(days: number): string {
  return `${Math.floor(days / 30.44)} mo`;
}

export default function SchedulingPage() {
  const list = useQuery({
    queryKey: ["defaulters"],
    queryFn: () => api<{ as_of: string; count: number; results: Defaulter[] }>("/defaulters"),
  });
  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorNote error={list.error} />;
  const { as_of, count, results } = list.data;
  return (
    <Section title={`Defaulters (${count}) as of ${as_of}`}>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Children under 2 with a dose more than 28 days past its due date. Order: most overdue doses first, then
        the child closest to a vaccine's upper age limit.
      </Typography>
      <TableContainer sx={{ maxHeight: 600 }}>
        <Table size="small" stickyHeader>
          <caption>Prioritised defaulter list for outreach planning.</caption>
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell>
              <TableCell>Child</TableCell>
              <TableCell>Age</TableCell>
              <TableCell align="right">Overdue doses</TableCell>
              <TableCell>Doses</TableCell>
              <TableCell align="right">Days to nearest age limit</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {results.map((d) => (
              <TableRow key={d.child_id}>
                <TableCell>{d.rank}</TableCell>
                <TableCell>
                  <Link component={RouterLink} to={`/children/${d.child_id}`}>
                    {d.name}
                  </Link>
                  <Typography variant="caption" display="block" color="text.secondary">
                    {d.system_id}
                  </Typography>
                </TableCell>
                <TableCell>{months(d.age_days)}</TableCell>
                <TableCell align="right">{d.overdue_count}</TableCell>
                <TableCell>{d.overdue.join(", ")}</TableCell>
                <TableCell align="right">{d.days_to_nearest_max_age}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Section>
  );
}
