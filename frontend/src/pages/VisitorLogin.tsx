import { Button, Card, Form, Input, Row, Tabs, message } from "antd";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { errMsg } from "@/api/client";
import { useEmailLogin, useEmailRegister, useSendEmailCode, useWechatCodeLogin } from "@/api/hooks";
import { useVisitorAuth } from "@/visitorAuth";

const RESEND_SECONDS = 60;

// 手机短信登录需要短信服务资质认证，暂时做不了，先只保留微信登录（SmsLoginTab 已移除，
// 后端 /api/user/sms/* 接口保留未删，资质办下来后可以直接把 Tab 加回来）。
function WechatLoginTab() {
  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useVisitorAuth();
  const from: string = (loc.state as { from?: string } | null)?.from ?? "/";
  const wechatLogin = useWechatCodeLogin();

  const handleLogin = (values: { code: string }) => {
    wechatLogin.mutate({ code: values.code.trim() }, {
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
        <div style={{ marginTop: 8, color: "#555", fontSize: 13 }}>
          扫码关注公众号，发送任意消息
        </div>
        <div style={{ color: "#888", fontSize: 12 }}>
          收到验证码后填入下方
        </div>
      </div>
      <Form layout="vertical" onFinish={handleLogin}>
        <Form.Item name="code" rules={[{ required: true, message: "请输入验证码" }]}>
          <Input placeholder="输入公众号回复的 6 位验证码" maxLength={6} style={{ textAlign: "center" }} />
        </Form.Item>
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
  const from: string = (loc.state as { from?: string } | null)?.from ?? "/";
  const emailLogin = useEmailLogin();

  const handleLogin = (values: { email: string; password: string }) => {
    emailLogin.mutate(
      { email: values.email.trim().toLowerCase(), password: values.password },
      {
        onSuccess: (d) => { login(d.access_token); nav(from, { replace: true }); },
        onError: (e) => message.error(errMsg(e, "登录失败")),
      },
    );
  };

  return (
    <Form layout="vertical" onFinish={handleLogin}>
      <Form.Item name="email" label="邮箱" rules={[{ required: true, message: "请输入邮箱" }]}>
        <Input placeholder="请输入邮箱" autoComplete="email" />
      </Form.Item>
      <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
        <Input.Password placeholder="请输入密码" autoComplete="current-password" />
      </Form.Item>
      <Form.Item style={{ marginBottom: 0 }}>
        <Button type="primary" htmlType="submit" block loading={emailLogin.isPending}>
          登录
        </Button>
      </Form.Item>
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
    sendCode.mutate({ email: v }, {
      onSuccess: () => { setCodeSent(true); startCountdown(); message.success("验证码已发送，请查收邮件（也留意垃圾箱）"); },
      onError: (e) => message.error(errMsg(e, "发送失败")),
    });
  };

  const handleRegister = (values: { code: string; password: string }) => {
    register.mutate(
      { email: email.trim().toLowerCase(), code: values.code, password: values.password },
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
        <Button type="primary" block loading={sendCode.isPending} onClick={handleSend}>
          获取验证码
        </Button>
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
          <Form.Item style={{ marginBottom: 8 }}>
            <Button type="primary" htmlType="submit" block loading={register.isPending}>
              注册并登录
            </Button>
          </Form.Item>
          <Button block disabled={countdown > 0} loading={sendCode.isPending} onClick={handleSend}>
            {countdown > 0 ? `${countdown}s 后重新发送` : "重新发送验证码"}
          </Button>
        </>
      )}
    </Form>
  );
}

export default function VisitorLogin() {
  return (
    <Row justify="center" style={{ marginTop: 80 }}>
      <Card style={{ width: 360 }}>
        <Tabs
          centered
          items={[
            { key: "wechat", label: "微信登录", children: <WechatLoginTab /> },
            { key: "email-login", label: "邮箱登录", children: <EmailLoginTab /> },
            { key: "email-register", label: "邮箱注册", children: <EmailRegisterTab /> },
          ]}
        />
      </Card>
    </Row>
  );
}
