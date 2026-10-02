import { Box, Typography } from "@mui/material";
import { useColorScheme } from "@mui/material/styles";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART } from "../theme";
import { fmtDate } from "../ui";

export interface ForecastSeries {
  antigen: string;
  antigen_name: string;
  model: string;
  accuracy: { model: string; mase: number | null; mae: number; smape: number; coverage80: number } | null;
  history: { week_start: string; issued: number }[];
  forecast: { week_start: string; yhat: number; lo80: number; hi80: number }[];
}

interface Point {
  week: string;
  issued?: number;
  forecast?: number;
  band?: [number, number];
}

export function chartPoints(series: ForecastSeries): Point[] {
  const points: Point[] = series.history.map((h) => ({ week: h.week_start, issued: h.issued }));
  // The forecast line starts at the last observed week so the two lines join.
  if (points.length > 0) points[points.length - 1].forecast = points[points.length - 1].issued;
  for (const f of series.forecast) points.push({ week: f.week_start, forecast: f.yhat, band: [f.lo80, f.hi80] });
  return points;
}

function Tip({ active, payload, label }: { active?: boolean; payload?: { payload: Point }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <Box sx={{ bgcolor: "background.paper", border: 1, borderColor: "divider", borderRadius: 1, p: 1, fontSize: 13 }}>
      <Typography variant="caption" color="text.secondary">
        Week of {fmtDate(label)}
      </Typography>
      {p.band ? (
        <>
          <Box>
            Forecast <strong>{p.forecast}</strong> doses
          </Box>
          <Box>
            80% interval {p.band[0]} to {p.band[1]}
          </Box>
        </>
      ) : (
        <Box>
          Issued <strong>{p.issued}</strong> doses
        </Box>
      )}
    </Box>
  );
}

export default function ForecastChart({ series }: { series: ForecastSeries }) {
  const { mode, systemMode } = useColorScheme();
  const ink = CHART[(mode === "system" ? systemMode : mode) === "dark" ? "dark" : "light"];
  const data = chartPoints(series);
  const firstForecast = series.forecast[0]?.week_start;
  return (
    <Box role="img" aria-label={`Weekly doses of ${series.antigen_name}: last 26 weeks and 4-week forecast`}>
      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", mb: 1, fontSize: 13, color: "text.secondary" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box sx={{ width: 18, borderTop: `2px solid ${ink.series}` }} /> Doses issued
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box sx={{ width: 18, borderTop: `2px dashed ${ink.series}` }} /> Forecast
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box sx={{ width: 18, height: 10, bgcolor: ink.series, opacity: 0.18, borderRadius: 0.5 }} /> 80% interval
        </Box>
      </Box>
      <Box sx={{ height: { xs: 240, sm: 300 } }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke={ink.grid} vertical={false} />
            <XAxis
              dataKey="week"
              tickFormatter={(w: string) => fmtDate(w, true)}
              tick={{ fill: ink.axis, fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: ink.grid }}
              minTickGap={32}
            />
            <YAxis tick={{ fill: ink.axis, fontSize: 12 }} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip content={<Tip />} />
            <Area dataKey="band" stroke="none" fill={ink.series} fillOpacity={0.18} isAnimationActive={false} />
            <Line dataKey="issued" stroke={ink.series} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line
              dataKey="forecast"
              stroke={ink.series}
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={{ r: 3, fill: ink.series, strokeWidth: 0 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </Box>
      {firstForecast && (
        <Typography variant="caption" color="text.secondary">
          Forecast from the week of {fmtDate(firstForecast)}.
        </Typography>
      )}
    </Box>
  );
}
