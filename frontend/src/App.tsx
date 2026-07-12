import {
  BulbFilled, BulbOutlined, DashboardOutlined, FileTextOutlined, FundOutlined,
  MenuOutlined, PieChartOutlined, RadarChartOutlined, SettingOutlined, UserOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Dropdown, Grid, Input, Layout, Menu, Modal, theme, Typography, message } from "antd";
import { useState } from "react";
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { errMsg } from "./api/client";
import { useAuthConfig, useSetNickname, useVisitorMe } from "./api/hooks";
import { useAuth } from "./auth";
import FeibiWidget from "./components/FeibiWidget";
import Admin from "./pages/Admin";
import VisitorLogin from "./pages/VisitorLogin";
import Dashboard from "./pages/Dashboard";
import Posts from "./pages/Posts";
import Screener from "./pages/Screener";
import SectorRank from "./pages/SectorRank";
import StockDetail from "./pages/StockDetail";
import Summary from "./pages/Summary";
import { useThemeMode } from "./theme";
import { useVisitorAuth } from "./visitorAuth";

const { Sider, Content, Header } = Layout;
const { useBreakpoint } = Grid;

const NAV = [
  { key: "/", icon: <DashboardOutlined />, label: "看板" },
  { key: "/posts", icon: <FileTextOutlined />, label: "帖子流" },
  { key: "/summary", icon: <FundOutlined />, label: "AI 总结" },
  { key: "/screener", icon: <RadarChartOutlined />, label: "选股" },
  { key: "/sectors", icon: <PieChartOutlined />, label: "板块行情" },
];

function RequireAdmin({ children }: { children: JSX.Element }) {
  const { loggedIn } = useAuth();
  const loc = useLocation();
  return loggedIn ? children : <Navigate to="/admin/login" replace state={{ from: loc.pathname }} />;
}

// authConfig 没读到之前不放行子页面：否则页面组件会先发只读请求，命中开着的登录墙拿 401，
// 界面卡在半失败状态，直到 authConfig 到位才跳转登录页，体验上像"卡住"。
function RequireVisitorOrAnon({ children }: { children: JSX.Element }) {
  const { data: authConfig, isLoading } = useAuthConfig();
  const { loggedIn: adminLoggedIn } = useAuth();
  const { loggedIn: visitorLoggedIn } = useVisitorAuth();
  const loc = useLocation();
  if (isLoading) return null;
  if (authConfig?.require_login && !adminLoggedIn && !visitorLoggedIn) {
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }
  return children;
}

// 访客登录后在 header 显示账号信息 + 改昵称 + 退出登录；未登录（匿名开关关闭时）不渲染。
function VisitorMenu() {
  const { loggedIn, logout } = useVisitorAuth();
  const { data: me } = useVisitorMe(loggedIn);
  const setNickname = useSetNickname();
  const nav = useNavigate();
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState("");
  if (!loggedIn) return null;
  const label =
    me?.login_type === "phone" ? me.phone
    : me?.login_type === "email" ? (me.nickname || me.email)
    : (me?.nickname || "微信用户");

  const saveNickname = () => {
    const v = draft.trim();
    if (!v) { message.warning("昵称不能为空"); return; }
    setNickname.mutate(v, {
      onSuccess: () => { message.success("已修改"); setEditOpen(false); },
      onError: (e) => message.error(errMsg(e, "修改失败")),
    });
  };

  return (
    <>
      <Dropdown
        menu={{
          items: [
            { key: "info", label: label ?? "账号", disabled: true },
            { type: "divider" },
            // 手机号本身就是账号标识不用改昵称；微信/邮箱账号可以自己起个昵称。
            ...(me?.login_type !== "phone" ? [{ key: "edit-nickname", label: "修改昵称" }] : []),
            { key: "logout", label: "退出登录" },
          ],
          onClick: ({ key }) => {
            if (key === "logout") {
              logout();
              nav("/login", { replace: true });
            } else if (key === "edit-nickname") {
              setDraft(me?.nickname || "");
              setEditOpen(true);
            }
          },
        }}
      >
        <Button type="text" icon={<UserOutlined />}>{label ?? "账号"}</Button>
      </Dropdown>
      <Modal
        title="修改昵称"
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={saveNickname}
        confirmLoading={setNickname.isPending}
      >
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={20} placeholder="请输入昵称" />
      </Modal>
    </>
  );
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

  // Menu 自带的 dark/light theme 是固定色板（暗色是那种深蓝 #001529），跟 Content/Header
  // 用 colorBgContainer 算出来的近黑背景不是一套色系。把 Menu 背景设透明，让它显出外层容器
  // 背景，外层（Sider/Drawer）再显式接管成 colorBgContainer，整站背景色才能统一。
  // 管理后台入口只在管理员已登录时才出现在导航里，避免访客看到一个点了也进不去的菜单项。
  const navItems = loggedIn ? [...NAV, { key: "/admin", icon: <SettingOutlined />, label: "管理后台" }] : NAV;
  const navMenu = (
    <Menu
      theme={navTheme}
      mode="inline"
      selectedKeys={[selected === "/" ? "/" : selected]}
      items={navItems}
      onClick={(e) => { nav(e.key); setDrawerOpen(false); }}
      style={{ background: "transparent" }}
    />
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {!isMobile && (
        <Sider
          theme={navTheme}
          width={200}
          style={{ background: token.colorBgContainer, borderRight: `1px solid ${token.colorBorderSecondary}` }}
        >
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
          <VisitorMenu />
        </Header>
        <Content style={{ padding: isMobile ? 12 : 20, overflow: "auto" }}>
          <Routes>
            <Route path="/login" element={<VisitorLogin />} />
            {/* 管理员登录/后台不受访客登录墙控制：管理员要能随时进来，且不出现在访客可见的导航里 */}
            <Route path="/admin/login" element={<Admin login />} />
            <Route path="/admin" element={<RequireAdmin><Admin /></RequireAdmin>} />
            <Route element={<RequireVisitorOrAnon><Outlet /></RequireVisitorOrAnon>}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/posts" element={<Posts />} />
              <Route path="/summary" element={<Summary />} />
              <Route path="/screener" element={<Screener />} />
              <Route path="/sectors" element={<SectorRank />} />
              <Route path="/stock/:code" element={<StockDetail />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
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
