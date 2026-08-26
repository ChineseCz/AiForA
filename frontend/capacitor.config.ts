import type { CapacitorConfig } from "@capacitor/cli";

// Set CAP_SERVER_URL before syncing, for example: http://1.2.3.4/
const serverUrl = process.env.CAP_SERVER_URL || "http://124.222.169.60/";

const config: CapacitorConfig = {
  appId: "com.xueqiu.insight",
  appName: "雪球看板",
  webDir: "dist",
  server: {
    url: serverUrl,
    cleartext: true,
    androidScheme: "http",
  },
};

export default config;
