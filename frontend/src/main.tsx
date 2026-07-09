import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./auth";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#1668dc", borderRadius: 8 } }}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AntApp>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </AntApp>
        </AuthProvider>
      </QueryClientProvider>
    </ConfigProvider>
  </React.StrictMode>,
);
