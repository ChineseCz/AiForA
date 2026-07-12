import {
  Alert, Button, Card, Checkbox, Col, DatePicker, Form, Input, InputNumber,
  Row, Select, Space, Switch, Tag, Typography, message,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, errMsg } from "@/api/client";
import {
  useAuthSettings, useJobStatus, useLogin, useSaveAuthSettings, useSaveSchedule, useSchedule, useUsers,
} from "@/api/hooks";
import { useAuth } from "@/auth";
import { useIsMobile } from "@/hooks/useIsMobile";

// ---- 登录表单 ----
function LoginForm() {
  const login = useLogin();
  const auth = useAuth();
  const nav = useNavigate();
  return (
    <Row justify="center" style={{ marginTop: "min(80px, 8vh)", padding: "0 12px" }}>
      <Card title="管理员登录" style={{ width: "100%", maxWidth: 360 }}>
        <Form
          layout="vertical"
          onFinish={(v) =>
            login.mutate(v, {
              onSuccess: (d) => { auth.login(d.access_token); message.success("登录成功"); nav("/admin"); },
              onError: (e) => message.error(errMsg(e, "登录失败")),
            })
          }
        >
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={login.isPending}>登录</Button>
        </Form>
      </Card>
    </Row>
  );
}

// ---- 单个后台任务面板：触发 + 轮询状态 ----
function JobPanel({ title, desc, kind, triggerPath, statusPath, body }: {
  title: string; desc: string; kind: string; triggerPath: string; statusPath: string; body?: object;
}) {
  const [polling, setPolling] = useState(true);
  const { data: status } = useJobStatus(kind, statusPath, polling);

  useEffect(() => { setPolling(!!status?.running); }, [status?.running]);

  const trigger = () => {
    api.post(triggerPath, body ?? {}).then((r) => {
      if (r.data?.started === false && r.data?.running) message.info("任务已在运行中");
      else message.success("已触发");
      setPolling(true);
    }).catch((e) => message.error(errMsg(e)));
  };

  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Row justify="space-between" align="middle">
        <Col flex="auto">
          <Space>
            <Typography.Text strong>{title}</Typography.Text>
            {status?.running
              ? <Tag color="processing">运行中</Tag>
              : status?.error ? <Tag color="error">失败</Tag>
              : status?.finished_at ? <Tag color="success">完成 {status.finished_at}</Tag> : null}
          </Space>
          <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{desc}</Typography.Text></div>
          {status?.log?.length ? (
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>{status.log[status.log.length - 1]}</div>
          ) : null}
          {status?.error ? <div style={{ color: "#cf1322", fontSize: 12 }}>{status.error}</div> : null}
        </Col>
        <Col>
          <Button onClick={trigger} loading={status?.running}>触发</Button>
        </Col>
      </Row>
    </Card>
  );
}

// ---- 定时任务配置 ----
function SchedulePanel() {
  const { data } = useSchedule();
  const save = useSaveSchedule();
  const [form] = Form.useForm();
  useEffect(() => { if (data) form.setFieldsValue(data); }, [data, form]);
  return (
    <Card size="small" title="定时任务">
      <Form form={form} onFinish={(v) =>
        save.mutate(v, { onSuccess: () => message.success("已保存"), onError: (e) => message.error(errMsg(e)) })}>
        <Space wrap style={{ marginBottom: 4 }}>
          <Form.Item name="enabled" label="定时采集" valuePropName="checked" style={{ marginBottom: 0 }}><Switch /></Form.Item>
          <Form.Item name="start" label="从" style={{ marginBottom: 0 }}><Input style={{ width: 90 }} placeholder="08:00" /></Form.Item>
          <Form.Item name="end" label="到" style={{ marginBottom: 0 }}><Input style={{ width: 90 }} placeholder="22:00" /></Form.Item>
          <Form.Item name="interval" label="间隔(分)" style={{ marginBottom: 0 }}><InputNumber min={5} /></Form.Item>
        </Space>
        <Space wrap style={{ marginBottom: 8, display: "block" }}>
          <Form.Item name="stock_auto_sync_enabled" label="全市场行情10分钟同步" valuePropName="checked" style={{ marginBottom: 0, display: "inline-block", marginRight: 24 }}>
            <Switch />
          </Form.Item>
          <Form.Item name="weekly_summary_enabled" label="周三/周日周总结" valuePropName="checked" style={{ marginBottom: 0, display: "inline-block" }}>
            <Switch />
          </Form.Item>
        </Space>
        <Button type="primary" htmlType="submit" loading={save.isPending}>保存</Button>
      </Form>
    </Card>
  );
}

// ---- 用户模式开关 ----
function AuthSettingsPanel() {
  const { data } = useAuthSettings();
  const save = useSaveAuthSettings();
  const enabled = !!data?.require_login_enabled;
  return (
    <Card size="small" title="访客登录" style={{ marginBottom: 12 }}>
      <Space align="center">
        <Switch
          checked={enabled}
          loading={save.isPending}
          onChange={(v) =>
            save.mutate({ require_login_enabled: v }, {
              onSuccess: () => message.success(v ? "已开启，访客需登录才能查看" : "已关闭，恢复匿名访问"),
              onError: (e) => message.error(errMsg(e)),
            })
          }
        />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {enabled ? "已开启：访客需登录（手机号或微信）才能访问只读页面" : "已关闭：任何人可匿名浏览只读页面"}
        </Typography.Text>
      </Space>
    </Card>
  );
}

// ---- 总结生成 ----
function SummarizePanel() {
  const { data: users } = useUsers();
  const [type, setType] = useState("daily");
  const [user, setUser] = useState<string>("");
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [regen, setRegen] = useState(false);
  const body = {
    type, user, regen,
    start: range?.[0] ? range[0].format("YYYY-MM-DD") : "",
    end: range?.[1] ? range[1].format("YYYY-MM-DD") : "",
  };
  return (
    <Card size="small" title="生成 AI 总结" style={{ marginBottom: 12 }}>
      <Space wrap style={{ marginBottom: 8 }}>
        <Select value={type} onChange={setType} style={{ width: 100 }}
          options={["daily", "weekly", "monthly", "yearly", "highlights"].map((v) => ({ value: v, label: v }))} />
        <Select allowClear placeholder="全部大V" style={{ width: 160 }} value={user || undefined}
          onChange={(v) => setUser(v || "")} options={users?.map((u) => ({ value: u.id, label: u.name }))} />
        <DatePicker.RangePicker value={range as never} onChange={(v) => setRange(v as never)} />
        <Checkbox checked={regen} onChange={(e) => setRegen(e.target.checked)}>
          强制重新生成（覆盖范围内已有的总结）
        </Checkbox>
      </Space>
      <JobPanelInline kind="summarize" triggerPath="/api/summarize" statusPath="/api/summarize/status" body={body} />
    </Card>
  );
}
// 复用 JobPanel 的触发+状态，但嵌在带参数的卡片里（去掉外层卡片）
function JobPanelInline(p: { kind: string; triggerPath: string; statusPath: string; body: object }) {
  const [polling, setPolling] = useState(true);
  const { data: status } = useJobStatus(p.kind, p.statusPath, polling);
  useEffect(() => { setPolling(!!status?.running); }, [status?.running]);
  const trigger = () => api.post(p.triggerPath, p.body)
    .then(() => { message.success("已触发"); setPolling(true); })
    .catch((e) => message.error(errMsg(e)));
  return (
    <Space>
      <Button type="primary" onClick={trigger} loading={status?.running}>开始生成</Button>
      {status?.running && <Tag color="processing">运行中</Tag>}
      {status?.log?.length ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>{status.log[status.log.length - 1]}</Typography.Text> : null}
    </Space>
  );
}

export default function Admin({ login }: { login?: boolean }) {
  const { loggedIn, logout } = useAuth();
  const isMobile = useIsMobile();
  if (login || !loggedIn) return <LoginForm />;

  return (
    <Space direction="vertical" size={isMobile ? 12 : 16} style={{ width: "100%" }}>
      <Row justify="space-between" align="middle">
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>管理后台</Typography.Title>
        <Button onClick={logout} size={isMobile ? "small" : "middle"}>退出登录</Button>
      </Row>

      <Alert type="info"
        message="抓取 / 历史K线回补依赖真实浏览器，需在 Windows 宿主的 browser 队列 worker 上运行；此处触发的这两项会进入队列等待宿主 worker 消费。" />

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={24} md={12}>
          <Typography.Title level={5}>数据同步</Typography.Title>
          <JobPanel title="行情快照同步" desc="全市场A股最新行情快照" kind="stock_sync"
            triggerPath="/api/stock/sync" statusPath="/api/stock/sync/status" />
          <JobPanel title="财务指标同步" desc="全市场最新一期财报指标" kind="finance_sync"
            triggerPath="/api/stock/finance_sync" statusPath="/api/stock/finance_sync/status" />
          <JobPanel title="板块名单同步" desc="行业/概念板块名录" kind="sector_sync"
            triggerPath="/api/stock/sync-sectors" statusPath="/api/stock/sync-sectors/status" />
          <JobPanel title="板块成分股全量同步" desc="供个股「所属板块」反查完整覆盖" kind="sector_members_sync"
            triggerPath="/api/stock/sync-sector-members" statusPath="/api/stock/sync-sector-members/status" />
          <JobPanel title="历史K线回补（宿主队列）" desc="均线类策略依赖，需宿主 worker" kind="stock_backfill"
            triggerPath="/api/stock/backfill" statusPath="/api/stock/backfill/status" body={{ days: 60 }} />
          <JobPanel title="雪球板块同步（宿主队列）" desc="申万134个行业（含半导体/软件开发等），需宿主 worker，耗时较长" kind="sync_xueqiu_sectors"
            triggerPath="/api/stock/sync-xueqiu-sectors" statusPath="/api/stock/sync-xueqiu-sectors/status" />
        </Col>
        <Col xs={24} md={12}>
          <Typography.Title level={5}>采集与总结</Typography.Title>
          <JobPanel title="雪球采集（宿主队列）" desc="抓取大V新帖，需宿主 worker（真实 Edge）" kind="crawl"
            triggerPath="/api/crawl" statusPath="/api/crawl/status" body={{ summarize: true }} />
          <SummarizePanel />
          <SchedulePanel />
          <AuthSettingsPanel />
        </Col>
      </Row>
    </Space>
  );
}
void dayjs;
