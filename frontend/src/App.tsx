import {
  BulbFilled, BulbOutlined, DashboardOutlined, MessageOutlined,
  MoreOutlined, RadarChartOutlined, SettingOutlined, StarOutlined, UserOutlined,
} from "@ant-design/icons";
import { Button, Dropdown, Input, Layout, Menu, Modal, theme, Typography, message } from "antd";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { api, errMsg } from "./api/client";
import { useSetNickname, useVisitorMe } from "./api/hooks";
import { useAuth } from "./auth";
import FeibiWidget from "./components/FeibiWidget";
import NetworkStatus from "./components/NetworkStatus";
import { useIsMobile } from "./hooks/useIsMobile";
import { useEdgeBackGesture } from "./hooks/useEdgeBackGesture";
import { useThemeMode } from "./theme";
import { useVisitorAuth } from "./visitorAuth";

const Admin = lazy(() => import("./pages/Admin"));
const Feed = lazy(() => import("./pages/Feed"));
const VisitorLogin = lazy(() => import("./pages/VisitorLogin"));
const My = lazy(() => import("./pages/My"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Screener = lazy(() => import("./pages/Screener"));
const StockDetail = lazy(() => import("./pages/StockDetail"));

const { Sider, Content, Header } = Layout;

const NAV = [
  { key: "/", icon: <DashboardOutlined />, label: "看板" },
  { key: "/feed", icon: <MessageOutlined />, label: "大V动态" },
  { key: "/screener", icon: <RadarChartOutlined />, label: "选股" },
  { key: "/my", icon: <StarOutlined />, label: "我的" },
];

function RequireAdmin({ children }: { children: JSX.Element }) {
  const { loggedIn } = useAuth();
  const loc = useLocation();
  return loggedIn ? children : <Navigate to="/login" replace state={{ from: loc.pathname }} />;
}

// 始终要求登录（后端 require_login 永远为 true）；token 存在即放行，后端校验有效性。
function RequireVisitorOrAnon({ children }: { children: JSX.Element }) {
  const { loggedIn: adminLoggedIn } = useAuth();
  const { loggedIn: visitorLoggedIn } = useVisitorAuth();
  const loc = useLocation();
  if (!adminLoggedIn && !visitorLoggedIn) {
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }
  return children;
}

// 访客登录后在 header 显示账号信息 + 改昵称 + 退出登录；游客（isGuest）只显示简单退出入口。
function VisitorMenu() {
  const { loggedIn, isGuest, logout, login: visitorLogin } = useVisitorAuth();
  const { logout: adminLogout, login: adminLogin } = useAuth();
  const { data: me } = useVisitorMe(loggedIn && !isGuest);
  const setNickname = useSetNickname();
  const nav = useNavigate();
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [emailOpen, setEmailOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [captcha, setCaptcha] = useState<{ challenge_id: string; image: string } | null>(null);
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [sendingCode, setSendingCode] = useState(false);
  const [changingEmail, setChangingEmail] = useState(false);
  const [bindOpen, setBindOpen] = useState(false);
  const [bindEmail, setBindEmail] = useState("");
  const [bindCode, setBindCode] = useState("");
  const [bindAnswer, setBindAnswer] = useState("");
  const [bindCaptcha, setBindCaptcha] = useState<{ challenge_id: string; image: string } | null>(null);
  const [bindSending, setBindSending] = useState(false);
  const [bindConfirming, setBindConfirming] = useState(false);
  if (!loggedIn) return null;

  if (isGuest) {
    return (
      <Dropdown
        menu={{
          items: [
            { key: "info", label: "游客模式（只读）", disabled: true },
            { type: "divider" },
            { key: "logout", label: "退出并登录账号" },
          ],
          onClick: ({ key }) => {
            if (key === "logout") { logout(); adminLogout(); nav("/login", { replace: true }); }
          },
        }}
      >
        <Button type="text" icon={<UserOutlined />}>游客</Button>
      </Dropdown>
    );
  }

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

  const loadEmailCaptcha = () => {
    setCaptchaAnswer("");
    api.get<{ challenge_id: string; image: string }>("/api/user/email/change-captcha")
      .then((r) => setCaptcha(r.data))
      .catch((e) => message.error(errMsg(e, "加载验证码失败")));
  };

  const openEmailChange = () => {
    setNewEmail(""); setEmailCode(""); setEmailOpen(true); loadEmailCaptcha();
  };

  const sendEmailCode = () => {
    const email = newEmail.trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { message.warning("请输入正确的新邮箱"); return; }
    setSendingCode(true);
    api.post("/api/user/email/change-send-code", { email, captcha_id: captcha?.challenge_id || "", captcha_answer: captchaAnswer.trim() })
      .then(() => { message.success("验证码已发送到新邮箱"); setCaptchaAnswer(""); })
      .catch((e) => message.error(errMsg(e, "发送失败")))
      .finally(() => { setSendingCode(false); loadEmailCaptcha(); });
  };

  const confirmEmailChange = () => {
    const email = newEmail.trim().toLowerCase();
    if (!emailCode.trim()) { message.warning("请输入邮箱验证码"); return; }
    setChangingEmail(true);
    api.post<{ email: string; access_token: string; admin_token?: string }>("/api/user/email/change", { email, code: emailCode.trim() })
      .then((r) => {
        visitorLogin(r.data.access_token);
        if (r.data.admin_token) adminLogin(r.data.admin_token);
        message.success("邮箱已更换，登录和邮件提醒已同步更新");
        setEmailOpen(false);
        window.setTimeout(() => window.location.reload(), 400);
      })
      .catch((e) => message.error(errMsg(e, "更换失败")))
      .finally(() => setChangingEmail(false));
  };

  const loadBindCaptcha = () => api.get<{ challenge_id: string; image: string }>("/api/user/email/bind-captcha").then((r) => setBindCaptcha(r.data));
  const openBindEmail = () => { setBindOpen(true); setBindEmail(""); setBindCode(""); setBindAnswer(""); loadBindCaptcha(); };
  const sendBindEmailCode = () => {
    setBindSending(true);
    api.post("/api/user/email/bind-send-code", { email: bindEmail.trim().toLowerCase(), captcha_id: bindCaptcha?.challenge_id || "", captcha_answer: bindAnswer.trim() })
      .then(() => message.success("验证码已发送到邮箱")).catch((e) => message.error(errMsg(e, "发送失败")))
      .finally(() => { setBindSending(false); loadBindCaptcha(); });
  };
  const confirmBindEmail = () => {
    setBindConfirming(true);
    api.post("/api/user/email/bind", { email: bindEmail.trim().toLowerCase(), code: bindCode.trim() })
      .then(() => { message.success("邮箱绑定成功"); setBindOpen(false); window.location.reload(); })
      .catch((e) => message.error(errMsg(e, "绑定失败"))).finally(() => setBindConfirming(false));
  };

  return (
    <>
      <Dropdown
        menu={{
          items: [
            { key: "info", label: label ?? "账号", disabled: true },
            { type: "divider" },
            ...(me?.login_type !== "phone" ? [{ key: "edit-nickname", label: "修改昵称" }] : []),
            ...(me?.email ? [{ key: "change-email", label: "更换邮箱" }] : [{ key: "bind-email", label: "绑定邮箱" }]),
            { key: "logout", label: "退出登录" },
          ],
          onClick: ({ key }) => {
            if (key === "logout") {
              logout();
              adminLogout();
              nav("/login", { replace: true });
            } else if (key === "edit-nickname") {
              setDraft(me?.nickname || "");
              setEditOpen(true);
            } else if (key === "change-email") {
              openEmailChange();
            } else if (key === "bind-email") {
              openBindEmail();
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
      <Modal title="更换邮箱" open={emailOpen} onCancel={() => setEmailOpen(false)} onOk={confirmEmailChange} confirmLoading={changingEmail} okText="确认更换">
        <Typography.Paragraph type="secondary">新邮箱将用于邮箱登录和买卖信号邮件提醒。</Typography.Paragraph>
        <Input value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="请输入新邮箱" autoComplete="email" style={{ marginBottom: 10 }} />
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          {captcha?.image && <img src={captcha.image} alt="图片验证码" style={{ width: 120, height: 40, border: "1px solid #d9d9d9", borderRadius: 4 }} />}
          <Input value={captchaAnswer} onChange={(e) => setCaptchaAnswer(e.target.value)} placeholder="图片算式答案" inputMode="numeric" maxLength={2} />
          <Button onClick={loadEmailCaptcha}>换一张</Button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Input value={emailCode} onChange={(e) => setEmailCode(e.target.value)} placeholder="新邮箱验证码" maxLength={6} />
          <Button onClick={sendEmailCode} loading={sendingCode}>获取验证码</Button>
        </div>
      </Modal>
      <Modal title="绑定邮箱" open={bindOpen} onCancel={() => setBindOpen(false)} onOk={confirmBindEmail} confirmLoading={bindConfirming} okText="确认绑定">
        <Input value={bindEmail} onChange={(e) => setBindEmail(e.target.value)} placeholder="请输入邮箱" style={{ marginBottom: 10 }} />
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          {bindCaptcha?.image && <img src={bindCaptcha.image} alt="图片验证码" style={{ width: 120, height: 40, border: "1px solid #d9d9d9", borderRadius: 4 }} />}
          <Input value={bindAnswer} onChange={(e) => setBindAnswer(e.target.value)} placeholder="图片答案" inputMode="numeric" maxLength={2} />
          <Button onClick={loadBindCaptcha}>换一张</Button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Input value={bindCode} onChange={(e) => setBindCode(e.target.value)} placeholder="邮箱验证码" maxLength={6} />
          <Button onClick={sendBindEmailCode} loading={bindSending}>获取验证码</Button>
        </div>
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

// 底部Tab栏（仿微信/支付宝）：只放常用的5个只读页面，管理后台/主题切换/账号挪进 header 的「更多」菜单，
// 栏位有限放不下这几个次要入口。
function BottomTabBar({ selected, onSelect }: { selected: string; onSelect: (key: string) => void }) {
  return (
    <div className="bottom-tab-bar">
      {NAV.map((item) => (
        <div
          key={item.key}
          className={`bottom-tab-item${selected === item.key ? " active" : ""}`}
          onClick={() => onSelect(item.key)}
        >
          {item.icon}
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const nav = useNavigate();
  const loc = useLocation();
  const { loggedIn } = useAuth();
  const selected = "/" + (loc.pathname.split("/")[1] || "");
  const isMobile = useIsMobile();
  const { mode, toggle } = useThemeMode();
  const navTheme = mode === "dark" ? "dark" : "light";
  // Layout.Header 的默认背景是固定的深色 token（不随亮暗算法变），得自己接管颜色
  const { token } = theme.useToken();
  const canGoBack = (window.history.state?.idx ?? 0) > 0;
  const exitConfirmUntil = useRef(0);
  const exitConfirmTimer = useRef<number | undefined>(undefined);
  const goBack = useCallback(() => {
    // 首页作为应用根页面处理：不回到登录页或之前的残留路由，交给双击返回退出逻辑。
    if (loc.pathname !== "/" && canGoBack) {
      nav(-1);
      return true;
    } else if (loc.pathname.startsWith("/stock/")) {
      nav("/screener");
      return true;
    }
    return false;
  }, [canGoBack, loc.pathname, nav]);

  const handleBack = useCallback(() => {
    if (goBack()) return true;
    if (Capacitor.isNativePlatform()) {
      const now = Date.now();
      if (now <= exitConfirmUntil.current) {
        void CapacitorApp.exitApp();
      } else {
        exitConfirmUntil.current = now + 2000;
        message.info("再滑动一次退出应用");
        window.clearTimeout(exitConfirmTimer.current);
        exitConfirmTimer.current = window.setTimeout(() => {
          exitConfirmUntil.current = 0;
        }, 2000);
      }
      return true;
    }
    return false;
  }, [goBack]);

  useEffect(() => () => window.clearTimeout(exitConfirmTimer.current), []);

  useEdgeBackGesture({
    enabled: isMobile && Capacitor.isNativePlatform(),
    onBack: handleBack,
  });

  // Menu 自带的 dark/light theme 是固定色板（暗色是那种深蓝 #001529），跟 Content/Header
  // 用 colorBgContainer 算出来的近黑背景不是一套色系。把 Menu 背景设透明，让它显出外层容器
  // 背景，外层（Sider）再显式接管成 colorBgContainer，整站背景色才能统一。
  // 管理后台入口只在管理员已登录时才出现在导航里，避免访客看到一个点了也进不去的菜单项。
  const navItems = loggedIn ? [...NAV, { key: "/admin", icon: <SettingOutlined />, label: "管理后台" }] : NAV;
  const navMenu = (
    <Menu
      theme={navTheme}
      mode="inline"
      selectedKeys={[selected === "/" ? "/" : selected]}
      items={navItems}
      onClick={(e) => nav(e.key)}
      style={{ background: "transparent" }}
    />
  );

  // 手机端底部Tab栏放不下管理后台/主题切换这两个次要入口，收进 header 右侧的「更多」下拉里。
  const moreMenu = (
    <Dropdown
      menu={{
        items: [
          { key: "theme", icon: mode === "dark" ? <BulbOutlined /> : <BulbFilled />, label: mode === "dark" ? "切换为浅色主题" : "切换为深色主题" },
          ...(loggedIn ? [{ key: "/admin", icon: <SettingOutlined />, label: "管理后台" }] : []),
        ],
        onClick: ({ key }) => { if (key === "theme") toggle(); else nav(key); },
      }}
    >
      <Button type="text" icon={<MoreOutlined />} />
    </Dropdown>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <NetworkStatus />
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
          <Typography.Text strong className="app-header-title">雪球看板 · Xueqiu Insight</Typography.Text>
          {isMobile ? moreMenu : (
            <Button
              type="text"
              icon={mode === "dark" ? <BulbOutlined /> : <BulbFilled />}
              onClick={toggle}
              title={mode === "dark" ? "切换为浅色主题" : "切换为深色主题"}
            />
          )}
          <VisitorMenu />
        </Header>
        <Content style={{
          padding: isMobile ? 12 : 20,
          paddingBottom: isMobile ? "calc(var(--tab-bar-height) + 12px)" : 20,
          overflow: "auto",
        }}>
          <Suspense fallback={<div style={{ padding: 24, textAlign: "center" }}>加载中…</div>}>
            <Routes>
              <Route path="/login" element={<VisitorLogin />} />
              {/* 管理员后台：管理员登录入口已移至 /login 页（IP 限制显示），此处无需独立登录路由 */}
              <Route path="/admin" element={<RequireAdmin><Admin /></RequireAdmin>} />
              <Route element={<RequireVisitorOrAnon><Outlet /></RequireVisitorOrAnon>}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/feed" element={<Feed />} />
                <Route path="/posts" element={<Navigate to="/feed" replace />} />
                <Route path="/summary" element={<Navigate to="/feed" replace />} />
                <Route path="/screener" element={<Screener />} />
                <Route path="/sectors" element={<Navigate to="/screener" replace />} />
                <Route path="/my" element={<My />} />
                <Route path="/stock/:code" element={<StockDetail />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </Content>
      </Layout>
      {isMobile && <BottomTabBar selected={selected} onSelect={nav} />}
      {loggedIn && <FeibiWidget />}
    </Layout>
  );
}
