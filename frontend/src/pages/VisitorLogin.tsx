import { LineChartOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Checkbox, Form, Input, Modal, Row, Segmented, Space, Tabs, Typography, message } from "antd";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { errMsg } from "@/api/client";
import { useAuthConfig, useEmailLogin, useEmailRegister, useGuestLogin, useRegisterCaptcha, useResetCaptcha, useResetPassword, useSendEmailCode, useSendResetEmailCode, useWechatCodeLogin } from "@/api/hooks";
import { useAuth } from "@/auth";
import { useVisitorAuth } from "@/visitorAuth";

const RESEND_SECONDS = 60;

function RememberLogin() {
  return (
    <Form.Item name="remember" valuePropName="checked" initialValue={true} style={{ marginBottom: 12 }}>
      <Checkbox>30日内免登录</Checkbox>
    </Form.Item>
  );
}

// 手机短信登录需要短信服务资质认证，暂时做不了，先只保留微信登录（SmsLoginTab 已移除，
// 后端 /api/user/sms/* 接口保留未删，资质办下来后可以直接把 Tab 加回来）。
function WechatLoginTab() {
  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useVisitorAuth();
  const from: string = (loc.state as { from?: string } | null)?.from ?? "/";
  const wechatLogin = useWechatCodeLogin();

  const handleLogin = (values: { code: string; remember?: boolean }) => {
    wechatLogin.mutate({ code: values.code.trim(), remember: !!values.remember }, {
      onSuccess: (d) => { login(d.access_token); nav(from, { replace: true }); },
      onError: (e) => message.error(errMsg(e, "验证失败，验证码错误或已过期")),
    });
  };

  return (
    <div>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <img
          src="/icons/qrcode_for_gh_bb2ee3d5682a_258.jpg"
          alt="关注公众号"
          style={{ width: 180, height: 180 }}
        />
        <div style={{ marginTop: 8, color: "var(--text-primary)", fontSize: 13 }}>
          扫码关注公众号，发送任意消息
        </div>
        <div style={{ color: "var(--text-secondary)", fontSize: 12 }}>
          收到验证码后填入下方
        </div>
      </div>
      <Form layout="vertical" onFinish={handleLogin}>
        <Form.Item name="code" rules={[{ required: true, message: "请输入验证码" }]}>
          <Input placeholder="输入公众号回复的 6 位验证码" maxLength={6} style={{ textAlign: "center" }} />
        </Form.Item>
        <RememberLogin />
        <Button type="primary" htmlType="submit" block loading={wechatLogin.isPending}>
          登录
        </Button>
      </Form>
    </div>
  );
}

function EmailLoginTab() {
  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useVisitorAuth();
  const auth = useAuth();
  const from: string = (loc.state as { from?: string } | null)?.from ?? "/";
  const emailLogin = useEmailLogin();
  const [loginForm] = Form.useForm();
  const sendResetCode = useSendResetEmailCode();
  const resetPassword = useResetPassword();
  const [resetOpen, setResetOpen] = useState(false);
  const [captchaOpen, setCaptchaOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetSent, setResetSent] = useState(false);
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [resetForm] = Form.useForm();
  const captcha = useResetCaptcha(captchaOpen);

  const sendReset = () => {
    const email = resetEmail.trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { message.warning("请输入正确的邮箱地址"); return; }
    sendResetCode.mutate({ email, captcha_id: captcha.data?.challenge_id || "", captcha_answer: captchaAnswer.trim() }, {
      onSuccess: () => { setResetSent(true); setCaptchaAnswer(""); setCaptchaOpen(false); message.success("如果邮箱已注册，验证码将发送到邮箱"); captcha.refetch(); },
      onError: (e) => message.error(errMsg(e, "发送失败")),
    });
  };

  const openReset = () => {
    const email = String(loginForm.getFieldValue("email") || "").trim().toLowerCase();
    if (!email) {
      message.warning("请先填写邮箱，再点击忘记密码");
      return;
    }
    setResetEmail(email);
    setCaptchaAnswer("");
    setResetOpen(true);
  };

  const reset = (values: { code: string; password: string }) => {
    resetPassword.mutate(
      { email: resetEmail.trim().toLowerCase(), code: values.code, password: values.password },
      {
        onSuccess: () => { message.success("密码已重置，请使用新密码登录"); setResetOpen(false); setResetSent(false); resetForm.resetFields(); },
        onError: (e) => message.error(errMsg(e, "重置失败")),
      },
    );
  };

  const handleLogin = (values: { email: string; password: string; remember?: boolean }) => {
    emailLogin.mutate(
      { email: values.email.trim().toLowerCase(), password: values.password, remember: !!values.remember },
      {
        onSuccess: (d) => {
          login(d.access_token);
          if (d.admin_token) auth.login(d.admin_token);
          nav(from, { replace: true });
        },
        onError: (e) => message.error(errMsg(e, "登录失败")),
      },
    );
  };

  return (
    <Form form={loginForm} layout="vertical" onFinish={handleLogin}>
      <Form.Item name="email" label="邮箱" rules={[{ required: true, message: "请输入邮箱" }]}>
        <Input placeholder="请输入邮箱" autoComplete="email" />
      </Form.Item>
      <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
        <Input.Password placeholder="请输入密码" autoComplete="current-password" />
      </Form.Item>
      <RememberLogin />
      <Form.Item style={{ marginBottom: 0 }}>
        <Button type="primary" htmlType="submit" block loading={emailLogin.isPending}>
          登录
        </Button>
      </Form.Item>
      <div style={{ textAlign: "right", marginTop: 8 }}>
        <Button type="link" size="small" onClick={openReset}>忘记密码？</Button>
      </div>
      <Modal
        title="找回邮箱密码"
        open={resetOpen}
        onCancel={() => { setResetOpen(false); setCaptchaOpen(false); setResetSent(false); setCaptchaAnswer(""); resetForm.resetFields(); }}
        footer={null}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Typography.Text>验证码将发送到：{resetEmail}</Typography.Text>
          <Button block onClick={() => setCaptchaOpen(true)}>验证并获取重置验证码</Button>
          {resetSent && (
            <Form form={resetForm} layout="vertical" onFinish={reset}>
              <Form.Item name="code" label="验证码" rules={[{ required: true, message: "请输入验证码" }]}>
                <Input maxLength={6} placeholder="请输入邮箱验证码" />
              </Form.Item>
              <Form.Item name="password" label="新密码" rules={[{ required: true, min: 6, message: "密码至少 6 位" }]}>
                <Input.Password placeholder="至少 6 位" autoComplete="new-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={resetPassword.isPending}>确认重置密码</Button>
            </Form>
          )}
        </Space>
      </Modal>
      <Modal
        title="完成图片验证"
        open={captchaOpen}
        onCancel={() => setCaptchaOpen(false)}
        onOk={sendReset}
        okText="验证并发送"
        confirmLoading={sendResetCode.isPending}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          {captcha.data?.image && <img src={captcha.data.image} alt="图片验证码" style={{ width: 144, height: 48, border: "1px solid #d9d9d9", borderRadius: 6 }} />}
          <Input value={captchaAnswer} onChange={(e) => setCaptchaAnswer(e.target.value)} placeholder="请输入图片中的算式答案" inputMode="numeric" maxLength={2} autoFocus />
          <Button type="link" size="small" icon={<ReloadOutlined />} onClick={() => { setCaptchaAnswer(""); captcha.refetch(); }}>看不清，换一张</Button>
        </Space>
      </Modal>
    </Form>
  );
}

function EmailRegisterTab() {
  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useVisitorAuth();
  const from: string = (loc.state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const sendCode = useSendEmailCode();
  const register = useEmailRegister();
  const [captchaOpen, setCaptchaOpen] = useState(false);
  const registerCaptcha = useRegisterCaptcha(captchaOpen);
  const [captchaAnswer, setCaptchaAnswer] = useState("");

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const startCountdown = () => {
    setCountdown(RESEND_SECONDS);
    timer.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(timer.current!); return 0; }
        return c - 1;
      });
    }, 1000);
  };

  const handleSend = () => {
    const v = email.trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { message.warning("请输入正确的邮箱地址"); return; }
    sendCode.mutate({ email: v, captcha_id: registerCaptcha.data?.challenge_id || "", captcha_answer: captchaAnswer.trim() }, {
      onSuccess: () => { setCodeSent(true); setCaptchaAnswer(""); setCaptchaOpen(false); startCountdown(); registerCaptcha.refetch(); message.success("验证码已发送，请查收邮件（也留意垃圾箱）"); },
      onError: (e) => message.error(errMsg(e, "发送失败")),
    });
  };

  const handleRegister = (values: { code: string; password: string; remember?: boolean }) => {
    register.mutate(
      { email: email.trim().toLowerCase(), code: values.code, password: values.password, remember: !!values.remember },
      {
        onSuccess: (d) => { login(d.access_token); nav(from, { replace: true }); },
        onError: (e) => message.error(errMsg(e, "注册失败")),
      },
    );
  };

  return (
    <Form layout="vertical" onFinish={handleRegister}>
      <Form.Item label="邮箱">
        <Input
          value={email}
          onChange={(e) => setEmail(e.target.value.trim())}
          placeholder="请输入邮箱"
          autoComplete="email"
          disabled={codeSent}
        />
      </Form.Item>
      {!codeSent ? (
        <Button type="primary" block onClick={() => setCaptchaOpen(true)}>验证并获取验证码</Button>
      ) : (
        <>
          <Form.Item name="code" label="验证码" rules={[{ required: true, message: "请输入验证码" }]}>
            <Input placeholder="6 位验证码" maxLength={6} autoFocus />
          </Form.Item>
          <Form.Item
            name="password"
            label="设置密码"
            rules={[{ required: true, min: 6, message: "密码至少 6 位" }]}
          >
            <Input.Password placeholder="至少 6 位" autoComplete="new-password" />
          </Form.Item>
          <RememberLogin />
          <Form.Item style={{ marginBottom: 8 }}>
            <Button type="primary" htmlType="submit" block loading={register.isPending}>
              注册并登录
            </Button>
          </Form.Item>
          <Button block disabled={countdown > 0} onClick={() => setCaptchaOpen(true)}>
            {countdown > 0 ? `${countdown}s 后重新发送` : "重新发送验证码"}
          </Button>
        </>
      )}
      <Modal
        title="完成图片验证"
        open={captchaOpen}
        onCancel={() => setCaptchaOpen(false)}
        onOk={handleSend}
        okText="验证并发送"
        confirmLoading={sendCode.isPending}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          {registerCaptcha.data?.image && <img src={registerCaptcha.data.image} alt="图片验证码" style={{ width: 144, height: 48, border: "1px solid #d9d9d9", borderRadius: 6 }} />}
          <Input value={captchaAnswer} onChange={(e) => setCaptchaAnswer(e.target.value)} placeholder="请输入图片中的算式答案" inputMode="numeric" maxLength={2} autoFocus />
          <Button type="link" size="small" icon={<ReloadOutlined />} onClick={() => { setCaptchaAnswer(""); registerCaptcha.refetch(); }}>看不清，换一张</Button>
        </Space>
      </Modal>
    </Form>
  );
}

function EmailAccountTab() {
  const [mode, setMode] = useState<"login" | "register">("login");
  return (
    <div>
      <Segmented
        block
        value={mode}
        onChange={(v) => setMode(v as "login" | "register")}
        options={[
          { value: "login", label: "邮箱登录" },
          { value: "register", label: "邮箱注册" },
        ]}
        style={{ marginBottom: 16 }}
      />
      {mode === "login" ? <EmailLoginTab /> : <EmailRegisterTab />}
    </div>
  );
}

export default function VisitorLogin() {
  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useVisitorAuth();
  const from: string = (loc.state as { from?: string } | null)?.from ?? "/";
  const { data: authConfig } = useAuthConfig();
  const guestLogin = useGuestLogin();

  const handleGuestLogin = () => {
    guestLogin.mutate(undefined, {
      onSuccess: (d) => { login(d.access_token, true); nav(from, { replace: true }); },
      onError: (e) => message.error(errMsg(e, "访客登录失败")),
    });
  };

  return (
    <Row justify="center" style={{ marginTop: "min(64px, 6vh)", padding: "0 12px" }}>
      <div style={{ width: "100%", maxWidth: 360 }}>
        <div className="login-hero">
          <div className="login-hero-icon"><LineChartOutlined /></div>
          <Typography.Title level={3} style={{ margin: "12px 0 2px" }}>雪球看板</Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>大V观点 · 实时行情 · 智能选股</Typography.Text>
        </div>
        <Card style={{ width: "100%" }}>
          <Tabs
            centered
            items={[
              { key: "wechat", label: "微信登录", children: <WechatLoginTab /> },
              { key: "email", label: "邮箱", children: <EmailAccountTab /> },
            ]}
          />
          {authConfig?.visitor_mode && (
            <div style={{ textAlign: "center", marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--ant-line)" }}>
              <Button type="link" onClick={handleGuestLogin} loading={guestLogin.isPending}>
                以游客方式登录（只读）
              </Button>
            </div>
          )}
        </Card>
      </div>
    </Row>
  );
}
