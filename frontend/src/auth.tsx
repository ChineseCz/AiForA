// 简单的管理员登录态：token 存在即视为已登录（后端 require_admin 兜底校验有效性）。
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { clearToken, getToken, setToken } from "@/api/client";

interface AuthCtx {
  loggedIn: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>({ loggedIn: false, login: () => {}, logout: () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loggedIn, setLoggedIn] = useState(!!getToken());

  useEffect(() => {
    const onUnauth = () => setLoggedIn(false);
    window.addEventListener("natapp-unauthorized", onUnauth);
    return () => window.removeEventListener("natapp-unauthorized", onUnauth);
  }, []);

  const login = (token: string) => {
    setToken(token);
    setLoggedIn(true);
  };
  const logout = () => {
    clearToken();
    setLoggedIn(false);
  };

  return <Ctx.Provider value={{ loggedIn, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
