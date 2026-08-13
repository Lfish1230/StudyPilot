import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  api,
  clearAccessToken,
  getAccessToken,
  setAccessToken,
  setUnauthorizedHandler,
} from "../../api/client";
import type { AuthCredentials, TokenResponse, User } from "../../api/contracts";

interface AuthContextValue {
  user: User | null;
  isChecking: boolean;
  login(credentials: AuthCredentials): Promise<void>;
  register(credentials: AuthCredentials): Promise<void>;
  logout(): void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isChecking, setIsChecking] = useState(() => getAccessToken() !== null);

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(undefined);
  }, [logout]);

  useEffect(() => {
    if (!getAccessToken()) {
      setIsChecking(false);
      return;
    }
    let active = true;
    api
      .request<User>("/auth/me")
      .then((verifiedUser) => {
        if (active) setUser(verifiedUser);
      })
      .catch(() => {
        if (active) logout();
      })
      .finally(() => {
        if (active) setIsChecking(false);
      });
    return () => {
      active = false;
    };
  }, [logout]);

  const login = useCallback(async (credentials: AuthCredentials) => {
    const token = await api.request<TokenResponse>("/auth/login", {
      method: "POST",
      body: credentials,
    });
    setAccessToken(token.access_token);
    try {
      const currentUser = await api.request<User>("/auth/me");
      setUser(currentUser);
    } catch (error) {
      clearAccessToken();
      throw error;
    }
  }, []);

  const register = useCallback(async (credentials: AuthCredentials) => {
    await api.request<User>("/auth/register", {
      method: "POST",
      body: credentials,
    });
  }, []);

  const value = useMemo(
    () => ({ user, isChecking, login, register, logout }),
    [isChecking, login, logout, register, user],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
