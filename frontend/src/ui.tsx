import {
  Alert,
  Box,
  Card,
  CardActionArea,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { useEffect, useState, type ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";

const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const SHORT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export function fmtDate(iso: string | null | undefined, short = false): string {
  if (!iso) return "-";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : (short ? SHORT : DATE).format(d);
}

export function ageLabel(days: number): string {
  if (days < 60) return `${Math.floor(days / 7)} wk`;
  const months = Math.floor(days / 30.44);
  return months < 24 ? `${months} mo` : `${Math.floor(months / 12)} y`;
}

export function titleCase(text: string): string {
  const words = text.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

export function useIsMobile(): boolean {
  const theme = useTheme();
  return useMediaQuery(theme.breakpoints.down("sm"));
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap", gap: 1.5, mb: { xs: 2, sm: 3 } }}>
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography variant="h5" component="h1" sx={{ fontSize: { xs: 22, sm: 26 } }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {action}
    </Box>
  );
}

export function Section({
  title,
  children,
  action,
  dense,
}: {
  title?: string;
  children: ReactNode;
  action?: ReactNode;
  dense?: boolean;
}) {
  return (
    <Paper variant="outlined" component="section" sx={{ p: dense ? 0 : { xs: 2, sm: 2.5 }, mb: { xs: 2, sm: 3 }, overflow: "hidden" }}>
      {(title || action) && (
        <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 1, mb: 1.5, p: dense ? 2 : 0, pb: 0 }}>
          <Typography variant="h6" component="h2" sx={{ flexGrow: 1, fontSize: 17 }}>
            {title}
          </Typography>
          {action}
        </Box>
      )}
      {children}
    </Paper>
  );
}

export type Tone = "default" | "good" | "warning" | "critical";
const TONE_COLOR: Record<Tone, string> = {
  default: "text.primary",
  good: "success.main",
  warning: "warning.main",
  critical: "error.main",
};

export function StatTile({
  label,
  value,
  hint,
  tone = "default",
  icon,
  to,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: Tone;
  icon?: ReactNode;
  to?: string;
}) {
  const body = (
    <Box sx={{ p: 2, display: "flex", gap: 1.5, alignItems: "flex-start", height: "100%" }}>
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
        <Typography component="p" sx={{ fontSize: 30, fontWeight: 700, lineHeight: 1.2, color: TONE_COLOR[tone] }}>
          {value}
        </Typography>
        {hint && (
          <Typography variant="caption" color="text.secondary">
            {hint}
          </Typography>
        )}
      </Box>
      {icon && (
        <Box sx={{ color: tone === "default" ? "text.secondary" : TONE_COLOR[tone], display: { xs: "none", sm: "flex" } }}>
          {icon}
        </Box>
      )}
    </Box>
  );
  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      {to ? (
        <CardActionArea component={RouterLink} to={to} sx={{ height: "100%" }} aria-label={`${label}: ${String(value)}`}>
          {body}
        </CardActionArea>
      ) : (
        body
      )}
    </Card>
  );
}

export function TileGrid({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={{
        display: "grid",
        gap: { xs: 1.5, sm: 2 },
        gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", md: "repeat(4, minmax(0, 1fr))" },
        mb: { xs: 2, sm: 3 },
      }}
    >
      {children}
    </Box>
  );
}

export function StatusChip({ tone, label }: { tone: Tone; label: string }) {
  const color = tone === "critical" ? "error" : tone === "warning" ? "warning" : tone === "good" ? "success" : "default";
  return <Chip size="small" color={color} label={label} variant={tone === "critical" ? "filled" : "outlined"} />;
}

export function Loading() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
      <CircularProgress aria-label="Loading" />
    </Box>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <Alert severity="error" sx={{ my: 1 }}>
      {error instanceof Error ? error.message : "Something went wrong."}
    </Alert>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
      {children}
    </Typography>
  );
}

export interface Column<T> {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  align?: "right";
  /** Shown as the card heading on small screens. */
  primary?: boolean;
  hideOnMobile?: boolean;
}

/** A table on wide screens; the same rows as labelled cards on phones, so nothing scrolls sideways. */
export function DataList<T>({
  rows,
  columns,
  rowKey,
  caption,
  empty = "Nothing to show.",
  maxHeight,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  caption: string;
  empty?: string;
  maxHeight?: number;
}) {
  const mobile = useIsMobile();
  if (rows.length === 0) return <EmptyState>{empty}</EmptyState>;
  if (mobile) {
    const primary = columns.find((c) => c.primary) ?? columns[0];
    const rest = columns.filter((c) => c !== primary && !c.hideOnMobile);
    return (
      <Stack component="ul" spacing={1} aria-label={caption} sx={{ listStyle: "none", p: 0, m: 0 }}>
        {rows.map((row) => (
          <Paper component="li" variant="outlined" key={rowKey(row)} sx={{ p: 1.5 }}>
            <Box sx={{ fontWeight: 600, mb: 0.5 }}>{primary.render(row)}</Box>
            <Box sx={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 1.5, rowGap: 0.25, alignItems: "center" }}>
              {rest.map((c) => (
                <Box key={c.key} sx={{ display: "contents" }}>
                  <Typography variant="caption" color="text.secondary">
                    {c.label}
                  </Typography>
                  <Box sx={{ fontSize: 14, textAlign: "right", minWidth: 0 }}>{c.render(row)}</Box>
                </Box>
              ))}
            </Box>
          </Paper>
        ))}
      </Stack>
    );
  }
  return (
    <TableContainer sx={{ maxHeight }}>
      <Table size="small" stickyHeader={Boolean(maxHeight)}>
        <caption>{caption}</caption>
        <TableHead>
          <TableRow>
            {columns.map((c) => (
              <TableCell key={c.key} align={c.align}>
                {c.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={rowKey(row)} hover>
              {columns.map((c) => (
                <TableCell key={c.key} align={c.align}>
                  {c.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
