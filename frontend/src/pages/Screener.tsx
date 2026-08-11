import {
  BulbOutlined, CheckCircleFilled, DeleteOutlined, FilterOutlined, PieChartOutlined, PlusOutlined, TeamOutlined,
} from "@ant-design/icons";
import {
  Button, Card, Checkbox, Collapse, Empty, Input, InputNumber, List, Modal, Segmented, Select, Space,
  Spin, Switch, Table, Tabs, Tag, Typography, message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useIsMobile } from "@/hooks/useIsMobile";

const TAG_COLLAPSE_LIMIT = 6;

function CollapsibleTags({ items, bullish, color }: { items?: string[]; bullish?: string[]; color?: string }) {
  const [expanded, setExpanded] = useState(false);
  if (!items?.length) return <>-</>;
  const shown = expanded ? items : items.slice(0, TAG_COLLAPSE_LIMIT);
  const hiddenCount = items.length - shown.length;
  const bullishSet = new Set(bullish);
  return (
    <Space size={[4, 4]} wrap>
      {shown.map((s) => (
        <Tag key={s} color={bullishSet.has(s) ? "purple" : color}>{s}</Tag>
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

import { errMsg, getToken, getVisitorToken } from "@/api/client";
import { useDeleteAdminSettingDefaults, useGenerateStockAiAnalysis, useSaveAdminSettingDefaults, useSaveUserSettings, useScreen, useScreenFields, useSectorRank, useSectors, useSettingsDefaults, useStockAiAnalysis, useUserSettings, useUsers } from "@/api/hooks";
import type { ScreenBody } from "@/api/hooks";
import type { Condition, SectorRankItem, StockRow } from "@/api/types";
import MarkdownContent from "@/components/MarkdownContent";
import { usePageContext } from "@/pageContext";
import { screenerState } from "./screenerState";
import type { CapFilter } from "./screenerState";
import { fmtNum, fmtPct, fmtYi, pctClass } from "@/util";

// ──────────────────────────────────────────────
// 板块行情 Tab
// ──────────────────────────────────────────────

function SectorRankTab({ onGotoScreener }: { onGotoScreener: () => void }) {
  const isMobile = useIsMobile();
  const { data, isLoading } = useSectorRank();
  const [kind, setKind] = useState<"industry" | "concept">("industry");
  const [q, setQ] = useState("");

  const items = useMemo(() => {
    const all = (data?.items || []).filter((it) => it.kind === kind);
    const query = q.trim();
    return query ? all.filter((it) => it.sector.includes(query)) : all;
  }, [data, kind, q]);

  const gotoMembers = (sector: string) => {
    Object.assign(screenerState, {
      strategies: [], conds: [], nameQuery: "",
      mentionOn: false, sectorOn: true, sectorMode: "manual", sectorNames: [sector],
    });
    onGotoScreener();
  };

  const columns: ColumnsType<SectorRankItem> = isMobile ? [
    { title: "板块", dataIndex: "sector",
      render: (name: string) => <a onClick={() => gotoMembers(name)}>{name}</a> },
    { title: "涨/跌", dataIndex: "up_count", width: 76,
      render: (_v, r) => <span style={{ fontSize: 12 }}><span className="up">{r.up_count}</span>/<span className="down">{r.down_count}</span></span> },
    { title: "平均涨幅", dataIndex: "avg_change_pct", width: 84,
      render: (v) => <span className={pctClass(v)}>{fmtPct(v)}</span>,
      sorter: (a, b) => (Number(a.avg_change_pct) || 0) - (Number(b.avg_change_pct) || 0),
      defaultSortOrder: "descend" },
  ] : [
    { title: "板块", dataIndex: "sector", width: 180,
      render: (name: string) => <a onClick={() => gotoMembers(name)}>{name}</a> },
    { title: "成分股数", dataIndex: "member_count", width: 90 },
    { title: "上涨", dataIndex: "up_count", width: 70, render: (v) => <span className="up">{v}</span> },
    { title: "下跌", dataIndex: "down_count", width: 70, render: (v) => <span className="down">{v}</span> },
    { title: "平均涨幅", dataIndex: "avg_change_pct", width: 100,
      render: (v) => <span className={pctClass(v)}>{fmtPct(v)}</span>,
      sorter: (a, b) => (Number(a.avg_change_pct) || 0) - (Number(b.avg_change_pct) || 0),
      defaultSortOrder: "descend" },
    { title: "市值加权涨幅", dataIndex: "mv_weighted_change_pct", width: 120,
      render: (v) => <span className={pctClass(v)}>{fmtPct(v)}</span>,
      sorter: (a, b) => (Number(a.mv_weighted_change_pct) || 0) - (Number(b.mv_weighted_change_pct) || 0) },
  ];

  return (
    <Card size="small">
      <Space wrap style={{ marginBottom: 12 }}>
        <Segmented value={kind} onChange={(v) => setKind(v as "industry" | "concept")}
          options={[{ label: "行业", value: "industry" }, { label: "概念题材", value: "concept" }]} />
        <Input placeholder="搜索板块名" allowClear value={q} onChange={(e) => setQ(e.target.value)}
          style={{ width: isMobile ? 150 : 200 }} />
        {data?.trade_date && <Tag color="blue">行情日 {data.trade_date}</Tag>}
      </Space>
      {items.length ? (
        <Table<SectorRankItem> rowKey="sector" size="small" columns={columns} dataSource={items}
          loading={isLoading} pagination={{ pageSize: 30, showSizeChanger: true }} />
      ) : <Empty description={isLoading ? "加载中" : "暂无数据"} />}
    </Card>
  );
}

// ──────────────────────────────────────────────
// 选股 Tab
// ──────────────────────────────────────────────

function StockCard({ row }: { row: StockRow }) {
  return (
    <Card size="small" style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <Space size={6}>
          <Link to={`/stock/${row.code}`} state={{ from: "screener" }} style={{ fontWeight: 600, fontSize: 15 }}>{row.name || row.code}</Link>
          <span style={{ color: "var(--text-secondary)", fontSize: 12 }}>{row.code}</span>
        </Space>
        <Space size={4}>
          <span className={pctClass(row.change_pct)} style={{ fontWeight: 600 }}>
            {fmtNum(row.close)} {fmtPct(row.change_pct)}
          </span>
          <StockAiAnalysisButton code={row.code} />
        </Space>
      </div>
      {(row.sectors?.length || row.concepts?.length) ? (
        <div style={{ marginBottom: 6 }}>
          <CollapsibleTags items={row.sectors} bullish={row.bullish_sectors} />
          {row.concepts?.length ? <CollapsibleTags items={row.concepts} bullish={row.bullish_concepts} color="cyan" /> : null}
        </div>
      ) : null}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "4px 8px",
        fontSize: 12, color: "var(--text-secondary)", marginBottom: row.bullish_users?.length ? 6 : 0,
      }}>
        <span>换手 <span style={{ color: "var(--text-primary)" }}>{fmtNum(row.turnover_rate)}</span></span>
        <span>PE <span style={{ color: "var(--text-primary)" }}>{fmtNum(row.pe_ttm)}</span></span>
        <span>PB <span style={{ color: "var(--text-primary)" }}>{fmtNum(row.pb)}</span></span>
        <span>市值 <span style={{ color: "var(--text-primary)" }}>{fmtYi(row.total_mv)}</span></span>
        <span>ROE <span style={{ color: "var(--text-primary)" }}>{row.roe == null ? "-" : fmtNum(row.roe)}</span></span>
      </div>
      {row.bullish_users?.length ? (
        <Space size={[4, 4]} wrap>
          {row.bullish_users.map((u) => <Tag key={u} color="volcano">{u}</Tag>)}
        </Space>
      ) : null}
    </Card>
  );
}

interface ParamField {
  key: string;
  label: string;
  default: number | boolean;
  type?: "bool";
  step?: number;
}

const PRESETS: { value: string; title: string; desc: string; params?: ParamField[] }[] = [
  {
    value: "ma_cross", title: "严格买点", desc: "金叉+站上MA20+多头排列+N日涨幅>阈值（主板）",
    params: [
      { key: "ma_fast", label: "快线周期", default: 5 },
      { key: "ma_mid", label: "中线周期", default: 10 },
      { key: "ma_slow", label: "慢线周期", default: 20 },
      { key: "cross_days", label: "金叉回望天数", default: 3 },
      { key: "rise_days", label: "涨幅统计天数", default: 5 },
      { key: "rise_pct", label: "涨幅阈值", default: 0.03, step: 0.01 },
      { key: "first_day", label: "仅首日出现", default: false, type: "bool" },
    ],
  },
  {
    value: "ma_cross2", title: "宽松买点", desc: "金叉+N日涨幅>阈值（剔除科创板）",
    params: [
      { key: "ma_fast", label: "快线周期", default: 5 },
      { key: "ma_mid", label: "中线周期", default: 10 },
      { key: "ma_slow", label: "慢线周期", default: 20 },
      { key: "cross_days", label: "金叉回望天数", default: 3 },
      { key: "rise_days", label: "涨幅统计天数", default: 5 },
      { key: "rise_pct", label: "涨幅阈值", default: 0.03, step: 0.01 },
      { key: "first_day", label: "仅首日出现", default: false, type: "bool" },
    ],
  },
  {
    value: "golden_cross", title: "金叉买点", desc: "近N日MACD金叉 且/或 KDJ金叉",
    params: [
      { key: "macd_fast", label: "MACD快线", default: 12 },
      { key: "macd_slow", label: "MACD慢线", default: 26 },
      { key: "macd_signal", label: "MACD信号线", default: 9 },
      { key: "kdj_window", label: "KDJ窗口", default: 9 },
      { key: "cross_days", label: "金叉回望天数", default: 4 },
      { key: "require_both", label: "要求MACD且KDJ同时", default: true, type: "bool" },
    ],
  },
  {
    value: "fund_ok", title: "基本面达标", desc: "净利润/EPS/ROE/营收/毛利率",
    params: [
      { key: "net_profit_yoy_min", label: "净利润同比>", default: 0, step: 1 },
      { key: "eps_min", label: "EPS>", default: 0.1, step: 0.1 },
      { key: "roe_min", label: "ROE(%)>", default: 3, step: 1 },
      { key: "revenue_yoy_min", label: "营收同比(%)>", default: 10, step: 1 },
      { key: "gross_margin_min", label: "毛利率(%)>", default: 10, step: 1 },
    ],
  },
  {
    value: "volume_breakout", title: "放量突破", desc: "突破N日最高价 且 成交量>均量×倍数",
    params: [
      { key: "breakout_days", label: "统计天数", default: 20 },
      { key: "volume_mult", label: "放量倍数", default: 1.5, step: 0.1 },
    ],
  },
  {
    value: "pullback_low_volume", title: "缩量回踩", desc: "近期曾放量上涨，现回踩均线附近且缩量",
    params: [
      { key: "lookback_days", label: "放量回看天数", default: 10 },
      { key: "ma_period", label: "均线周期", default: 20 },
      { key: "near_pct", label: "贴近均线幅度", default: 0.02, step: 0.01 },
      { key: "recent_days", label: "近期量能天数", default: 3 },
      { key: "avg_days", label: "均量统计天数", default: 20 },
      { key: "spike_mult", label: "放量判定倍数", default: 1.5, step: 0.1 },
      { key: "low_volume_mult", label: "缩量判定倍数", default: 0.7, step: 0.1 },
    ],
  },
  {
    value: "boll_breakout", title: "布林带收口突破", desc: "带宽收口后突破布林带上轨",
    params: [
      { key: "period", label: "布林带周期", default: 20 },
      { key: "mult", label: "标准差倍数", default: 2, step: 0.1 },
      { key: "squeeze_days", label: "收口统计天数", default: 60 },
      { key: "squeeze_pct", label: "收口分位阈值", default: 0.3, step: 0.05 },
    ],
  },
  {
    value: "rsi_oversold_bounce", title: "RSI超卖反弹", desc: "RSI从阈值下方回升到阈值上方且当日收阳",
    params: [
      { key: "period", label: "RSI周期", default: 14 },
      { key: "threshold", label: "超卖阈值", default: 30, step: 1 },
      { key: "lookback_days", label: "回看天数", default: 2 },
    ],
  },
  {
    value: "turnover_surge", title: "换手异动", desc: "换手率>阈值 且 涨幅在区间内（排除涨停）",
    params: [
      { key: "turnover_min", label: "换手率(%)>", default: 5, step: 0.5 },
      { key: "change_pct_min", label: "涨幅下限(%)", default: 4, step: 0.5 },
      { key: "change_pct_max", label: "涨幅上限(%)", default: 9.5, step: 0.5 },
    ],
  },
  {
    value: "volume_price_up", title: "量价齐升", desc: "连续N日成交量与收盘价同步递增",
    params: [{ key: "streak_days", label: "连续天数", default: 3 }],
  },
  {
    value: "sell_ma_death_cross", title: "MA死叉卖点", desc: "近N日MA5下穿MA10（趋势转弱信号）",
    params: [{ key: "cross_days", label: "死叉回望天数", default: 3 }],
  },
  {
    value: "sell_break_ma20", title: "跌破均线卖点", desc: "收盘价从均线上方下穿均线（止损信号）",
    params: [{ key: "ma_period", label: "均线周期", default: 20 }],
  },
  {
    value: "sell_rsi_overbought", title: "RSI超买回落", desc: "RSI从阈值上方回落到阈值下方（高位止盈）",
    params: [
      { key: "period", label: "RSI周期", default: 14 },
      { key: "threshold", label: "超买阈值", default: 70, step: 1 },
      { key: "lookback_days", label: "回看天数", default: 2 },
    ],
  },
  {
    value: "sell_high_volume_drop", title: "高位放量阴线", desc: "均线上方+阴线+成交量>均量×倍数（出货信号）",
    params: [
      { key: "ma_period", label: "均线周期", default: 20 },
      { key: "volume_lookback", label: "均量统计天数", default: 20 },
      { key: "volume_mult", label: "放量倍数", default: 1.5, step: 0.1 },
    ],
  },
];
const OPS = [">", ">=", "<", "<=", "==", "!="];

function StrategyParamPanel({
  fields, values, onChange,
}: { fields: ParamField[]; values: Record<string, number | boolean>; onChange: (key: string, v: number | boolean) => void }) {
  return (
    <div className="strategy-param-panel" onClick={(e) => e.stopPropagation()}>
      <Space wrap size={[12, 8]}>
        {fields.map((f) => (
          <Space key={f.key} size={4}>
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{f.label}</span>
            {f.type === "bool" ? (
              <Switch size="small" checked={Boolean(values[f.key] ?? f.default)}
                onChange={(v) => onChange(f.key, v)} />
            ) : (
              <InputNumber size="small" style={{ width: 80 }} step={f.step ?? 1}
                value={Number(values[f.key] ?? f.default)}
                onChange={(v) => onChange(f.key, Number(v))} />
            )}
          </Space>
        ))}
      </Space>
    </div>
  );
}

function StockAiAnalysisButton({ code }: { code: string }) {
  const [open, setOpen] = useState(false);
  const { data, isFetching } = useStockAiAnalysis(code, open);
  const gen = useGenerateStockAiAnalysis();

  return (
    <>
      <Button size="small" type="text" icon={<BulbOutlined />} onClick={(e) => { e.stopPropagation(); setOpen(true); }}>
        AI解读
      </Button>
      <Modal title={`AI综合解读 · ${code}`} open={open} onCancel={() => setOpen(false)} footer={null} width={640}>
        <Spin spinning={isFetching || gen.isPending}>
          {data?.generated || gen.data?.generated ? (
            <MarkdownContent className="markdown-body" html={gen.data?.html ?? data?.html ?? ""} />
          ) : (
            <Empty description="还没有生成过，点击下方按钮生成">
              <Button type="primary" onClick={() => gen.mutate(code, { onError: (e) => message.error(errMsg(e, "生成失败")) })}>
                生成解读
              </Button>
            </Empty>
          )}
          {(data?.generated || gen.data?.generated) && (
            <div style={{ marginTop: 12, textAlign: "right" }}>
              <Button size="small" loading={gen.isPending}
                onClick={() => gen.mutate(code, { onError: (e) => message.error(errMsg(e, "生成失败")) })}>
                重新生成
              </Button>
            </div>
          )}
        </Spin>
      </Modal>
    </>
  );
}

function ScreenerTab({ pendingRun, onRunDone }: { pendingRun: boolean; onRunDone: () => void }) {
  const isMobile = useIsMobile();
  const { data: fields } = useScreenFields();
  const { data: sectors } = useSectors();
  const { data: users } = useUsers();
  const screen = useScreen();
  const loc = useLocation();
  const nav = useNavigate();

  const isLoggedIn = !!(getToken() || getVisitorToken());
  const isAdmin = !!getToken();
  const { data: userSettingsData } = useUserSettings("screen_params", isLoggedIn);
  const { data: sysDefaultsData } = useSettingsDefaults("screen_params");
  const saveUserSettings = useSaveUserSettings();
  const saveAdminDefaults = useSaveAdminSettingDefaults();
  const deleteAdminDefaults = useDeleteAdminSettingDefaults();

  const [strategies, setStrategies] = useState<string[]>(screenerState.strategies);
  const [strategyParams, setStrategyParams] = useState<Record<string, Record<string, number | boolean>>>(
    screenerState.strategyParams,
  );
  const [paramsLoaded, setParamsLoaded] = useState(false);
  const [conds, setConds] = useState<Condition[]>(screenerState.conds);
  const [nameQuery, setNameQuery] = useState(screenerState.nameQuery);
  const [capFilter, setCapFilter] = useState<CapFilter>(screenerState.capFilter);
  const [mentionOn, setMentionOn] = useState(screenerState.mentionOn);
  const [mentionDays, setMentionDays] = useState(screenerState.mentionDays);
  const [mentionUsers, setMentionUsers] = useState<string[]>(screenerState.mentionUsers);
  const [mentionBullishOnly, setMentionBullishOnly] = useState(screenerState.mentionBullishOnly);
  const [sectorOn, setSectorOn] = useState(screenerState.sectorOn);
  const [sectorMode, setSectorMode] = useState(screenerState.sectorMode);
  const [sectorNames, setSectorNames] = useState<string[]>(screenerState.sectorNames);
  const [rows, setRows] = useState<StockRow[]>(screenerState.rows);
  const [tradeDate, setTradeDate] = useState<string | null>(screenerState.tradeDate);

  useEffect(() => {
    if (paramsLoaded) return;
    const value = (userSettingsData?.value ?? sysDefaultsData?.value) as
      | Record<string, Record<string, number | boolean>>
      | null
      | undefined;
    if (value && typeof value === "object") {
      setStrategyParams(value);
      setParamsLoaded(true);
    } else if (userSettingsData !== undefined && sysDefaultsData !== undefined) {
      setParamsLoaded(true);
    }
  }, [userSettingsData, sysDefaultsData, paramsLoaded]);

  usePageContext(
    `用户在"选股"页。已选策略：${strategies.length ? strategies.join("、") : "无"}；` +
    `${mentionOn ? `只看大V提及（${mentionDays}天内${mentionBullishOnly ? "，只看多" : ""}，${mentionUsers.length ? mentionUsers.length + "位大V" : "全部大V"}）；` : ""}` +
    `${sectorOn ? `只看板块/概念（${sectorMode === "bullish" ? "大V看多的板块/概念" : sectorNames.join("、") || "未选"}）；` : ""}` +
    (rows.length
      ? `筛出 ${rows.length} 只（行情日 ${tradeDate}），前几只：${rows.slice(0, 8).map((r) => r.name || r.code).join("、")}。`
      : "还没有筛选结果。"),
  );

  useEffect(() => {
    Object.assign(screenerState, {
      strategies, strategyParams, conds, nameQuery, capFilter, mentionOn, mentionDays, mentionUsers, mentionBullishOnly,
      sectorOn, sectorMode, sectorNames, rows, tradeDate,
    });
  }, [strategies, strategyParams, conds, nameQuery, capFilter, mentionOn, mentionDays, mentionUsers, mentionBullishOnly,
    sectorOn, sectorMode, sectorNames, rows, tradeDate]);

  const setStrategyParam = (strategyKey: string, paramKey: string, v: number | boolean) => {
    setStrategyParams((prev) => ({ ...prev, [strategyKey]: { ...prev[strategyKey], [paramKey]: v } }));
  };

  const handleSaveParams = () => {
    saveUserSettings.mutate(
      { key: "screen_params", value: strategyParams },
      {
        onSuccess: () => message.success("参数已保存"),
        onError: (e) => message.error(errMsg(e, "保存失败")),
      },
    );
  };

  const handleSaveAdminDefaults = () => {
    saveAdminDefaults.mutate(
      { key: "screen_params", value: strategyParams },
      {
        onSuccess: () => message.success("全局默认已更新"),
        onError: (e) => message.error(errMsg(e, "保存失败")),
      },
    );
  };

  const handleResetAdminDefaults = () => {
    deleteAdminDefaults.mutate("screen_params", {
      onSuccess: () => message.success("全局默认已恢复（重置为内置值）"),
      onError: (e) => message.error(errMsg(e, "重置失败")),
    });
  };

  const addCond = () => setConds([...conds, { field: "change_pct", op: ">", value: 0 }]);
  const setCond = (i: number, patch: Partial<Condition>) =>
    setConds(conds.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  const delCond = (i: number) => setConds(conds.filter((_, idx) => idx !== i));

  const run = () => {
    const activeParams: Record<string, Record<string, number | boolean>> = {};
    for (const s of strategies) {
      if (strategyParams[s] && Object.keys(strategyParams[s]).length) activeParams[s] = strategyParams[s];
    }
    const mvConds: Condition[] = [];
    if (capFilter === "small") {
      mvConds.push({ field: "total_mv", op: "<", value: 500000 });
    } else if (capFilter === "mid") {
      mvConds.push({ field: "total_mv", op: ">=", value: 500000 });
      mvConds.push({ field: "total_mv", op: "<", value: 2000000 });
    } else if (capFilter === "large") {
      mvConds.push({ field: "total_mv", op: ">=", value: 2000000 });
    }
    const body: ScreenBody = {
      strategies, conditions: [...conds, ...mvConds], name_query: nameQuery, limit: 300,
      strategy_params: Object.keys(activeParams).length ? activeParams : undefined,
    };
    if (mentionOn) {
      body.mentioned = { enabled: true, days: mentionDays, user_ids: mentionUsers, bullish_only: mentionBullishOnly };
    }
    if (sectorOn) body.sector = { enabled: true, mode: sectorMode, names: sectorNames, days: mentionDays, user_ids: mentionUsers };
    screen.mutate(body, {
      onSuccess: (d) => { setRows(d.items); setTradeDate(d.trade_date); },
      onError: (e) => message.error(errMsg(e)),
    });
  };

  // 从板块行情 Tab 点板块名跳转过来时自动跑一次筛选
  useEffect(() => {
    if (pendingRun) { run(); onRunDone(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingRun]);

  // 兼容旧的外部 navigate("/screener", { state: { autoRun: true } }) 跳转
  useEffect(() => {
    if ((loc.state as { autoRun?: boolean } | null)?.autoRun) {
      run();
      nav(loc.pathname, { replace: true, state: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const columns: ColumnsType<StockRow> = [
    { title: "名称", dataIndex: "name", fixed: "left", width: 110,
      render: (n: string, r) => <Link to={`/stock/${r.code}`} state={{ from: "screener" }}>{n || r.code}</Link> },
    { title: "代码", dataIndex: "code", width: 90 },
    { title: "所属板块", dataIndex: "sectors", width: 200,
      render: (secs: string[] | undefined, r) => <CollapsibleTags items={secs} bullish={r.bullish_sectors} /> },
    { title: "概念题材", dataIndex: "concepts", width: 200,
      render: (cs: string[] | undefined, r) => <CollapsibleTags items={cs} bullish={r.bullish_concepts} /> },
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
    { title: "", key: "ai", fixed: "right", width: 90,
      render: (_v, r) => <StockAiAnalysisButton code={r.code} /> },
  ];

  return (
    <Space direction="vertical" size={isMobile ? 12 : 16} style={{ width: "100%" }}>
      <Card title={isMobile ? "预设策略" : "预设策略（可多选，取交集；不选也可以，靠下面的条件/提及/板块筛选）"} size="small"
        extra={isLoggedIn && (
          <Space size={4}>
            <Button size="small" loading={saveUserSettings.isPending} onClick={handleSaveParams}>保存参数</Button>
            {isAdmin && (
              <>
                <Button size="small" type="primary" ghost loading={saveAdminDefaults.isPending} onClick={handleSaveAdminDefaults}>修改全局默认</Button>
                <Button size="small" danger loading={deleteAdminDefaults.isPending} onClick={handleResetAdminDefaults}>恢复默认</Button>
              </>
            )}
          </Space>
        )}
      >
        <div className="preset-grid">
          {PRESETS.map((p) => {
            const active = strategies.includes(p.value);
            return (
              <div
                key={p.value}
                className={`preset-card${active ? " active" : ""}`}
                onClick={() => setStrategies(
                  active ? strategies.filter((s) => s !== p.value) : [...strategies, p.value],
                )}
              >
                {active && <CheckCircleFilled className="preset-card-check" />}
                <div className="preset-card-title">{p.title}</div>
                <div className="preset-card-desc">{p.desc}</div>
                {active && p.params && (
                  <div onClick={(e) => e.stopPropagation()}>
                    <Collapse
                      size="small" ghost
                      defaultActiveKey={isMobile ? ["params"] : []}
                      items={[{
                        key: "params",
                        label: "参数（默认值即原策略行为）",
                        children: (
                          <StrategyParamPanel
                            fields={p.params}
                            values={strategyParams[p.value] ?? {}}
                            onChange={(k, v) => setStrategyParam(p.value, k, v)}
                          />
                        ),
                      }]}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <Card title={isMobile ? "筛选条件" : "筛选条件（与预设取交集）"} size="small">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Input placeholder="股票名称/代码/缩写，如 茅台 / 600519 / GZMT" allowClear
            value={nameQuery} onChange={(e) => setNameQuery(e.target.value)} style={{ maxWidth: 360 }} />

          <div className="filter-section">
            <div className="filter-section-title">市值规模</div>
            <Segmented
              value={capFilter}
              onChange={(v) => setCapFilter(v as CapFilter)}
              options={[
                { label: "不限", value: "all" },
                { label: "小盘 (<50亿)", value: "small" },
                { label: "中盘 (50-200亿)", value: "mid" },
                { label: "大盘 (>200亿)", value: "large" },
              ]}
            />
          </div>

          <div className="filter-section">
            <div className="filter-section-title"><FilterOutlined /> 数值条件</div>
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
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
            </Space>
          </div>

          <div className="filter-section">
            <div className="filter-section-title"><TeamOutlined /> 大V提及</div>
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
          </div>

          <div className="filter-section">
            <div className="filter-section-title"><PieChartOutlined /> 板块/概念</div>
            <Space wrap>
              <Checkbox checked={sectorOn} onChange={(e) => setSectorOn(e.target.checked)}>只看板块/概念</Checkbox>
              <Select style={{ width: 160 }} value={sectorMode} onChange={setSectorMode}
                options={[{ value: "manual", label: "手动选择" }, { value: "bullish", label: "大V看多的板块/概念" }]} />
              {sectorMode === "manual" && (
                <Select mode="multiple" allowClear placeholder="选择行业/概念" style={{ minWidth: 280 }}
                  value={sectorNames} onChange={setSectorNames} showSearch optionFilterProp="label"
                  options={sectors?.map((s) => ({ value: s.name, label: `${s.name}${s.abbr ? " " + s.abbr : ""}` }))} />
              )}
            </Space>
          </div>

          <Button type="primary" size="large" loading={screen.isPending} onClick={run} block={isMobile}>
            开始筛选
          </Button>
        </Space>
      </Card>

      <Card size="small"
        title={`筛选结果${tradeDate ? `（行情日 ${tradeDate}）` : ""}`}
        extra={rows.length ? <Tag color="blue">{rows.length} 只</Tag> : null}
      >
        {rows.length ? (
          isMobile ? (
            <List<StockRow>
              dataSource={rows}
              pagination={{ pageSize: 20, size: "small" }}
              renderItem={(row) => <StockCard row={row} />}
            />
          ) : (
            <Table<StockRow> rowKey="code" size="small" columns={columns} dataSource={rows}
              scroll={{ x: 1550 }} pagination={{ pageSize: 20, showSizeChanger: true }} />
          )
        ) : <Empty description="设定条件后点击「开始筛选」" />}
      </Card>
    </Space>
  );
}

// ──────────────────────────────────────────────
// 选股主页（板块行情 + 选股两 Tab）
// ──────────────────────────────────────────────

export default function Screener() {
  const isMobile = useIsMobile();
  const [activeTab, setActiveTab] = useState("screener");
  const [pendingRun, setPendingRun] = useState(false);

  const handleGotoScreener = () => {
    setActiveTab("screener");
    setPendingRun(true);
  };

  return (
    <Space direction="vertical" size={0} style={{ width: "100%" }}>
      <Typography.Title level={isMobile ? 5 : 4} style={{ margin: "0 0 12px" }}>选股</Typography.Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size={isMobile ? "small" : "middle"}
        destroyInactiveTabPane
        items={[
          { key: "sectors", label: "板块行情", children: <SectorRankTab onGotoScreener={handleGotoScreener} /> },
          { key: "screener", label: "选股", children: <ScreenerTab pendingRun={pendingRun} onRunDone={() => setPendingRun(false)} /> },
        ]}
      />
    </Space>
  );
}
