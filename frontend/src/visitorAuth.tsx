// 访客登录态：token 存在即视为已登录（后端 require_visitor 兜底校验有效性）。
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { clearVisitorToken, getVisitorToken, setVisitorToken } from "@/api/client";

interface VisitorAuthCtx {
  loggedIn: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const Ctx = createContext<VisitorAuthCtx>({ loggedIn: false, login: () => {}, logout: () => {} });

export function VisitorAuthProvider({ children }: { children: ReactNode }) {
  const [loggedIn, setLoggedIn] = useState(!!getVisitorToken());

  useEffect(() => {
    const onUnauth = () => setLoggedIn(false);
    window.addEventListener("natapp-visitor-unauthorized", onUnauth);
    return () => window.removeEventListener("natapp-visitor-unauthorized", onUnauth);
  }, []);

  const login = (token: string) => {
    setVisitorToken(token);
    setLoggedIn(true);
  };
  const logout = () => {
    clearVisitorToken();
    setLoggedIn(false);
  };

  return <Ctx.Provider value={{ loggedIn, login, logout }}>{children}</Ctx.Provider>;
}

export const useVisitorAuth = () => useContext(Ctx);
