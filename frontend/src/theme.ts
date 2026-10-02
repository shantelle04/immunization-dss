import { createTheme } from "@mui/material";

// Status colours are reserved for state (good, warning, critical) and always shown with a label or icon.
const shared = {
  success: { main: "#0a7d0a" },
  warning: { main: "#b26a00" },
  error: { main: "#c62f2f" },
};

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "data" },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: "#1f63b8" },
        secondary: { main: "#0f766e" },
        background: { default: "#f6f7f9", paper: "#ffffff" },
        divider: "#e3e6ea",
        ...shared,
      },
    },
    dark: {
      palette: {
        primary: { main: "#6da7ec" },
        secondary: { main: "#4fd1c5" },
        background: { default: "#0f1114", paper: "#181b20" },
        divider: "#2a2f37",
        success: { main: "#4cc04c" },
        warning: { main: "#fab219" },
        error: { main: "#ef6b6b" },
      },
    },
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily:
      'Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    h4: { fontWeight: 700, letterSpacing: "-0.02em" },
    h5: { fontWeight: 700, letterSpacing: "-0.01em" },
    h6: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { minHeight: 44 } } },
    MuiPaper: { defaultProps: { elevation: 0 } },
    MuiTextField: { defaultProps: { size: "small" } },
    MuiTableCell: { styleOverrides: { head: { fontWeight: 600, whiteSpace: "nowrap" } } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiTab: { styleOverrides: { root: { minHeight: 48 } } },
  },
});

// Chart ink: one series hue, validated for both modes; the forecast is the same hue, dashed, with a band.
export const CHART = {
  light: { series: "#2a78d6", grid: "#e1e0d9", axis: "#898781", ink: "#52514e" },
  dark: { series: "#3987e5", grid: "#2c2c2a", axis: "#898781", ink: "#c3c2b7" },
};
