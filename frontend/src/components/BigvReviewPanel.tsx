import {
  AutoComplete, Button, Card, Checkbox, Col, DatePicker, Input, Row, Select, Space, Statistic, Switch, Table, Tag, Typography, message,
} from "antd";
import type { Dayjs } from "dayjs";
import { useState } from "react";

import { api, errMsg, getToken } from "@/api/client";
import { useUsers } from "@/api/hooks";

export default function BigvReviewPanel() {
  const isAdmin = !!getToken();
  const { data: users } = useUsers();
  const [user, setUser] = useState("");
  const [start, setStart] = useState<Dayjs | null>(null);
  const [end, setEnd] = useState<Dayjs | null>(null);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<Array<Record<string, any>>>([]);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);
  const [groupByDay, setGroupByDay] = useState(true);

  const load = () => {
    setLoading(true);
    api.get("/api/bigv-review", { params: {
      user, start: start?.format("YYYY-MM-DD") || "", end: end?.format("YYYY-MM-DD") || "", limit: 200, group_by_day: groupByDay,
    } }).then((r) => {
      setItems(r.data?.items || []);
      setSummary(r.data?.summary || null);
    }).catch((e) => message.error(errMsg(e))).finally(() => setLoading(false));
  };

  const extract = () => api.post("/api/bigv-review/extract", {})
    .then((r) => message.success(`已提交 ${r.data?.count || 0} 篇文章的观点提取任务`))
    .catch((e) => message.error(errMsg(e)));

  return (
    <Card size="small" title="大V观点与行情复盘">
      <Space wrap style={{ marginBottom: 8 }}>
        <Select allowClear placeholder="全部大V" style={{ width: 160 }} value={user || undefined}
          onChange={(v) => setUser(v || "")} options={users?.map((u) => ({ value: u.id, label: u.name }))} />
        <DatePicker value={start} onChange={setStart} placeholder="开始日期" />
        <DatePicker value={end} onChange={setEnd} placeholder="结束日期" />
        <Button type="primary" onClick={load} loading={loading}>开始复盘</Button>
        <Checkbox checked={groupByDay} onChange={(e) => setGroupByDay(e.target.checked)}>按日合并文章</Checkbox>
        {isAdmin ? <Button onClick={extract}>补提取观点</Button> : null}
      </Space>
      {summary ? <Row gutter={[8, 8]} style={{ marginBottom: 10 }}>
        <Col xs={12} sm={6}><Statistic title={groupByDay ? "日期数" : "文章数"} value={summary.posts ?? 0} /><Typography.Text type="secondary">文章 {summary.article_total ?? summary.posts ?? 0}</Typography.Text></Col>
        <Col xs={12} sm={6}><Statistic title="可验证率" value={summary.verification_rate ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="1日平均收益" value={summary.windows?.["1"]?.average_return ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="5日平均收益" value={summary.windows?.["5"]?.average_return ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="20日平均收益" value={summary.windows?.["20"]?.average_return ?? "-"} suffix="%" /></Col>
        <Col xs={12} sm={6}><Statistic title="60日平均收益" value={summary.windows?.["60"]?.average_return ?? "-"} suffix="%" /></Col>
      </Row> : null}
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
          { title: "标的", width: 280, render: (_: unknown, r: Record<string, any>) => r.targets?.map((t: Record<string, any>) => <Typography.Text key={t.code} style={{ color: targetColor(t.direction), marginRight: 8 }}>{t.name}({t.code})</Typography.Text>) || "未识别" },
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

function TargetHorizonList({ targets, windows }: { targets?: Array<Record<string, any>>; windows: string[] }) {
  if (!targets?.length) return <Typography.Text type="secondary">-</Typography.Text>;
  return <Space direction="vertical" size={2}>
    {targets.map((target) => <div key={target.code} style={{ color: targetColor(target.direction) }}>
      <Typography.Text strong style={{ color: targetColor(target.direction) }}>{target.name}</Typography.Text>
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
      render: (_: unknown, target: Record<string, any>) => <Typography.Text style={{ color: targetColor(target.direction) }}>{target.name} ({target.code}) · {target.direction || "未定向"}</Typography.Text>,
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
