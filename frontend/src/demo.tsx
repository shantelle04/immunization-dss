import { Alert, AlertTitle, Box, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { demoAccounts, type Role, type User } from "./api";
import { useAuth } from "./auth";
import { titleCase } from "./ui";

// Demonstration sign-in (D-46). Nothing here appears unless the server reports demo accounts, which it does
// only on a local demonstration installation with IMMDSS_DEMO_LOGIN on.
export function useDemoAccounts(): User[] {
  const accounts = useQuery({ queryKey: ["demo-accounts"], queryFn: demoAccounts, staleTime: Infinity });
  return accounts.data ?? [];
}

const ROLES: { role: Role; label: string }[] = [
  { role: "healthcare_worker", label: "Health worker" },
  { role: "facility_manager", label: "Facility manager" },
  { role: "system_admin", label: "System administrator" },
];

export function DemoPicker({ accounts }: { accounts: User[] }) {
  const { signInDemo } = useAuth();
  const facilities = [
    ...new Map(accounts.filter((a) => a.facility).map((a) => [a.facility!.code, a.facility!])).values(),
  ];
  const [facility, setFacility] = useState(facilities[0]?.code ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function pick(username: string) {
    setBusy(true);
    setError("");
    try {
      await signInDemo(username);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign in failed.");
      setBusy(false);
    }
  }

  return (
    <Box component="section" aria-labelledby="demo-title" sx={{ mt: 3 }}>
      <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>
        <AlertTitle id="demo-title">Demonstration only</AlertTitle>
        Pick a role to sign in without a password. This shortcut exists only on this demonstration installation,
        which holds synthetic records. In real use every person signs in with their own username and password
        above, and this panel does not appear.
      </Alert>
      {facilities.length > 0 && (
        <TextField
          select
          label="Facility"
          value={facility}
          onChange={(e) => setFacility(e.target.value)}
          fullWidth
          sx={{ mb: 1.5 }}
        >
          {facilities.map((f) => (
            <MenuItem key={f.code} value={f.code}>
              {f.name} ({f.code})
            </MenuItem>
          ))}
        </TextField>
      )}
      <Stack spacing={1}>
        {ROLES.map(({ role, label }) => {
          const account = accounts.find(
            (a) => a.role === role && (role === "system_admin" || a.facility?.code === facility),
          );
          return (
            <Button
              key={role}
              variant="outlined"
              disabled={!account || busy}
              onClick={() => account && void pick(account.username)}
              sx={{ justifyContent: "space-between" }}
            >
              <span>Sign in as {label.toLowerCase()}</span>
              <Typography component="span" variant="caption" color="text.secondary">
                {account ? account.username : "no demo account"}
              </Typography>
            </Button>
          );
        })}
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
}

export function DemoBanner({ user, onSwitch }: { user: User; onSwitch: () => void }) {
  return (
    <Alert
      severity="warning"
      square
      sx={{ py: 0, alignItems: "center" }}
      action={
        <Button color="inherit" size="small" onClick={onSwitch}>
          Switch account
        </Button>
      }
    >
      <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
        Demonstration mode: signed in as {user.username} ({titleCase(user.role).toLowerCase()}). Real users sign in
        with their own details.
      </Box>
      <Box component="span" sx={{ display: { sm: "none" } }}>
        Demo: {user.username}
      </Box>
    </Alert>
  );
}
