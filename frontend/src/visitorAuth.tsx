// 访客登录态：token 存在即视为已登录（后端 require_visitor 兜底校验有效性）。
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { clearVisitorToken, getVisitorToken, setVisitorToken } from "@/api/client";

const GUEST_FLAG_KEY = "natapp_visitor_is_guest";

interface VisitorAuthCtx {
  loggedIn: boolean;
  isGuest: boolean;
  login: (token: string, guest?: boolean) => void;
  logout: () => void;
}

const Ctx = createContext<VisitorAuthCtx>({ loggedIn: false, isGuest: false, login: () => {}, logout: () => {} });

export function VisitorAuthProvider({ children }: { children: ReactNode }) {
  const [loggedIn, setLoggedIn] = useState(!!getVisitorToken());
  const [isGuest, setIsGuest] = useState(localStorage.getItem(GUEST_FLAG_KEY) === "1");

  useEffect(() => {
    const onUnauth = () => {
      setLoggedIn(false);
      setIsGuest(false);
      localStorage.removeItem(GUEST_FLAG_KEY);
    };
    window.addEventListener("natapp-visitor-unauthorized", onUnauth);
    return () => window.removeEventListener("natapp-visitor-unauthorized", onUnauth);
  }, []);

  const login = (token: string, guest = false) => {
    setVisitorToken(token);
    if (guest) localStorage.setItem(GUEST_FLAG_KEY, "1");
    else localStorage.removeItem(GUEST_FLAG_KEY);
    setLoggedIn(true);
    setIsGuest(guest);
  };
  const logout = () => {
    clearVisitorToken();
    localStorage.removeItem(GUEST_FLAG_KEY);
    setLoggedIn(false);
    setIsGuest(false);
  };

  return <Ctx.Provider value={{ loggedIn, isGuest, login, logout }}>{children}</Ctx.Provider>;
}

export const useVisitorAuth = () => useContext(Ctx);
