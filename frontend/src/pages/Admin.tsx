import {
  Button, Card, Checkbox, Col, DatePicker, Form, Input, InputNumber,
  Collapse, Row, Select, Space, Statistic, Switch, Table, Tag, Typography, Upload, message,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";

import { api, errMsg } from "@/api/client";
import {
  useAuthSettings, useBackfillFailures, useDataHealth, useJobStatus, useRecentJobs, useSaveAuthSettings, useSaveSchedule, useSchedule, useUsers,
} from "@/api/hooks";
import { useIsMobile } from "@/hooks/useIsMobile";

// ---- 单个后台任务面板：触发 + 轮询状态 ----
function JobPanel({ title, desc, kind, triggerPath, statusPath, body, backfill }: {
  title: string; desc: string; kind: string; triggerPath: string; statusPath: string; body?: object; backfill?: boolean;
}) {
  const [polling, setPolling] = useState(true);
  const [failedOnly, setFailedOnly] = useState(false);
  const [backfillDays, setBackfillDays] = useState(60);
  const { data: status } = useJobStatus(kind, statusPath, polling);

  useEffect(() => { setPolling(!!status?.running); }, [status?.running]);

  const trigger = () => {
    api.post(triggerPath, backfill ? { ...(body ?? {}), days: backfillDays, failed_only: failedOnly } : (body ?? {})).then((r) => {
      if (r.data?.started === false && r.data?.running) {
        message.warning(r.data?.error || "任务已在运行中，请稍后再试");
      } else {
        message.success("已触发");
      }
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
          {backfill ? (
            <Space wrap>
              <Space size={4}>
                <Typography.Text type="secondary">向前补</Typography.Text>
                <InputNumber min={20} max={500} value={backfillDays} onChange={(v) => setBackfillDays(v || 60)} addonAfter="条" />
              </Space>
              <Checkbox checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)}>
                只重试上次失败的标的
              </Checkbox>
            </Space>
          ) : null}
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
          <Form.Item name="stock_auto_sync_enabled" label="全市场行情同步" valuePropName="checked" style={{ marginBottom: 0, display: "inline-block", marginRight: 24 }}>
            <Switch />
          </Form.Item>
          <Form.Item name="stock_sync_interval" label="行情间隔(分)" style={{ marginBottom: 0, display: "inline-block", marginRight: 24 }}>
            <InputNumber min={5} max={240} />
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
              onSuccess: () => message.success(v ? "已开启：登录页将显示游客入口" : "已关闭：须用微信/邮箱账号登录"),
              onError: (e) => message.error(errMsg(e)),
            })
          }
        />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {enabled ? "已开启：游客可在登录页以游客方式进入（只读）" : "已关闭：须用微信/邮箱账号登录，无游客入口"}
        </Typography.Text>
      </Space>
    </Card>
  );
}

const JOB_LABELS: Record<string, string> = {
  stock_sync: "行情快照",
  stock_backfill: "历史K线回补",
  finance_sync: "财务指标",
  bond_sync: "转债行情",
  bond_basic_sync: "转债资料",
  sector_sync: "板块名单",
  sector_members_sync: "板块成分股",
  sync_xueqiu_sectors: "雪球板块",
  crawl: "雪球采集",
  wechat_import: "微信公众号导入",
  wechat_discover: "公众号历史发现",
  summarize: "AI总结",
};

function formatJobTime(value?: number) {
  return value ? dayjs.unix(value).format("MM-DD HH:mm") : "-";
}

function formatDuration(value?: number | null) {
  if (value == null) return "-";
  if (value < 60) return `${value}秒`;
  return `${Math.floor(value / 60)}分${value % 60}秒`;
}

function MonitoringPanel() {
  const { data: health, isLoading: healthLoading } = useDataHealth();
  const { data: recent, isLoading: jobsLoading } = useRecentJobs();
  const { data: failures, isLoading: failuresLoading } = useBackfillFailures();
  const [retrying, setRetrying] = useState(false);
  const retryFailures = () => {
    setRetrying(true);
    api.post("/api/stock/backfill", { days: 60, failed_only: true })
      .then((r) => {
        if (r.data?.started === false) message.warning(r.data?.error || "已有回补任务运行中");
        else message.success("已提交失败标的重试任务");
      })
      .catch((e) => message.error(errMsg(e)))
      .finally(() => setRetrying(false));
  };
  return (
    <>
      <Card size="small" title="数据健康">
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}><Statistic title="股票最新交易日" value={health?.stock_date || "暂无"} loading={healthLoading} /></Col>
          <Col xs={12} md={6}><Statistic title="股票当天记录" value={health?.stock_count ?? 0} loading={healthLoading} /></Col>
          <Col xs={12} md={6}><Statistic title="转债最新交易日" value={health?.bond_date || "暂无"} loading={healthLoading} /></Col>
          <Col xs={12} md={6}><Statistic title="转债当天记录" value={health?.bond_count ?? 0} loading={healthLoading} /></Col>
          <Col xs={12} md={6}>
            <Statistic title="回补失败标的" value={health?.backfill_failures ?? 0} loading={healthLoading}
              valueStyle={health?.backfill_failures ? { color: "#cf1322" } : undefined} />
          </Col>
        </Row>
        <Typography.Text type="secondary" style={{ display: "block", marginTop: 10, fontSize: 12 }}>
          最近行情同步：{health?.stock_sync_status === "running" ? "运行中" : health?.stock_sync_status === "success" ? "成功" : health?.stock_sync_status === "error" ? "失败" : "暂无记录"}
          {health?.stock_sync_duration_seconds != null ? `，耗时 ${formatDuration(health.stock_sync_duration_seconds)}` : ""}
          {health?.stock_sync_summary ? `，${health.stock_sync_summary}` : ""}
        </Typography.Text>
      </Card>
      <Collapse defaultActiveKey={[]} style={{ marginTop: 12 }} items={[{
        key: "recent-jobs",
        label: `最近任务（${recent?.items?.length || 0}）`,
        children: <Table
          size="small"
          loading={jobsLoading}
          rowKey="id"
          pagination={false}
          scroll={{ x: 620 }}
          dataSource={recent?.items || []}
          expandable={{
            expandedRowRender: (record) => (
              <pre style={{ margin: 0, maxHeight: 260, overflow: "auto", whiteSpace: "pre-wrap", fontSize: 12 }}>
                {record.log || record.error || "暂无详细日志"}
              </pre>
            ),
            rowExpandable: (record) => !!record.log || !!record.error,
          }}
          columns={[
            { title: "任务", dataIndex: "kind", render: (v: string) => JOB_LABELS[v] || v },
            { title: "状态", dataIndex: "status", render: (v: string) => <Tag color={v === "running" ? "processing" : v === "success" || v === "done" ? "success" : "error"}>{v === "running" ? "运行中" : v === "success" || v === "done" ? "完成" : "失败"}</Tag> },
            { title: "来源", dataIndex: "source" },
            { title: "开始", dataIndex: "started_at", render: formatJobTime },
            { title: "结束", dataIndex: "finished_at", render: formatJobTime },
            { title: "耗时", dataIndex: "duration_seconds", render: formatDuration },
            { title: "错误", dataIndex: "error", ellipsis: true },
          ]}
        />,
      }]} />
      <Collapse defaultActiveKey={[]} style={{ marginTop: 12 }} items={[{
        key: "backfill-failures",
        label: `回补失败清单（${failures?.items?.length || 0}）`,
        extra: <Button size="small" type="primary" disabled={!failures?.items?.length} loading={retrying} onClick={(e) => { e.stopPropagation(); retryFailures(); }}>重试全部失败</Button>,
        children: <Table
          size="small"
          loading={failuresLoading}
          rowKey={(r) => `${r.asset_type}-${r.code}`}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          scroll={{ x: 620 }}
          dataSource={failures?.items || []}
          columns={[
            { title: "类型", dataIndex: "asset_type", render: (v: string) => v === "bond" ? "转债" : "股票" },
            { title: "代码", dataIndex: "code" },
            { title: "更新时间", dataIndex: "updated_at", render: (v: number) => formatJobTime(v) },
            { title: "错误", dataIndex: "error", ellipsis: true },
          ]}
        />,
      }]} />
    </>
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
    .then((r) => {
      if (r.data?.started === false && r.data?.running) {
        message.warning(r.data?.error || "任务已在运行中，请稍后再试");
      } else {
        message.success("已触发");
      }
      setPolling(true);
    })
    .catch((e) => message.error(errMsg(e)));
  return (
    <Space>
      <Button type="primary" onClick={trigger} loading={status?.running}>开始生成</Button>
      {status?.running && <Tag color="processing">运行中</Tag>}
      {status?.log?.length ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>{status.log[status.log.length - 1]}</Typography.Text> : null}
    </Space>
  );
}

export default function Admin() {
  const isMobile = useIsMobile();

  const cleanupZombie = () => {
    api.post("/api/jobs/cleanup-zombie").then((r) => {
      if (r.data.cleaned === 0) {
        message.info("没有僵尸任务需要清理");
      } else {
        message.success(`已清理 ${r.data.cleaned} 个僵尸任务`);
      }
    }).catch((e) => message.error(errMsg(e)));
  };

  return (
    <Space direction="vertical" size={isMobile ? 12 : 16} style={{ width: "100%" }}>
      <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>管理后台</Typography.Title>

      <Card size="small" style={{ marginBottom: 12 }}>
        <Space>
          <Button danger onClick={cleanupZombie}>
            清理僵尸任务
          </Button>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            如果任务卡住超过 2 小时，点击清理后可重新触发
          </Typography.Text>
        </Space>
      </Card>

      <MonitoringPanel />

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={24} md={12}>
          <Typography.Title level={5}>数据同步</Typography.Title>
          <JobPanel title="行情快照同步" desc="全市场A股 + ETF最新行情快照" kind="stock_sync"
            triggerPath="/api/stock/sync" statusPath="/api/stock/sync/status" />
          <JobPanel title="转债资料同步" desc="转股价、到期日、信用等级等基础资料" kind="bond_basic_sync"
            triggerPath="/api/bond/basic_sync" statusPath="/api/bond/basic_sync/status" />
          <JobPanel title="财务指标同步" desc="全市场最新一期财报指标" kind="finance_sync"
            triggerPath="/api/stock/finance_sync" statusPath="/api/stock/finance_sync/status" />
          <JobPanel title="板块名单同步" desc="行业/概念板块名录" kind="sector_sync"
            triggerPath="/api/stock/sync-sectors" statusPath="/api/stock/sync-sectors/status" />
          <JobPanel title="板块成分股全量同步" desc="供个股「所属板块」反查完整覆盖" kind="sector_members_sync"
            triggerPath="/api/stock/sync-sector-members" statusPath="/api/stock/sync-sector-members/status" />
          <JobPanel title="历史K线回补" desc="保留已有数据，并向更早日期扩展指定条数" kind="stock_backfill"
            triggerPath="/api/stock/backfill" statusPath="/api/stock/backfill/status" body={{ days: 60 }} backfill />
          <JobPanel title="雪球板块同步" desc="申万134个行业（含半导体/软件开发等），耗时较长" kind="sync_xueqiu_sectors"
            triggerPath="/api/stock/sync-xueqiu-sectors" statusPath="/api/stock/sync-xueqiu-sectors/status" />
        </Col>
        <Col xs={24} md={12}>
          <Typography.Title level={5}>采集与总结</Typography.Title>
          <JobPanel title="雪球采集" desc="抓取大V新帖（Playwright+Chromium）" kind="crawl"
            triggerPath="/api/crawl" statusPath="/api/crawl/status" body={{ summarize: true }} />
          <JobPanel title="沪深 300 基准同步" desc="同步观点复盘所需的沪深 300 历史行情" kind="index_sync"
            triggerPath="/api/index/sync" statusPath="/api/index/sync/status" />
          <WechatImportPanel />
          <WechatDiscoverPanel />
          <BigvReviewPanel />
          <SummarizePanel />
          <SchedulePanel />
          <AuthSettingsPanel />
        </Col>
      </Row>
    </Space>
  );
}

function WechatImportPanel() {
  const [urls, setUrls] = useState("");
  const [polling, setPolling] = useState(true);
  const { data: status } = useJobStatus("wechat_import", "/api/wechat/import/status", polling);
  useEffect(() => { setPolling(!!status?.running); }, [status?.running]);
  const trigger = () => {
    const values = urls.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
    if (!values.length) { message.warning("请输入微信公众号文章链接"); return; }
    api.post("/api/wechat/import", { urls: values })
      .then((r) => {
        if (r.data?.started === false && r.data?.running) message.warning("公众号导入任务正在运行");
        else message.success("已提交公众号文章导入");
        setPolling(true);
      })
      .catch((e) => message.error(errMsg(e)));
  };
  const uploadCsv = (file: File) => {
    const form = new FormData();
    form.append("file", file);
    api.post("/api/wechat/import-csv", form)
      .then((r) => {
        if (r.data?.started === false && r.data?.running) message.warning("公众号导入任务正在运行");
        else message.success("已提交 CSV 批量导入，并自动生成 AI 总结");
        setPolling(true);
      })
      .catch((e) => message.error(errMsg(e)));
  };
  return (
    <Card size="small" title="微信公众号文章导入" style={{ marginBottom: 12 }}>
      <Space.Compact style={{ width: "100%" }}>
        <Input.TextArea value={urls} onChange={(e) => setUrls(e.target.value)} autoSize={{ minRows: 2, maxRows: 6 }} placeholder="每行粘贴一个 mp.weixin.qq.com/s/... 文章链接" />
        <Button type="primary" onClick={trigger} loading={status?.running}>导入</Button>
      </Space.Compact>
      <Upload accept=".csv,text/csv" showUploadList={false} beforeUpload={(file) => { uploadCsv(file); return false; }} disabled={status?.running}>
        <Button style={{ marginTop: 8 }} disabled={status?.running}>上传 CSV 批量导入</Button>
      </Upload>
      <Typography.Text type="secondary" style={{ display: "block", fontSize: 12, marginTop: 6 }}>
        每篇串行抓取，间隔约 4 秒；重复文章自动覆盖更新，不会重复新增。
      </Typography.Text>
      {status?.log?.length ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>{status.log[status.log.length - 1]}</Typography.Text> : null}
      {status?.error ? <div style={{ color: "#cf1322", fontSize: 12 }}>{status.error}</div> : null}
    </Card>
  );
}

function WechatDiscoverPanel() {
  const [keyword, setKeyword] = useState("主升龙神");
  const [polling, setPolling] = useState(true);
  const { data: status } = useJobStatus("wechat_discover", "/api/wechat/discover/status", polling);
  useEffect(() => { setPolling(!!status?.running); }, [status?.running]);
  const trigger = () => api.post("/api/wechat/discover", { keyword, pages: 1 })
    .then(() => { message.success("已提交低频历史发现"); setPolling(true); })
    .catch((e) => message.error(errMsg(e)));
  return (
    <Card size="small" title="公众号历史文章发现" style={{ marginBottom: 12 }}>
      <Space.Compact style={{ width: "100%" }}>
        <Input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="公众号名称" />
        <Button onClick={trigger} loading={status?.running}>发现一页</Button>
      </Space.Compact>
      <Typography.Text type="secondary" style={{ display: "block", fontSize: 12, marginTop: 6 }}>
        低频搜索一页并自动尝试导入；搜狗触发验证时，请使用上方链接批量导入。
      </Typography.Text>
      {status?.log?.length ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>{status.log[status.log.length - 1]}</Typography.Text> : null}
      {status?.error ? <div style={{ color: "#cf1322", fontSize: 12 }}>{status.error}</div> : null}
    </Card>
  );
}

function BigvReviewPanel() {
  const { data: users } = useUsers();
  const [user, setUser] = useState("");
  const [start, setStart] = useState<Dayjs | null>(null);
  const [end, setEnd] = useState<Dayjs | null>(null);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<Array<Record<string, any>>>([]);
  const load = () => {
    setLoading(true);
    api.get("/api/bigv-review", { params: {
      user,
      start: start?.format("YYYY-MM-DD") || "",
      end: end?.format("YYYY-MM-DD") || "",
      limit: 200,
    } }).then((r) => setItems(r.data?.items || []))
      .catch((e) => message.error(errMsg(e)))
      .finally(() => setLoading(false));
  };
  return (
    <Card size="small" title="大 V 观点与行情复盘" style={{ marginBottom: 12 }}>
      <Space wrap style={{ marginBottom: 8 }}>
        <Select allowClear placeholder="全部大 V" style={{ width: 160 }} value={user || undefined}
          onChange={(v) => setUser(v || "")} options={users?.map((u) => ({ value: u.id, label: u.name }))} />
        <DatePicker value={start} onChange={setStart} placeholder="开始日期" />
        <DatePicker value={end} onChange={setEnd} placeholder="结束日期" />
        <Button type="primary" onClick={load} loading={loading}>开始复盘</Button>
        <Button onClick={() => api.post("/api/bigv-review/extract")
          .then((r) => message.success(`已提交 ${r.data?.count || 0} 篇文章的观点提取任务`))
          .catch((e) => message.error(errMsg(e)))}>
          补提取观点
        </Button>
      </Space>
      <Table
        size="small"
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
        scroll={{ x: 900 }}
        dataSource={items}
        columns={[
          { title: "日期", dataIndex: "date", width: 100 },
          { title: "大 V", dataIndex: "user_name", width: 120 },
          { title: "文章", dataIndex: "title", ellipsis: true },
          { title: "方向", dataIndex: "direction", width: 80, render: (v: string) => <Tag color={v === "看多" ? "red" : v === "看空" ? "green" : "default"}>{v}</Tag> },
          { title: "标的", width: 180, render: (_: unknown, r: Record<string, any>) => r.targets?.map((t: Record<string, string>) => `${t.name}(${t.code})`).join("、") || "未识别" },
          { title: "验证", dataIndex: "verdict", width: 90 },
          { title: "复盘", width: 90, render: (_: unknown, r: Record<string, any>) => r.targets?.[0]?.performance?.["5"] != null ? `5日 ${r.targets[0].performance["5"]}%` : "暂无数据" },
        ]}
      />
    </Card>
  );
}
void dayjs;
