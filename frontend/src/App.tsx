import {
  BulbFilled, BulbOutlined, DashboardOutlined, FileTextOutlined, FundOutlined,
  MenuOutlined, PieChartOutlined, RadarChartOutlined, SettingOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Grid, Layout, Menu, theme, Typography } from "antd";
import { useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "./auth";
import FeibiWidget from "./components/FeibiWidget";
import Admin from "./pages/Admin";
import Dashboard from "./pages/Dashboard";
import Posts from "./pages/Posts";
import Screener from "./pages/Screener";
import SectorRank from "./pages/SectorRank";
import StockDetail from "./pages/StockDetail";
import Summary from "./pages/Summary";
import { useThemeMode } from "./theme";

const { Sider, Content, Header } = Layout;
const { useBreakpoint } = Grid;

const NAV = [
  { key: "/", icon: <DashboardOutlined />, label: "看板" },
  { key: "/posts", icon: <FileTextOutlined />, label: "帖子流" },
  { key: "/summary", icon: <FundOutlined />, label: "AI 总结" },
  { key: "/screener", icon: <RadarChartOutlined />, label: "选股" },
  { key: "/sectors", icon: <PieChartOutlined />, label: "板块行情" },
  { key: "/admin", icon: <SettingOutlined />, label: "管理后台" },
];

function RequireAdmin({ children }: { children: JSX.Element }) {
  const { loggedIn } = useAuth();
  const loc = useLocation();
  return loggedIn ? children : <Navigate to="/admin/login" replace state={{ from: loc.pathname }} />;
}

function Brand() {
  return (
    <div style={{ padding: "18px 16px" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        雪球看板
      </Typography.Title>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>Xueqiu Insight</Typography.Text>
    </div>
  );
}

export default function App() {
  const nav = useNavigate();
  const loc = useLocation();
  const { loggedIn } = useAuth();
  const selected = "/" + (loc.pathname.split("/")[1] || "");
  const screens = useBreakpoint();
  const isMobile = !screens.lg;
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { mode, toggle } = useThemeMode();
  const navTheme = mode === "dark" ? "dark" : "light";
  // Layout.Header 的默认背景是固定的深色 token（不随亮暗算法变），得自己接管颜色
  const { token } = theme.useToken();

  const navMenu = (
    <Menu
      theme={navTheme}
      mode="inline"
      selectedKeys={[selected === "/" ? "/" : selected]}
      items={NAV}
      onClick={(e) => { nav(e.key); setDrawerOpen(false); }}
    />
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {!isMobile && (
        <Sider theme={navTheme} width={200}>
          <Brand />
          {navMenu}
        </Sider>
      )}
      <Layout>
        <Header className="app-header" style={{ background: token.colorBgContainer, borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
          {isMobile && (
            <Button type="text" icon={<MenuOutlined />} onClick={() => setDrawerOpen(true)} />
          )}
          <Typography.Text strong className="app-header-title">雪球看板 · Xueqiu Insight</Typography.Text>
          <Button
            type="text"
            icon={mode === "dark" ? <BulbOutlined /> : <BulbFilled />}
            onClick={toggle}
            title={mode === "dark" ? "切换为浅色主题" : "切换为深色主题"}
          />
        </Header>
        <Content style={{ padding: isMobile ? 12 : 20, overflow: "auto" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/posts" element={<Posts />} />
            <Route path="/summary" element={<Summary />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/sectors" element={<SectorRank />} />
            <Route path="/stock/:code" element={<StockDetail />} />
            <Route path="/admin/login" element={<Admin login />} />
            <Route path="/admin" element={<RequireAdmin><Admin /></RequireAdmin>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
      <Drawer
        placement="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={220}
        styles={{ body: { padding: 0 } }}
        closeIcon={null}
        title={<Brand />}
      >
        {navMenu}
      </Drawer>
      {loggedIn && <FeibiWidget />}
    </Layout>
  );
}
