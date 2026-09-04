import { DownloadOutlined } from "@ant-design/icons";
import {
  AutoComplete, Button, Card, Checkbox, Col, DatePicker, Input, Progress, Row, Segmented, Select, Space, Statistic, Switch, Table, Tag, Typography, message,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ReactECharts from "echarts-for-react";

import { api, errMsg, getToken } from "@/api/client";
import { useJobStatus, useUsers } from "@/api/hooks";

type DatePreset = "7d" | "30d" | "90d" | "year" | "all" | "custom";
const REVIEW_PREFS_KEY = "bigv_review_preferences";

function getSavedReviewPrefs(): { user: string; preset: DatePreset; groupByDay: boolean } {
  try {
    const value = JSON.parse(localStorage.getItem(REVIEW_PREFS_KEY) || "{}");
    return {
      user: typeof value.user === "string" ? value.user : "",
      preset: ["7d", "30d", "90d", "year", "all", "custom"].includes(value.preset) ? value.preset : "90d",
      groupByDay: value.groupByDay !== false,
    };
  } catch {
    return { user: "", preset: "90d", groupByDay: true };
  }
}

function datesForPreset(preset: DatePreset): [Dayjs | null, Dayjs | null] {
  const today = dayjs();
  if (preset === "all") return [null, null];
  if (preset === "year") return [today.startOf("year"), today];
  if (preset === "custom") return [null, null];
  return [today.subtract(Number(preset.replace("d", "")), "day"), today];
}

export default function BigvReviewPanel() {
  const isAdmin = !!getToken();
  const { data: users } = useUsers();
  const saved = getSavedReviewPrefs();
  const [user, setUser] = useState(saved.user);
  const [datePreset, setDatePreset] = useState<DatePreset>(saved.preset);
  const initialDates = datesForPreset(saved.preset);
  const [start, setStart] = useState<Dayjs | null>(initialDates[0]);
  const [end, setEnd] = useState<Dayjs | null>(initialDates[1]);
  const [loading, setLoading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [items, setItems] = useState<Array<Record<string, any>>>([]);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [groupByDay, setGroupByDay] = useState(saved.groupByDay);
  const [directionFilter, setDirectionFilter] = useState("");
  const [verdictFilter, setVerdictFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const { data: reviewStatus } = useJobStatus("bigv_review", "/api/bigv-review/run/status", reviewing);

  useEffect(() => {
    localStorage.setItem(REVIEW_PREFS_KEY, JSON.stringify({ user, preset: datePreset, groupByDay }));
  }, [user, datePreset, groupByDay]);

  function load(savedOnly = true) {
    setLoading(true);
    api.get("/api/bigv-review", { params: {
      user, start: start?.format("YYYY-MM-DD") || "", end: end?.format("YYYY-MM-DD") || "", limit: 0, group_by_day: groupByDay,
      direction: directionFilter, verdict: verdictFilter, extraction_status: statusFilter,
      saved_only: savedOnly,
    } }).then((r) => {
      setItems(r.data?.items || []);
      setSummary(r.data?.summary || null);
      setHasMore(!!r.data?.has_more);
    }).catch((e) => message.error(errMsg(e))).finally(() => setLoading(false));
  }

  function exportReview() {
    api.get("/api/bigv-review/export", { params: {
      user, start: start?.format("YYYY-MM-DD") || "", end: end?.format("YYYY-MM-DD") || "",
      direction: directionFilter, verdict: verdictFilter, extraction_status: statusFilter,
    }, responseType: "blob" }).then((response) => {
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "bigv-review.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    }).catch((e) => message.error(errMsg(e, "导出失败")));
  }

  useEffect(() => {
    if (!reviewing || !reviewStatus || reviewStatus.running) return;
    setReviewing(false);
    if (reviewStatus.error) {
      message.error(reviewStatus.error);
      return;
    }
    load(true);
  }, [reviewing, reviewStatus]);

  function startReview() {
    if (loading || reviewing) return;
    setReviewing(true);
    api.post("/api/bigv-review/run", {
      user, start: start?.format("YYYY-MM-DD") || "", end: end?.format("YYYY-MM-DD") || "",
      limit: 0, group_by_day: groupByDay, direction: directionFilter,
      verdict: verdictFilter, extraction_status: statusFilter, refresh_partial: true,
    }).then((r) => {
      if (!r.data?.started) {
        setReviewing(false);
        if (r.data?.running) message.info("已有复盘任务正在运行");
      }
    }).catch((e) => {
      setReviewing(false);
      message.error(errMsg(e));
    });
  }

  function cancelReview() {
    const jobId = reviewStatus?.job_id;
    if (!jobId) return;
    api.post(`/api/bigv-review/run/${jobId}/cancel`).then(() => message.info("已请求取消复盘任务"))
      .catch((e) => message.error(errMsg(e, "取消失败")));
  }

  function retryReview() {
    setReviewing(true);
    api.post("/api/bigv-review/run/retry").then((r) => {
      if (!r.data?.started && r.data?.running) message.info("已有复盘任务正在运行");
    }).catch((e) => { setReviewing(false); message.error(errMsg(e, "重试失败")); });
  }

  const extract = () => api.post("/api/bigv-review/extract", {})
    .then((r) => message.success(`已提交 ${r.data?.count || 0} 篇文章的观点提取任务`))
    .catch((e) => message.error(errMsg(e)));
  const monthly = summary?.monthly ?? [];

  return (
    <Card size="small" title="大V观点与行情复盘">
      <Space wrap style={{ marginBottom: 8 }}>
        <Select allowClear placeholder="全部大V" style={{ width: 160 }} value={user || undefined}
          onChange={(v) => setUser(v || "")} options={users?.map((u) => ({ value: u.id, label: u.name }))} />
        <Segmented
          value={datePreset}
          onChange={(value) => {
            const next = value as DatePreset;
            setDatePreset(next);
            const dates = datesForPreset(next);
            setStart(dates[0]);
            setEnd(dates[1]);
          }}
          options={[{ label: "近7天", value: "7d" }, { label: "近30天", value: "30d" }, { label: "近90天", value: "90d" }, { label: "今年", value: "year" }, { label: "全部", value: "all" }, { label: "自定义", value: "custom" }]}
        />
        {datePreset === "custom" ? <DatePicker value={start} onChange={setStart} placeholder="开始日期" /> : null}
        {datePreset === "custom" ? <DatePicker value={end} onChange={setEnd} placeholder="结束日期" /> : null}
        <Button onClick={() => load(true)} loading={loading} disabled={reviewing || loading}>加载已有复盘</Button>
        <Button type="primary" onClick={startReview} loading={reviewing} disabled={reviewing || loading}>开始增量复盘</Button>
        {reviewing ? <Button danger onClick={cancelReview}>取消任务</Button> : null}
        {!reviewing && ["error", "canceled"].includes(reviewStatus?.status || "") ? <Button onClick={retryReview}>重试上次复盘</Button> : null}
        <Button icon={<DownloadOutlined />} onClick={exportReview} disabled={reviewing}>导出 CSV</Button>
        <Select allowClear placeholder="方向" style={{ width: 100 }} value={directionFilter || undefined} onChange={(v) => setDirectionFilter(v || "")} options={[{ value: "看多", label: "看多" }, { value: "看空", label: "看空" }]} />
        <Select allowClear placeholder="验证状态" style={{ width: 120 }} value={verdictFilter || undefined} onChange={(v) => setVerdictFilter(v || "")} options={["可验证", "部分可验证", "暂无行情", "待验证"].map((v) => ({ value: v, label: v }))} />
        <Select allowClear placeholder="观点状态" style={{ width: 110 }} value={statusFilter || undefined} onChange={(v) => setStatusFilter(v || "")} options={["ready", "pending", "error", "missing"].map((v) => ({ value: v, label: v }))} />
        <Checkbox checked={groupByDay} onChange={(e) => setGroupByDay(e.target.checked)}>按日合并文章</Checkbox>
        {isAdmin ? <Button onClick={extract}>补提取观点</Button> : null}
      </Space>
      {loading && !reviewing ? <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
        正在读取已保存的复盘结果，不会重新计算行情。
      </Typography.Text> : null}
      {!loading && !reviewing && !items.length ? <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
        当前条件下没有已保存的复盘结果；如需补算缺失文章，请点击“开始复盘”。
      </Typography.Text> : null}
      {reviewing ? <div style={{ marginBottom: 8 }}>
        <Progress
          percent={reviewStatus?.progress?.total ? Math.round((reviewStatus.progress.processed || 0) / reviewStatus.progress.total * 100) : 0}
          status="active"
          size="small"
        />
        <Typography.Text type="secondary">
          {reviewStatus?.progress?.processed || 0}/{reviewStatus?.progress?.total || "?"} 篇
          {reviewStatus?.progress?.reused ? `，复用 ${reviewStatus.progress.reused} 篇` : ""}
          {reviewStatus?.progress?.computed ? `，重新计算 ${reviewStatus.progress.computed} 篇` : ""}
          {reviewStatus?.log?.slice(-1)[0] ? ` · ${reviewStatus.log.slice(-1)[0]}` : " · 正在后台复盘，请稍候..."}
        </Typography.Text>
      </div> : null}
      {summary ? <Row gutter={[8, 8]} style={{ marginBottom: 10 }}>
        <Col xs={12} sm={6}><Statistic title={groupByDay ? "日期数" : "文章数"} value={summary.posts ?? 0} /><Typography.Text type="secondary">文章 {summary.article_total ?? summary.posts ?? 0}</Typography.Text></Col>
        <Col xs={12} sm={6}><Statistic title="可验证率" value={summary.verification_rate ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="1日平均收益" value={summary.windows?.["1"]?.average_return ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="5日平均收益" value={summary.windows?.["5"]?.average_return ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="20日平均收益" value={summary.windows?.["20"]?.average_return ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="60日平均收益" value={summary.windows?.["60"]?.average_return ?? "-"} suffix="%" /></Col>
      </Row> : null}
      {summary?.accuracy ? <Table
        size="small"
        pagination={false}
        style={{ marginBottom: 10 }}
        dataSource={["1", "3", "5", "7", "10", "20", "60", "120"].map((window) => ({ window, ...summary.accuracy[window] }))}
        rowKey="window"
        columns={[
          { title: "周期", dataIndex: "window", width: 70, render: (v: string) => `${v}日` },
          { title: "样本", dataIndex: "samples", width: 70 },
          { title: "方向正确率", dataIndex: "correct_rate", width: 110, render: (v: number | null) => v == null ? "-" : `${v}%` },
          { title: "平均收益", dataIndex: "average_return", width: 100, render: (v: number | null) => v == null ? "-" : `${v}%` },
          { title: "平均超额", dataIndex: "average_excess", width: 100, render: (v: number | null) => v == null ? "-" : `${v}%` },
          { title: "跑赢基准率", dataIndex: "benchmark_win_rate", width: 110, render: (v: number | null) => v == null ? "-" : `${v}%` },
          { title: "达标率", dataIndex: "target_hit_rate", width: 90, render: (v: number | null) => v == null ? "-" : `${v}%` },
        ]}
      /> : null}
      {summary?.rankings?.length ? <Table
        size="small"
        pagination={false}
        style={{ marginBottom: 10 }}
        title={() => "大 V 表现排名（按 20 日方向正确率）"}
        dataSource={summary.rankings}
        rowKey={(row: Record<string, any>) => String(row.user_id || row.user_name)}
        columns={[
          { title: "排名", width: 60, render: (_: unknown, _row: Record<string, any>, index: number) => index + 1 },
          { title: "大 V", dataIndex: "user_name", width: 140 },
          { title: "文章", dataIndex: "posts", width: 70 },
          { title: "标的", dataIndex: "targets", width: 70 },
          ...["1", "5", "20", "60"].map((window) => ({
            title: `${window}日正确率`, width: 100,
            render: (_: unknown, row: Record<string, any>) => row.accuracy?.[window]?.correct_rate == null ? "-" : `${row.accuracy[window].correct_rate}%`,
          })),
        ]}
      /> : null}
      {monthly.length > 1 ? <ReactECharts
        style={{ height: 280, marginBottom: 10 }}
        option={{
          tooltip: { trigger: "axis" },
          legend: { data: ["1日平均收益", "5日平均收益", "20日方向正确率"] },
          xAxis: { type: "category", data: monthly.map((item: Record<string, any>) => item.month) },
          yAxis: [{ type: "value", name: "收益率 %" }, { type: "value", name: "正确率 %", min: 0, max: 100 }],
          series: [
            { name: "1日平均收益", type: "line", data: monthly.map((item: Record<string, any>) => item.windows?.["1"]?.average_return) },
            { name: "5日平均收益", type: "line", data: monthly.map((item: Record<string, any>) => item.windows?.["5"]?.average_return) },
            { name: "20日方向正确率", type: "line", yAxisIndex: 1, data: monthly.map((item: Record<string, any>) => item.windows?.["20"]?.correct_rate) },
          ],
        }}
      /> : null}
      {hasMore ? <Typography.Text type="warning" style={{ display: "block", marginBottom: 8 }}>结果已达到当前查询限制，请缩小日期范围或按大V查询。</Typography.Text> : null}
      <Table size="small" loading={loading} rowKey="id" pagination={{ pageSize: 10, hideOnSinglePage: true }} scroll={{ x: 900 }}
        dataSource={items}
        expandable={{ expandedRowRender: (record) => <Space direction="vertical" size={4} style={{ width: "100%" }}>
          {record.targets?.length ? <TargetPerformanceTable targets={record.targets} /> : null}
          {record.claims?.length ? record.claims.map((claim: Record<string, any>) => <OpinionClaimEditor key={claim.id} claim={claim} onSaved={load} editable={isAdmin} />)
            : <Typography.Text type="secondary">尚未完成观点提取，请点击“补提取观点”。</Typography.Text>}
        </Space> }}
        columns={[
          { title: "日期", dataIndex: "date", width: 100 },
          { title: "大V", dataIndex: "user_name", width: 120 },
          { title: "文章", width: 300, ellipsis: true, render: (_: unknown, r: Record<string, any>) => r.title || r.source_title || r.text?.split(/\r?\n/)[0]?.slice(0, 80) || "无标题文章" },
          { title: "方向", dataIndex: "direction", width: 80, render: (v: string) => <Tag color={v === "看多" ? "red" : v === "看空" ? "green" : "default"}>{v}</Tag> },
          { title: "标的", width: 280, render: (_: unknown, r: Record<string, any>) => r.targets?.length ? r.targets.map((t: Record<string, any>) => <TargetLink key={t.code} target={t} />) : "未识别" },
          { title: "验证", dataIndex: "verdict", width: 90 },
          { title: "短线 1/3/5日", width: 220, render: (_: unknown, r: Record<string, any>) => <TargetHorizonList targets={r.targets} windows={["1", "3", "5"]} /> },
          { title: "中线 7/10/20日", width: 230, render: (_: unknown, r: Record<string, any>) => <TargetHorizonList targets={r.targets} windows={["7", "10", "20"]} /> },
          { title: "长线 60/120日", width: 220, render: (_: unknown, r: Record<string, any>) => <TargetHorizonList targets={r.targets} windows={["60", "120"]} /> },
        ]}
      />
    </Card>
  );
}

function targetColor(direction?: string) {
  return direction === "看多" ? "#f5222d" : direction === "看空" ? "#52c41a" : undefined;
}

function TargetLink({ target }: { target: Record<string, any> }) {
  const color = targetColor(target.direction);
  return <Link to={`/stock/${target.code}`} style={{ color, marginRight: 8, whiteSpace: "nowrap" }}>
    {target.name}({target.code})
  </Link>;
}

function TargetHorizonList({ targets, windows }: { targets?: Array<Record<string, any>>; windows: string[] }) {
  if (!targets?.length) return <Typography.Text type="secondary">-</Typography.Text>;
  return <Space direction="vertical" size={2}>
    {targets.map((target) => <div key={target.code} style={{ color: targetColor(target.direction) }}>
      <Typography.Text strong><TargetLink target={target} /></Typography.Text>
      <Typography.Text type="secondary">：{windows.map((window) => {
        const value = target.performance?.[window];
        return `${window}日 ${target.quote_count === 0 ? "暂无" : value == null ? "未到期" : `${value}%`}`;
      }).join(" / ")}</Typography.Text>
    </div>)}
  </Space>;
}

function TargetPerformanceTable({ targets }: { targets: Array<Record<string, any>> }) {
  return <Table
    size="small"
    pagination={false}
    rowKey="code"
    dataSource={targets}
    scroll={{ x: 700 }}
    columns={[{
      title: "标的 / 方向",
      width: 150,
      render: (_: unknown, target: Record<string, any>) => <Typography.Text><TargetLink target={target} /> · <span style={{ color: targetColor(target.direction) }}>{target.direction || "未定向"}</span></Typography.Text>,
    }, ...["1", "3", "5", "7", "10", "20", "60", "120"].map((window) => ({
      title: `${window}日`,
      width: 130,
      render: (_: unknown, target: Record<string, any>) => {
        const value = target.performance?.[window];
        const excess = target.excess?.[window];
        return <Typography.Text style={{ color: value == null ? undefined : targetColor(target.direction) }}>
          {target.quote_count === 0 ? "暂无行情" : value == null ? "未到期" : <>{value}% <Typography.Text type="secondary">(超额 {excess ?? "-"}%)</Typography.Text></>}
        </Typography.Text>;
      },
    }))]}
  />;
}

function OpinionClaimEditor({ claim, onSaved, editable }: { claim: Record<string, any>; onSaved: () => void; editable: boolean }) {
  const [code, setCode] = useState(String(claim.code || ""));
  const [name, setName] = useState(String(claim.name || ""));
  const [ignored, setIgnored] = useState(Boolean(claim.ignored));
  const [options, setOptions] = useState<Array<{ value: string; label: string; code: string }>>([]);
  const [saving, setSaving] = useState(false);

  const searchStocks = (value: string) => {
    setName(value);
    if (value.trim().length < 2) return setOptions([]);
    api.get("/api/stock/search", { params: { q: value.trim(), limit: 20 } })
      .then((r) => setOptions((r.data?.items || []).map((item: { code: string; name: string }) => ({ value: item.name, label: `${item.name} (${item.code})`, code: item.code }))))
      .catch(() => setOptions([]));
  };
  const save = () => {
    const normalizedCode = code.trim();
    if (normalizedCode && !/^\d{6}$/.test(normalizedCode)) return message.error("股票代码必须是 6 位数字");
    setSaving(true);
    api.patch(`/api/bigv-review/claim/${claim.id}`, { code: normalizedCode, name: name.trim() })
      .then((r) => {
        if (r.data?.updated) { message.success("观点标的已更新"); onSaved(); }
        else message.error(r.data?.error || "更新失败");
      })
      .catch((e) => message.error(errMsg(e))).finally(() => setSaving(false));
  };
  const toggleIgnored = (value: boolean) => {
    setIgnored(value);
    api.patch(`/api/bigv-review/claim/${claim.id}`, { ignored: value })
      .then((r) => {
        if (r.data?.updated) onSaved();
        else { setIgnored(!value); message.error(r.data?.error || "更新失败"); }
      })
      .catch((e) => { setIgnored(!value); message.error(errMsg(e)); });
  };
  return <Space direction="vertical" size={4} style={{ width: "100%" }}>
    <Typography.Text type="secondary">{claim.direction} · 置信度 {claim.confidence ?? "-"} · {claim.claim || "无观点摘要"}{claim.evidence ? `；证据：${claim.evidence}` : ""}</Typography.Text>
    {editable ? <Space size={8}><Switch size="small" checked={ignored} onChange={toggleIgnored} /><Typography.Text type="secondary">{ignored ? "已忽略，不纳入复盘" : "纳入复盘"}</Typography.Text></Space> : null}
    {editable ? <Space.Compact>
      <AutoComplete size="small" value={name} options={options} onSearch={searchStocks} onSelect={(value, option) => { setName(value); setCode(String(option.code || "")); }} style={{ minWidth: 220 }}>
        <Input placeholder="输入股票名称/代码" />
      </AutoComplete>
      <Input size="small" value={code} onChange={(e) => setCode(e.target.value)} placeholder="6位代码" maxLength={6} />
      <Button size="small" loading={saving} onClick={save}>确认映射</Button>
    </Space.Compact> : null}
  </Space>;
}
