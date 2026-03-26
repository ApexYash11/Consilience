"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getUsage, login as loginRequest, register as registerRequest, validateSession, type UsageResponse } from "@/lib/auth";
import { ApiError } from "@/lib/api";

const STORAGE_KEY = "consilience_access_token";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  token: string | null;
  usage: UsageResponse | null;
  error: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshUsage: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function getFriendlyError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }

    return window.localStorage.getItem(STORAGE_KEY);
  });
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadUsage = useCallback(async (activeToken: string) => {
    const summary = await getUsage(activeToken);
    setUsage(summary);
  }, []);

  useEffect(() => {
    async function initAuth() {
      if (!token) {
        setStatus("unauthenticated");
        return;
      }
      try {
        const isValid = await validateSession(token);
        if (isValid) {
          setStatus("authenticated");
          await loadUsage(token);
        } else {
          window.localStorage.removeItem(STORAGE_KEY);
          setToken(null);
          setStatus("unauthenticated");
        }
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
        setToken(null);
        setStatus("unauthenticated");
      }
    }
    initAuth();
  }, [token, loadUsage]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const result = await loginRequest({ email, password });
    
    // CRITICAL: Store token IMMEDIATELY to unblock auth state
    // This allows redirect to happen even if usage loading fails
    window.localStorage.setItem(STORAGE_KEY, result.access_token);
    setToken(result.access_token);
    setStatus("authenticated");
    
    // Load usage in the background without blocking
    // If this fails, user is still authenticated with basic token
    loadUsage(result.access_token).catch((err) => {
      console.error("[Auth] Failed to load usage data:", err);
      // Still authenticated, just without usage data
    });
  }, [loadUsage]);

  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      setError(null);
      await registerRequest({ email, password, full_name: fullName });
      await login(email, password);
    },
    [login]
  );

  const logout = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setUsage(null);
    setError(null);
    setStatus("unauthenticated");
  }, []);

  const refreshUsage = useCallback(async () => {
    if (!token) {
      return;
    }

    try {
      setError(null);
      await loadUsage(token);
    } catch (err) {
      const message = getFriendlyError(err);
      setError(message);
    }
  }, [loadUsage, token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      token,
      usage,
      error,
      isAuthenticated: status === "authenticated",
      login: async (email: string, password: string) => {
        try {
          await login(email, password);
        } catch (err) {
          setError(getFriendlyError(err));
          throw err;
        }
      },
      register: async (email: string, password: string, fullName?: string) => {
        try {
          await register(email, password, fullName);
        } catch (err) {
          setError(getFriendlyError(err));
          throw err;
        }
      },
      logout,
      refreshUsage,
    }),
    [error, login, logout, refreshUsage, register, status, token, usage]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
