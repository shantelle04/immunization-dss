import VaccinesIcon from "@mui/icons-material/VaccinesOutlined";
import { Alert, Avatar, Box, Button, Paper, TextField, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { homeFor } from "../routes";
import { ThemeToggle } from "../shell";

export default function LoginPage() {
  const { user, signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user)} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signIn(username, password);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box
      component="main"
      sx={{
        minHeight: "100dvh",
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
        bgcolor: "background.default",
      }}
    >
      <Box
        sx={{
          display: { xs: "none", md: "flex" },
          flexDirection: "column",
          justifyContent: "center",
          gap: 2,
          p: 8,
          color: "#fff",
          background: "linear-gradient(150deg, #184f95 0%, #0f766e 100%)",
        }}
      >
        <Typography variant="h4" component="p">
          Every child, every dose, on time.
        </Typography>
        <Typography sx={{ opacity: 0.9, maxWidth: 440 }}>
          Vaccine stock forecasts and stock-out alerts, a prioritised defaulter list for outreach, and one
          immunization record per child that any authorised facility can retrieve.
        </Typography>
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", p: 2, position: "relative" }}>
        <Box sx={{ position: "absolute", top: 8, right: 8 }}>
          <ThemeToggle />
        </Box>
        <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, width: "100%", maxWidth: 400 }}>
          <Avatar variant="rounded" sx={{ bgcolor: "primary.main", mb: 2 }}>
            <VaccinesIcon />
          </Avatar>
          <Typography variant="h5" component="h1">
            Immunization Decision Support System
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
            Sign in with the account your administrator gave you.
          </Typography>
          <form onSubmit={submit} noValidate>
            <TextField
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              fullWidth
              margin="normal"
              size="medium"
              required
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              fullWidth
              margin="normal"
              size="medium"
              required
            />
            {error && (
              <Alert severity="error" sx={{ mt: 1 }}>
                {error}
              </Alert>
            )}
            <Button type="submit" variant="contained" size="large" fullWidth sx={{ mt: 2 }} disabled={busy}>
              Sign in
            </Button>
          </form>
          <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 2 }}>
            Repeated failed attempts lock the account for a short time. All records in this system are synthetic.
          </Typography>
        </Paper>
      </Box>
    </Box>
  );
}
