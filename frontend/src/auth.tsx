import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as client from "./api";
import type { User } from "./api";

interface AuthState {
  user: User | null;
  checking: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

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

  const signIn = useCallback(async (username: string, password: string) => {
    setUser(await client.login(username, password));
  }, []);

  const signOut = useCallback(async () => {
    await client.logout();
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, checking, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used inside AuthProvider");
  return state;
}
