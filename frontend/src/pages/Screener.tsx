import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import {
  Button, Card, Checkbox, Empty, Input, InputNumber, Select, Space, Table, Tag, Typography, message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const TAG_COLLAPSE_LIMIT = 6;
// 大V最近看好的板块/概念用红框描出来，跟"大V看好"列的 volcano 色呼应，其余保持原色底不填充。
const BULLISH_TAG_STYLE = { border: "1px solid #ff4d4f" };

function CollapsibleTags({ items, bullish, color }: { items?: string[]; bullish?: string[]; color?: string }) {
  const [expanded, setExpanded] = useState(false);
  if (!items?.length) return <>-</>;
  const shown = expanded ? items : items.slice(0, TAG_COLLAPSE_LIMIT);
  const hiddenCount = items.length - shown.length;
  const bullishSet = new Set(bullish);
  return (
    <Space size={[4, 4]} wrap>
      {shown.map((s) => (
        <Tag key={s} color={color} style={bullishSet.has(s) ? BULLISH_TAG_STYLE : undefined}>{s}</Tag>
      ))}
      {hiddenCount > 0 && (
        <Tag style={{ cursor: "pointer" }} onClick={() => setExpanded(true)}>+{hiddenCount}</Tag>
      )}
      {expanded && items.length > TAG_COLLAPSE_LIMIT && (
        <Tag style={{ cursor: "pointer" }} onClick={() => setExpanded(false)}>收起</Tag>
      )}
    </Space>
  );
}

import { errMsg } from "@/api/client";
import { useScreen, useScreenFields, useSectors, useUsers } from "@/api/hooks";
import type { ScreenBody } from "@/api/hooks";
import type { Condition, StockRow } from "@/api/types";
import { usePageContext } from "@/pageContext";
import { screenerState } from "./screenerState";
import { fmtNum, fmtPct, fmtYi, pctClass } from "@/util";

const PRESETS = [
  { value: "ma_cross", label: "严格买点：金叉+站上MA20+多头排列+5日涨幅>3%（主板）" },
  { value: "ma_cross2", label: "宽松买点：金叉+5日涨幅>3%（剔除科创板）" },
  { value: "golden_cross", label: "金叉买点：近4日MACD金叉≥1次 且 KDJ金叉≥1次" },
  { value: "fund_ok", label: "基本面达标：净利润/EPS/ROE/营收/毛利率" },
];
const OPS = [">", ">=", "<", "<=", "==", "!="];

export default function Screener() {
  const { data: fields } = useScreenFields();
  const { data: sectors } = useSectors();
  const { data: users } = useUsers();
  const screen = useScreen();

  // 初始值取自 screenerState 这个模块级单例——从 /stock/:code 返回时能接得上上次的筛选和结果，
  // 不用每次都重新勾一遍条件、重新点一次筛选。
  const [strategies, setStrategies] = useState<string[]>(screenerState.strategies);
  const [conds, setConds] = useState<Condition[]>(screenerState.conds);
  const [nameQuery, setNameQuery] = useState(screenerState.nameQuery);
  const [mentionOn, setMentionOn] = useState(screenerState.mentionOn);
  const [mentionDays, setMentionDays] = useState(screenerState.mentionDays);
  const [mentionUsers, setMentionUsers] = useState<string[]>(screenerState.mentionUsers);
  const [mentionBullishOnly, setMentionBullishOnly] = useState(screenerState.mentionBullishOnly);
  const [sectorOn, setSectorOn] = useState(screenerState.sectorOn);
  const [sectorMode, setSectorMode] = useState(screenerState.sectorMode);
  const [sectorNames, setSectorNames] = useState<string[]>(screenerState.sectorNames);

  const [rows, setRows] = useState<StockRow[]>(screenerState.rows);
  const [tradeDate, setTradeDate] = useState<string | null>(screenerState.tradeDate);

  usePageContext(
    `用户在"选股"页。已选策略：${strategies.length ? strategies.join("、") : "无"}；` +
    `${mentionOn ? `只看大V提及（${mentionDays}天内${mentionBullishOnly ? "，只看多" : ""}，${mentionUsers.length ? mentionUsers.length + "位大V" : "全部大V"}）；` : ""}` +
    `${sectorOn ? `只看板块（${sectorMode === "bullish" ? "大V看多的板块" : sectorNames.join("、") || "未选"}）；` : ""}` +
    (rows.length
      ? `筛出 ${rows.length} 只（行情日 ${tradeDate}），前几只：${rows.slice(0, 8).map((r) => r.name || r.code).join("、")}。`
      : "还没有筛选结果。"),
  );

  // 组件还活着的每一次变化都同步写回单例，下次重新 mount 时就能读到最新的
  useEffect(() => {
    Object.assign(screenerState, {
      strategies, conds, nameQuery, mentionOn, mentionDays, mentionUsers, mentionBullishOnly,
      sectorOn, sectorMode, sectorNames, rows, tradeDate,
    });
  }, [strategies, conds, nameQuery, mentionOn, mentionDays, mentionUsers, mentionBullishOnly,
    sectorOn, sectorMode, sectorNames, rows, tradeDate]);

  const addCond = () => setConds([...conds, { field: "change_pct", op: ">", value: 0 }]);
  const setCond = (i: number, patch: Partial<Condition>) =>
    setConds(conds.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  const delCond = (i: number) => setConds(conds.filter((_, idx) => idx !== i));

  const run = () => {
    const body: ScreenBody = { strategies, conditions: conds, name_query: nameQuery, limit: 300 };
    if (mentionOn) {
      body.mentioned = { enabled: true, days: mentionDays, user_ids: mentionUsers, bullish_only: mentionBullishOnly };
    }
    if (sectorOn) body.sector = { enabled: true, mode: sectorMode, names: sectorNames, days: mentionDays, user_ids: mentionUsers };
    screen.mutate(body, {
      onSuccess: (d) => { setRows(d.items); setTradeDate(d.trade_date); },
      onError: (e) => message.error(errMsg(e)),
    });
  };

  const columns: ColumnsType<StockRow> = [
    { title: "名称", dataIndex: "name", fixed: "left", width: 110,
      render: (n: string, r) => <Link to={`/stock/${r.code}`}>{n || r.code}</Link> },
    { title: "代码", dataIndex: "code", width: 90 },
    { title: "所属板块", dataIndex: "sectors", width: 200,
      render: (secs: string[] | undefined, r) => <CollapsibleTags items={secs} bullish={r.bullish_sectors} /> },
    { title: "概念题材", dataIndex: "concepts", width: 200,
      render: (cs: string[] | undefined, r) => <CollapsibleTags items={cs} bullish={r.bullish_concepts} color="purple" /> },
    { title: "最新价", dataIndex: "close", width: 90, render: (v) => fmtNum(v) },
    { title: "涨跌幅", dataIndex: "change_pct", width: 90,
      render: (v) => <span className={pctClass(v)}>{fmtPct(v)}</span>,
      sorter: (a, b) => (Number(a.change_pct) || 0) - (Number(b.change_pct) || 0) },
    { title: "换手率", dataIndex: "turnover_rate", width: 90, render: (v) => fmtNum(v) },
    { title: "市盈率", dataIndex: "pe_ttm", width: 90, render: (v) => fmtNum(v) },
    { title: "市净率", dataIndex: "pb", width: 80, render: (v) => fmtNum(v) },
    { title: "总市值", dataIndex: "total_mv", width: 100, render: (v) => fmtYi(v) },
    { title: "ROE", dataIndex: "roe", width: 80, render: (v) => (v == null ? "-" : fmtNum(v)) },
    { title: "大V看好", dataIndex: "bullish_users", width: 160,
      render: (users?: string[]) => users?.length
        ? <Space size={[4, 4]} wrap>{users.map((u) => <Tag key={u} color="volcano">{u}</Tag>)}</Space>
        : "-" },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>选股</Typography.Title>

      <Card title="预设策略（可多选，取交集；不选也可以，靠下面的条件/提及/板块筛选）" size="small">
        <Checkbox.Group
          options={PRESETS} value={strategies}
          onChange={(v) => setStrategies(v as string[])}
          style={{ display: "flex", flexDirection: "column", gap: 6 }}
        />
      </Card>

      <Card title="筛选条件（与预设取交集）" size="small">
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input placeholder="股票名称/代码/缩写，如 茅台 / 600519 / GZMT" allowClear
            value={nameQuery} onChange={(e) => setNameQuery(e.target.value)} style={{ maxWidth: 360 }} />
          {conds.map((c, i) => (
            <Space key={i} wrap>
              <Select style={{ width: 140 }} value={c.field} onChange={(v) => setCond(i, { field: v })}
                options={fields?.map((f) => ({ value: f.field, label: f.label }))} />
              <Select style={{ width: 80 }} value={c.op} onChange={(v) => setCond(i, { op: v })}
                options={OPS.map((o) => ({ value: o, label: o }))} />
              <InputNumber value={c.value} onChange={(v) => setCond(i, { value: Number(v) })} />
              <Button icon={<DeleteOutlined />} type="text" danger onClick={() => delCond(i)} />
            </Space>
          ))}
          <Button icon={<PlusOutlined />} onClick={addCond} type="dashed">添加条件</Button>

          <Space wrap>
            <Checkbox checked={mentionOn} onChange={(e) => setMentionOn(e.target.checked)}>只看大V最近</Checkbox>
            <InputNumber min={1} value={mentionDays} onChange={(v) => setMentionDays(Number(v) || 7)} style={{ width: 70 }} />
            <span>天内提及</span>
            <Select mode="multiple" allowClear placeholder="全部大V（不选=全部）" style={{ minWidth: 220 }}
              value={mentionUsers} onChange={setMentionUsers} showSearch optionFilterProp="label"
              options={users?.map((u) => ({ value: u.id, label: u.name }))} />
            <Checkbox checked={mentionBullishOnly} onChange={(e) => setMentionBullishOnly(e.target.checked)}>
              只看大V看多
            </Checkbox>
          </Space>

          <Space wrap>
            <Checkbox checked={sectorOn} onChange={(e) => setSectorOn(e.target.checked)}>只看板块</Checkbox>
            <Select style={{ width: 160 }} value={sectorMode} onChange={setSectorMode}
              options={[{ value: "manual", label: "手动选择" }, { value: "bullish", label: "大V看多的板块" }]} />
            {sectorMode === "manual" && (
              <Select mode="multiple" allowClear placeholder="选择板块" style={{ minWidth: 280 }}
                value={sectorNames} onChange={setSectorNames} showSearch optionFilterProp="label"
                options={sectors?.map((s) => ({ value: s.name, label: `${s.name}${s.abbr ? " " + s.abbr : ""}` }))} />
            )}
          </Space>

          <Button type="primary" loading={screen.isPending} onClick={run}>开始筛选</Button>
        </Space>
      </Card>

      <Card size="small"
        title={`筛选结果${tradeDate ? `（行情日 ${tradeDate}）` : ""}`}
        extra={rows.length ? <Tag color="blue">{rows.length} 只</Tag> : null}
      >
        {rows.length ? (
          <Table<StockRow> rowKey="code" size="small" columns={columns} dataSource={rows}
            scroll={{ x: 1460 }} pagination={{ pageSize: 20, showSizeChanger: true }} />
        ) : <Empty description="设定条件后点击「开始筛选」" />}
      </Card>
    </Space>
  );
}
