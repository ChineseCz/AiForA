import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 开发代理：/api 和 /health 转发到后端（容器 API 发布在宿主 8088）。
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8088", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8088", changeOrigin: true },
    },
  },
  build: {
    // 拆分大依赖为独立 vendor chunk，避免单个巨包（echarts/antd 体积大）
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts", "echarts-for-react"],
          antd: ["antd", "@ant-design/icons"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
