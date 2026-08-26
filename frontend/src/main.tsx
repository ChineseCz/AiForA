import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider, theme as antdTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Capacitor } from "@capacitor/core";

import App from "./App";
import { AuthProvider } from "./auth";
import { ThemeModeProvider, useThemeMode } from "./theme";
import { VisitorAuthProvider } from "./visitorAuth";
import "./index.css";

if (Capacitor.isNativePlatform()) {
  document.documentElement.classList.add("capacitor-app");
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
});

function ThemedRoot() {
  const { mode } = useThemeMode();
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: mode === "dark" ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: { colorPrimary: "#1668dc", borderRadius: 8 },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <VisitorAuthProvider>
            <AntApp>
              <BrowserRouter>
                <App />
              </BrowserRouter>
            </AntApp>
          </VisitorAuthProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ThemedRoot />
    </ThemeModeProvider>
  </React.StrictMode>,
);
