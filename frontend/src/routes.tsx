import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import type { Role, User } from "./api";
import { useAuth } from "./auth";
import { Loading } from "./ui";

export function homeFor(user: User): string {
  return user.role === "system_admin" ? "/admin" : "/overview";
}

// Hiding screens is convenience only; the server refuses every request a role may not make.
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, checking } = useAuth();
  if (checking) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />;
  return <>{children}</>;
}

export function Home() {
  const { user, checking } = useAuth();
  if (checking) return <Loading />;
  return <Navigate to={user ? homeFor(user) : "/login"} replace />;
}
