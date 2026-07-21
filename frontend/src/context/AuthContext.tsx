// src/context/AuthContext.tsx
import React, { createContext, useContext, useState, ReactNode } from "react";

const STORAGE_KEY = "ee_user_email";

interface AuthContextProps {
  isAuthenticated: boolean;
  userEmail: string | null;
  login: (email: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextProps | undefined>(undefined);

// Resolve the initial session synchronously, BEFORE any route renders.
// When the backend OAuth callback redirects to "/?auth=success&email=...",
// we consume those params here, persist the email, and strip the query from
// the URL — so ProtectedRoute sees an authenticated user on the first render
// and never bounces back to /login.
const resolveInitialEmail = (): string | null => {
  const params = new URLSearchParams(window.location.search);
  if (params.get("auth") === "success") {
    const email = params.get("email");
    if (email) {
      localStorage.setItem(STORAGE_KEY, email);
    }
    params.delete("auth");
    params.delete("email");
    const qs = params.toString();
    const clean = window.location.pathname + (qs ? `?${qs}` : "");
    window.history.replaceState({}, "", clean);
    if (email) return email;
  }
  return localStorage.getItem(STORAGE_KEY);
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [userEmail, setUserEmail] = useState<string | null>(resolveInitialEmail);

  const login = (email: string) => {
    localStorage.setItem(STORAGE_KEY, email);
    setUserEmail(email);
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setUserEmail(null);
  };

  return (
    <AuthContext.Provider
      value={{ isAuthenticated: !!userEmail, userEmail, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextProps => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
