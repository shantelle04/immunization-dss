import { Alert, Box, Button, Paper, TextField, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { homeFor } from "../routes";

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
    <Box component="main" sx={{ display: "flex", justifyContent: "center", px: 2, py: 8 }}>
      <Paper variant="outlined" sx={{ p: 3, width: "100%", maxWidth: 380 }}>
        <Typography variant="h5" component="h1" gutterBottom>
          Immunization Decision Support System
        </Typography>
        <form onSubmit={submit} noValidate>
          <TextField
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            fullWidth
            margin="normal"
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
            required
          />
          {error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {error}
            </Alert>
          )}
          <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }} disabled={busy}>
            Sign in
          </Button>
        </form>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Accounts are created by the system administrator. Repeated failed attempts lock the account for a
          short time.
        </Typography>
      </Paper>
    </Box>
  );
}
