// 亮/暗主题状态：优先读本地存储，否则跟随系统偏好；切换后写入 <html data-theme> 供 CSS 变量使用
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type ThemeMode = "light" | "dark";
const STORAGE_KEY = "theme-mode";

function getInitialMode(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const ThemeModeContext = createContext<{ mode: ThemeMode; toggle: () => void }>({
  mode: "light",
  toggle: () => {},
});

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(getInitialMode);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
    localStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  const value = useMemo(
    () => ({ mode, toggle: () => setMode((m) => (m === "light" ? "dark" : "light")) }),
    [mode],
  );

  return <ThemeModeContext.Provider value={value}>{children}</ThemeModeContext.Provider>;
}

export function useThemeMode() {
  return useContext(ThemeModeContext);
}
