import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as client from "./api";
import type { User } from "./api";

interface AuthState {
  user: User | null;
  checking: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signInDemo: (username: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    let active = true;
    client
      .refreshSession()
      .catch(() => null)
      .then((u) => {
        if (active) {
          setUser(u);
          setChecking(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  // Every cached answer belongs to the account that fetched it; a new account must never see the last one's.
  const start = useCallback(
    (next: User) => {
      queryClient.clear();
      setUser(next);
    },
    [queryClient],
  );

  const signIn = useCallback(
    async (username: string, password: string) => start(await client.login(username, password)),
    [start],
  );

  const signInDemo = useCallback(async (username: string) => start(await client.demoLogin(username)), [start]);

  const signOut = useCallback(async () => {
    try {
      await client.logout();
    } finally {
      queryClient.clear();
      setUser(null);
    }
  }, [queryClient]);

  return <AuthContext.Provider value={{ user, checking, signIn, signInDemo, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used inside AuthProvider");
  return state;
}
