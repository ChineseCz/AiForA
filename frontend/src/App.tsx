import {
  DashboardOutlined, FileTextOutlined, FundOutlined, RadarChartOutlined, SettingOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "./auth";
import Admin from "./pages/Admin";
import Dashboard from "./pages/Dashboard";
import Posts from "./pages/Posts";
import Screener from "./pages/Screener";
import StockDetail from "./pages/StockDetail";
import Summary from "./pages/Summary";

const { Sider, Content } = Layout;

const NAV = [
  { key: "/", icon: <DashboardOutlined />, label: "看板" },
  { key: "/posts", icon: <FileTextOutlined />, label: "帖子流" },
  { key: "/summary", icon: <FundOutlined />, label: "AI 总结" },
  { key: "/screener", icon: <RadarChartOutlined />, label: "选股" },
  { key: "/admin", icon: <SettingOutlined />, label: "管理后台" },
];

function RequireAdmin({ children }: { children: JSX.Element }) {
  const { loggedIn } = useAuth();
  const loc = useLocation();
  return loggedIn ? children : <Navigate to="/admin/login" replace state={{ from: loc.pathname }} />;
}

export default function App() {
  const nav = useNavigate();
  const loc = useLocation();
  const selected = "/" + (loc.pathname.split("/")[1] || "");

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="dark" width={200} breakpoint="lg" collapsedWidth={0}>
        <div style={{ padding: "18px 16px", color: "#fff" }}>
          <Typography.Title level={4} style={{ color: "#fff", margin: 0 }}>
            雪球看板
          </Typography.Title>
          <Typography.Text style={{ color: "#8ea0b5", fontSize: 12 }}>Xueqiu Insight</Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected === "/" ? "/" : selected]}
          items={NAV}
          onClick={(e) => nav(e.key)}
        />
      </Sider>
      <Layout>
        <Content style={{ padding: 20, overflow: "auto" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/posts" element={<Posts />} />
            <Route path="/summary" element={<Summary />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/stock/:code" element={<StockDetail />} />
            <Route path="/admin/login" element={<Admin login />} />
            <Route path="/admin" element={<RequireAdmin><Admin /></RequireAdmin>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
