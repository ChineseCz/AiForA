import { CalendarOutlined, FileTextOutlined, FireOutlined, TeamOutlined } from "@ant-design/icons";
import {
  Alert, Card, Col, Empty, InputNumber, List, Row, Segmented, Select,
  Space, Spin, Tag, Tooltip, Typography,
} from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useIndexKline, useOverview, useQuote, useUsers } from "@/api/hooks";
import type { BullishHeatBoard, BullishHeatItem, KlineBar } from "@/api/types";
import { useIsMobile } from "@/hooks/useIsMobile";
import { usePageContext } from "@/pageContext";
import { useThemeMode } from "@/theme";
import { screenerState } from "./screenerState";
import { fmtNum, fmtPct, pctClass } from "@/util";

// ──────────────────────────────────────────────
// 工具组件
// ──────────────────────────────────────────────

/** 前3名金银铜徽章，其余小号灰字排名 */
function RankBadge({ rank }: { rank: number }) {
  const medals = ["🥇", "🥈", "🥉"];
  if (rank <= 3) {
    return (
      <span style={{ fontSize: 20, lineHeight: 1, minWidth: 24, display: "inline-block", textAlign: "center" }}>
        {medals[rank - 1]}
      </span>
    );
  }
  return (
    <span style={{
      color: "#aaa", fontSize: 12, fontWeight: 600,
      minWidth: 24, display: "inline-block", textAlign: "center",
    }}>
      {rank}
    </span>
  );
}

/** 热度进度条（相对第1名的宽度比例，右侧显示绝对数量） */
function HeatBar({ value, max, color = "#ff4d4f", unit = "只" }: { value: number; max: number; color?: string; unit?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        flex: 1, maxWidth: 260, height: 6, borderRadius: 3,
        background: "var(--ant-color-fill-tertiary, #f0f0f0)",
        overflow: "hidden",
      }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width .4s" }} />
      </div>
      <span style={{ fontSize: 11, color: "#999", minWidth: 32, textAlign: "right" }}>{value}{unit}</span>
    </div>
  );
}

/** 大V名字Tag，点击跳转到 AI 总结页 */
function UserTag({ name, nameToId }: { name: string; nameToId: Map<string, string> }) {
  const navigate = useNavigate();
  const uid = nameToId.get(name);
  if (!uid) return <Tag key={name}>{name}</Tag>;
  return (
    <Tooltip title="查看 AI 总结" key={name}>
      <Tag
        style={{ cursor: "pointer" }}
        color="geekblue"
        onClick={() => navigate("/feed", { state: { userId: uid } })}
      >
        {name}
      </Tag>
    </Tooltip>
  );
}

// ──────────────────────────────────────────────
// 热度榜：个股 Tab
// ──────────────────────────────────────────────
function StockHeatList({
  items, isLoading, daysLabel, nameToId, page, onPageChange,
}: {
  items: BullishHeatItem[];
  isLoading: boolean;
  daysLabel: string;
  nameToId: Map<string, string>;
  page: number;
  onPageChange: (p: number) => void;
}) {
  const HEAT_PAGE_SIZE = 8;
  const maxCount = items[0]?.bullish_count ?? 1;

  if (!items.length) {
    return <Empty description={isLoading ? "加载中" : `${daysLabel}暂无大V看多判定`} />;
  }
  return (
    <List<BullishHeatItem>
      dataSource={items}
      pagination={{ pageSize: HEAT_PAGE_SIZE, size: "small", hideOnSinglePage: true, current: page, onChange: onPageChange }}
      renderItem={(it, i) => {
        const rank = (page - 1) * HEAT_PAGE_SIZE + i + 1;
        const pct = maxCount > 0 ? Math.round((it.bullish_count / maxCount) * 100) : 0;
        return (
          <List.Item style={{ padding: "6px 0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
              <RankBadge rank={rank} />
              <Link to={`/stock/${it.code}`} style={{ fontWeight: 600, fontSize: 14, whiteSpace: "nowrap" }}>{it.name}</Link>
              {it.close != null && (
                <span className={pctClass(it.change_pct)} style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                  {fmtNum(it.close)}&nbsp;{fmtPct(it.change_pct)}
                </span>
              )}
              {/* 进度条 */}
              <div style={{ flex: 1, minWidth: 40, maxWidth: 180, height: 5, borderRadius: 3, background: "var(--ant-color-fill-tertiary, #333)", overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: "#ff4d4f", borderRadius: 3, transition: "width .4s" }} />
              </div>
              <span style={{ fontSize: 11, color: "#ff7043", whiteSpace: "nowrap", fontWeight: 600 }}>🔥{it.bullish_count}位</span>
              <span style={{ fontSize: 11, color: "#888", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 200 }}>
                {it.bullish_users.map((u, idx) => {
                  const id = nameToId.get(u);
                  return (
                    <span key={u}>
                      {idx > 0 && <span style={{ margin: "0 2px", color: "#555" }}>·</span>}
                      {id
                        ? <Link to={`/summary/${id}`} style={{ color: "#888", fontSize: 11 }}>{u}</Link>
                        : <span>{u}</span>
                      }
                    </span>
                  );
                })}
              </span>
            </div>
          </List.Item>
        );
      }}
    />
  );
}

// ──────────────────────────────────────────────
// 热度榜：行业 / 概念 Tab
// ──────────────────────────────────────────────
function BoardHeatList({
  boards, isLoading, daysLabel, kind, nameToId, page, onPageChange,
}: {
  boards: BullishHeatBoard[];
  isLoading: boolean;
  daysLabel: string;
  kind: "industry" | "concept";
  nameToId: Map<string, string>;
  page: number;
  onPageChange: (p: number) => void;
}) {
  const navigate = useNavigate();
  const HEAT_PAGE_SIZE = 6;
  const filtered = boards.filter((b) => b.kind === kind);
  const maxCount = filtered[0]?.bullish_stock_count ?? 1;

  const goScreener = (sectorName: string) => {
    Object.assign(screenerState, {
      sectorOn: true,
      sectorMode: "manual",
      sectorNames: [sectorName],
      strategies: [],
      conds: [],
      nameQuery: "",
    });
    navigate("/screen", { state: { autoRun: true } });
  };

  if (!filtered.length) {
    return <Empty description={isLoading ? "加载中" : `${daysLabel}暂无${kind === "industry" ? "行业" : "概念"}数据`} />;
  }
  return (
    <List<BullishHeatBoard>
      dataSource={filtered}
      pagination={{ pageSize: HEAT_PAGE_SIZE, size: "small", hideOnSinglePage: true, current: page, onChange: onPageChange }}
      renderItem={(it, i) => {
        const rank = (page - 1) * HEAT_PAGE_SIZE + i + 1;
        return (
          <List.Item style={{ padding: "10px 0" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10, width: "100%" }}>
              <div style={{ paddingTop: 2 }}><RankBadge rank={rank} /></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <Space wrap size={[6, 4]} style={{ marginBottom: 4 }}>
                  <Tooltip title="点击筛选该板块">
                    <Typography.Text
                      strong
                      style={{ fontSize: 14, cursor: "pointer", color: "var(--ant-color-primary)" }}
                      onClick={() => goScreener(it.sector)}
                    >
                      {it.sector} ↗
                    </Typography.Text>
                  </Tooltip>
                  <Tag color="volcano" style={{ marginInlineEnd: 0 }}>🔥 {it.bullish_stock_count} 只股票</Tag>
                  <Tag>{it.bullish_user_count} 位大V</Tag>
                </Space>
                <HeatBar value={it.bullish_stock_count} max={maxCount} color="#722ed1" />
                <Space size={[4, 4]} wrap style={{ marginTop: 6 }}>
                  {it.bullish_stocks.map((s) => (
                    <Tag key={s.code} color="default">
                      <Link to={`/stock/${s.code}`}>{s.name}</Link>
                    </Tag>
                  ))}
                </Space>
                <Space size={[4, 4]} wrap style={{ marginTop: 4 }}>
                  {it.bullish_users.map((u) => (
                    <UserTag key={u} name={u} nameToId={nameToId} />
                  ))}
                </Space>
              </div>
            </div>
          </List.Item>
        );
      }}
    />
  );
}

// ──────────────────────────────────────────────
// 大盘指数日线图（仿股票详情页画法，副图可收起）
// ──────────────────────────────────────────────

const UP_COLOR = "#f43f5e";
const DOWN_COLOR = "#22c55e";

const INDEX_SIGNALS = [
  { key: "strict_ok" as const,          name: "严格买点",     color: "#e64545", dir: "buy" as const },
  { key: "loose_ok" as const,           name: "宽松买点",     color: "#3b82f6", dir: "buy" as const },
  { key: "golden_ok" as const,          name: "金叉买点",     color: "#06b6d4", dir: "buy" as const },
  { key: "volume_breakout_ok" as const, name: "放量突破",     color: "#84cc16", dir: "buy" as const },
  { key: "boll_breakout_ok" as const,   name: "布林带突破",   color: "#a855f7", dir: "buy" as const },
  { key: "rsi_bounce_ok" as const,      name: "RSI超卖反弹",  color: "#f59e0b", dir: "buy" as const },
  { key: "mid_reverse_ok" as const,     name: "趋势下跌",     color: "#f97316", dir: "sell" as const },
  { key: "stop_loss_ok" as const,       name: "短期止损",     color: "#8b5cf6", dir: "sell" as const },
  { key: "rsi_overbought_ok" as const,  name: "RSI超买回落",  color: "#ec4899", dir: "sell" as const },
  { key: "break_ma_ok" as const,        name: "跌破均线止损", color: "#f43f5e", dir: "sell" as const },
  { key: "high_vol_drop_ok" as const,   name: "高位放量阴线", color: "#dc2626", dir: "sell" as const },
];
const IDX_BUY_KEYS = INDEX_SIGNALS.filter((s) => s.dir === "buy").map((s) => s.key);
const IDX_SELL_KEYS = INDEX_SIGNALS.filter((s) => s.dir === "sell").map((s) => s.key);
const IDX_STACK_PX = 13;

function buildIndexOption(
  bars: KlineBar[], dark: boolean, showVol: boolean, showMacd: boolean, showKdj: boolean,
  zoom?: { start: number; end: number },
) {
  const dates = bars.map((b) => b.trade_date);
  const axisColor = dark ? "#9aa3ad" : "#666";
  const lineColor = dark ? "#3c3c3c" : "#ddd";
  const splitLine = { lineStyle: { color: dark ? "#2a2e33" : "#f0f0f0" } };

  const MAIN_H = 200;
  const SUB_H = 76;
  const GAP = 6;
  const TOP = 76;

  const subKeys = [
    showVol && "vol", showMacd && "macd", showKdj && "kdj",
  ].filter(Boolean) as string[];

  const grids: { top: number; height: number }[] = [{ top: TOP, height: MAIN_H }];
  let y = TOP + MAIN_H + GAP;
  for (let i = 0; i < subKeys.length; i++) {
    grids.push({ top: y, height: SUB_H });
    y += SUB_H + GAP;
  }
  const volIdx = subKeys.indexOf("vol") >= 0 ? subKeys.indexOf("vol") + 1 : -1;
  const macdIdx = subKeys.indexOf("macd") >= 0 ? subKeys.indexOf("macd") + 1 : -1;
  const kdjIdx = subKeys.indexOf("kdj") >= 0 ? subKeys.indexOf("kdj") + 1 : -1;

  const eGrids = grids.map((g) => ({ left: 56, right: 12, top: g.top, height: g.height }));
  const xAxes = grids.map((_, i) => ({
    type: "category" as const, data: dates, gridIndex: i, boundaryGap: false,
    axisLabel: i === grids.length - 1 ? { color: axisColor, fontSize: 10, rotate: 30 } : { show: false },
    axisLine: { lineStyle: { color: lineColor } },
    axisTick: { show: false },
    splitLine: { show: false },
    axisPointer: { label: { show: i === grids.length - 1 } },
  }));
  const yAxes = grids.map((_, i) => ({
    type: "value" as const, gridIndex: i, scale: true,
    axisLabel: {
      color: axisColor, fontSize: 10,
      formatter: i === volIdx ? (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}亿` : v >= 1e4 ? `${(v / 1e4).toFixed(0)}万` : String(v)) : undefined,
    },
    axisLine: { show: false }, axisTick: { show: false }, splitLine,
  }));

  const signalSeries = INDEX_SIGNALS.map((s) => {
    const order = s.dir === "buy" ? IDX_BUY_KEYS.indexOf(s.key) : IDX_SELL_KEYS.indexOf(s.key);
    const pxOffset = (order + 1) * IDX_STACK_PX * (s.dir === "buy" ? 1 : -1);
    return {
      name: s.name,
      type: "scatter",
      xAxisIndex: 0,
      yAxisIndex: 0,
      symbol: s.dir === "sell" ? "path://M 0 5 L -6 -5 L 6 -5 Z" : "triangle",
      symbolSize: s.dir === "sell" ? 11 : 10,
      symbolRotate: 0,
      symbolOffset: [0, pxOffset],
      itemStyle: { color: s.color },
      tooltip: { show: false },
      z: 6,
      data: bars
        .map((b, i) => (b[s.key] ? [i, s.dir === "buy" ? (b.low ?? b.close) : (b.high ?? b.close)] : null))
        .filter(Boolean) as [number, number][],
    };
  });

  const series: Record<string, unknown>[] = [
    {
      type: "candlestick", name: "指数", xAxisIndex: 0, yAxisIndex: 0,
      data: bars.map((b) => [b.open, b.close, b.low, b.high]),
      itemStyle: { color: UP_COLOR, color0: DOWN_COLOR, borderColor: UP_COLOR, borderColor0: DOWN_COLOR },
    },
    ...(["ma5", "ma10", "ma20"] as const).map((key, i) => ({
      type: "line", name: key.toUpperCase(), xAxisIndex: 0, yAxisIndex: 0,
      data: bars.map((b) => b[key]), symbol: "none", smooth: false,
      lineStyle: { width: 1, color: ["#f59e0b", "#60a5fa", "#a78bfa"][i] },
    })),
    ...signalSeries,
  ];

  if (volIdx >= 0) {
    series.push({
      type: "bar", name: "成交量", xAxisIndex: volIdx, yAxisIndex: volIdx,
      data: bars.map((b) => ({ value: b.volume, itemStyle: { color: b.close >= b.open ? UP_COLOR : DOWN_COLOR } })),
    });
  }
  if (macdIdx >= 0) {
    series.push(
      { type: "line", name: "DIF", xAxisIndex: macdIdx, yAxisIndex: macdIdx, data: bars.map((b) => b.dif), symbol: "none", lineStyle: { width: 1, color: "#60a5fa" } },
      { type: "line", name: "DEA", xAxisIndex: macdIdx, yAxisIndex: macdIdx, data: bars.map((b) => b.dea), symbol: "none", lineStyle: { width: 1, color: "#f97316" } },
      { type: "bar", name: "MACD", xAxisIndex: macdIdx, yAxisIndex: macdIdx, data: bars.map((b) => ({ value: b.macd, itemStyle: { color: b.macd >= 0 ? UP_COLOR : DOWN_COLOR } })) },
    );
  }
  if (kdjIdx >= 0) {
    series.push(
      { type: "line", name: "K", xAxisIndex: kdjIdx, yAxisIndex: kdjIdx, data: bars.map((b) => b.k), symbol: "none", lineStyle: { width: 1, color: "#f59e0b" } },
      { type: "line", name: "D", xAxisIndex: kdjIdx, yAxisIndex: kdjIdx, data: bars.map((b) => b.d), symbol: "none", lineStyle: { width: 1, color: "#60a5fa" } },
      { type: "line", name: "J", xAxisIndex: kdjIdx, yAxisIndex: kdjIdx, data: bars.map((b) => b.j), symbol: "none", lineStyle: { width: 1, color: "#a78bfa" } },
    );
  }

  const zoomStart = zoom?.start ?? Math.max(0, 100 - (90 / Math.max(1, bars.length)) * 100);
  const zoomEnd = zoom?.end ?? 100;
  const allIdx = grids.map((_, i) => i);
  const lStyle = { fontSize: 11, color: dark ? "#c9c9c9" : "#333" };

  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: {
      trigger: "axis",
      triggerOn: "none",
      axisPointer: { type: "cross" },
      showContent: false,
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    legend: [
      {
        id: "basic",
        data: ["指数", "MA5", "MA10", "MA20"],
        top: 4, left: 0, right: 0, textStyle: lStyle,
      },
      {
        id: "buy",
        data: INDEX_SIGNALS.filter((s) => s.dir === "buy").map((s) => s.name),
        selected: Object.fromEntries(INDEX_SIGNALS.filter((s) => s.dir === "buy").map((s) => [s.name, true])),
        type: "scroll", show: true, top: 28, left: 9999, textStyle: lStyle,
      },
      {
        id: "sell",
        data: INDEX_SIGNALS.filter((s) => s.dir === "sell").map((s) => ({
          name: s.name, icon: "path://M 0 5 L -6 -5 L 6 -5 Z",
        })),
        selected: Object.fromEntries(INDEX_SIGNALS.filter((s) => s.dir === "sell").map((s) => [s.name, true])),
        type: "scroll", show: true, top: 52, left: 9999, textStyle: lStyle,
      },
    ],
    grid: eGrids,
    xAxis: xAxes,
    yAxis: yAxes,
    series,
    dataZoom: [
      { type: "inside", xAxisIndex: allIdx, start: zoomStart, end: zoomEnd, preventDefaultMouseMove: false, zoomRate: 0.3 },
      {
        type: "slider", xAxisIndex: allIdx, bottom: 6, height: 18, start: zoomStart, end: zoomEnd,
        textStyle: { color: axisColor, fontSize: 9 },
        handleStyle: { color: dark ? "#5b6779" : "#aaa" },
        fillerColor: dark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.04)",
      },
    ],
  };
}

// 顶部指标条：仿 StockDetail InfoBar，MA 颜色与 buildIndexOption 一致
function IndexInfoBar({ bar, prevClose }: { bar: KlineBar; prevClose?: number }) {
  const pct = prevClose ? ((bar.close - prevClose) / prevClose) * 100 : 0;
  const pctColor = pct > 0 ? UP_COLOR : pct < 0 ? DOWN_COLOR : undefined;
  const cells = [
    { label: "日期", value: bar.trade_date },
    { label: "开盘", value: fmtNum(bar.open) },
    { label: "收盘", value: fmtNum(bar.close) },
    { label: "涨跌幅", value: `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`, color: pctColor },
    { label: "最高", value: fmtNum(bar.high) },
    { label: "最低", value: fmtNum(bar.low) },
    { label: "MA5",  value: fmtNum(bar.ma5),  color: "#f59e0b" },
    { label: "MA10", value: fmtNum(bar.ma10), color: "#60a5fa" },
    { label: "MA20", value: fmtNum(bar.ma20), color: "#a78bfa" },
  ];
  return (
    <div className="stock-infobar">
      {cells.map((c) => (
        <span key={c.label} className="cell">
          <span className="label">{c.label}</span>
          <span className="value" style={c.color ? { color: c.color } : undefined}>{c.value}</span>
        </span>
      ))}
    </div>
  );
}

// 副图左上角小字标注，位置对齐 buildIndexOption 的动态 grid
const IDX_SUB_TOP0 = 76 + 200 + 6 + 4; // main_top + main_h + gap + label_offset
const IDX_SUB_STEP = 76 + 6;           // sub_h + gap

function IndexSubLabels({
  bar, showVol, showMacd, showKdj,
}: { bar: KlineBar; showVol: boolean; showMacd: boolean; showKdj: boolean }) {
  let y = IDX_SUB_TOP0;
  const items: { key: string; top: number; node: ReactNode }[] = [];
  if (showVol) {
    items.push({
      key: "vol", top: y,
      node: <>成交量 <span style={{ color: bar.close >= bar.open ? UP_COLOR : DOWN_COLOR }}>{Number(bar.volume ?? 0).toLocaleString()} 手</span></>,
    });
    y += IDX_SUB_STEP;
  }
  if (showMacd) {
    items.push({
      key: "macd", top: y,
      node: <>DIF <span style={{ color: "#60a5fa" }}>{fmtNum(bar.dif)}</span>{" "}DEA <span style={{ color: "#f97316" }}>{fmtNum(bar.dea)}</span>{" "}MACD <span style={{ color: (bar.macd ?? 0) >= 0 ? UP_COLOR : DOWN_COLOR }}>{fmtNum(bar.macd)}</span></>,
    });
    y += IDX_SUB_STEP;
  }
  if (showKdj) {
    items.push({
      key: "kdj", top: y,
      node: <>K <span style={{ color: "#f59e0b" }}>{fmtNum(bar.k)}</span>{" "}D <span style={{ color: "#60a5fa" }}>{fmtNum(bar.d)}</span>{" "}J <span style={{ color: "#a78bfa" }}>{fmtNum(bar.j)}</span></>,
    });
  }
  return (
    <>
      {items.map((it) => (
        <div key={it.key} style={{
          position: "absolute", left: 60, top: it.top, fontSize: 11,
          color: "var(--text-secondary)", pointerEvents: "none", whiteSpace: "nowrap",
        }}>
          {it.node}
        </div>
      ))}
    </>
  );
}

const INDICES = [
  { code: "sh000001", label: "上证" },
  { code: "sz399001", label: "深证" },
  { code: "sz399006", label: "创业板" },
  { code: "sh000300", label: "沪深300" },
];

function IndexChart({ dark, isMobile }: { dark: boolean; isMobile: boolean }) {
  const [selectedCode, setSelectedCode] = useState("sh000001");
  const [period, setPeriod] = useState<"day" | "week" | "month">("day");
  const { data, isLoading } = useIndexKline(selectedCode, period);
  const { data: quote } = useQuote(selectedCode);
  const [showVol, setShowVol] = useState(true);
  const [showMacd, setShowMacd] = useState(false);
  const [showKdj, setShowKdj] = useState(false);
  const [buyExpanded, setBuyExpanded] = useState(false);
  const [sellExpanded, setSellExpanded] = useState(false);
  const chartRef = useRef<ReactECharts>(null);
  const zoomRef = useRef<{ start: number; end: number } | undefined>(undefined);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [chartReady, setChartReady] = useState(false);

  // 与个股详情页保持一致：前端合并实时报价
  // - 日期相同（收盘后历史接口已包含当日）：覆盖最后一根 bar 的 OHLCV
  // - 日期不同且 quote 更新（盘中/盘前当日无历史 bar）：追加一根今日 bar
  const bars = useMemo(() => {
    const raw = data?.bars ?? [];
    if (period !== "day" || !quote || quote.error || !raw.length) return raw;
    const last = raw[raw.length - 1];
    if (last.trade_date === quote.trade_date) {
      // 同一天：覆盖 OHLCV
      const merged = {
        ...last,
        close: quote.close,
        high: Math.max(last.high, quote.high),
        low: Math.min(last.low, quote.low),
        volume: quote.volume ?? last.volume,
      };
      return [...raw.slice(0, -1), merged];
    }
    if (quote.trade_date > last.trade_date) {
      // 新交易日：历史接口还没有今日 bar，追加一根（指标字段置 null/false）
      const todayBar: KlineBar = {
        trade_date: quote.trade_date,
        open: quote.open ?? quote.close,
        high: quote.high ?? quote.close,
        low: quote.low ?? quote.close,
        close: quote.close,
        volume: quote.volume ?? 0,
        ma5: null, ma10: null, ma20: null,
        dif: 0, dea: 0, macd: 0,
        k: 0, d: 0, j: 0,
        strict_ok: false, loose_ok: false, golden_ok: false,
        mid_reverse_ok: false, stop_loss_ok: false,
        volume_breakout_ok: false, boll_breakout_ok: false,
        rsi_bounce_ok: false, rsi_overbought_ok: false,
        break_ma_ok: false, high_vol_drop_ok: false,
      };
      return [...raw, todayBar];
    }
    return raw;
  }, [data, period, quote]);

  const activeIdx = hoverIdx != null && bars[hoverIdx] ? hoverIdx : bars.length - 1;
  const active = bars[activeIdx];
  const prevClose = activeIdx > 0 ? bars[activeIdx - 1]?.close : undefined;

  // 近14根 bar 内有中期反转信号，提示趋势偏弱
  const trendWeak = bars.length > 0 && bars.slice(-14).some((b) => b.mid_reverse_ok);

  const option = useMemo(
    () => (bars.length ? buildIndexOption(bars, dark, showVol, showMacd, showKdj, zoomRef.current) : {}),
    [bars, dark, showVol, showMacd, showKdj],
  );
  const height = 76 + 200 + 30 /* dataZoom */
    + (showVol ? 82 : 0) + (showMacd ? 82 : 0) + (showKdj ? 82 : 0);

  const toggleBuy = () => {
    const inst = chartRef.current?.getEchartsInstance();
    if (!inst) return;
    const newShow = !buyExpanded;
    inst.setOption({ legend: [{}, { id: "buy", left: newShow ? 54 : 9999 }] });
    setBuyExpanded(newShow);
  };

  const toggleSell = () => {
    const inst = chartRef.current?.getEchartsInstance();
    if (!inst) return;
    const newShow = !sellExpanded;
    inst.setOption({ legend: [{}, {}, { id: "sell", left: newShow ? 54 : 9999 }] });
    setSellExpanded(newShow);
  };

  const onEvents = useMemo(() => ({
    datazoom: (e: { start?: number; end?: number; batch?: { start?: number; end?: number }[] }) => {
      const item = e?.batch?.[0] ?? e;
      if (typeof item.start === "number" && typeof item.end === "number") {
        zoomRef.current = { start: item.start, end: item.end };
      }
    },
    updateAxisPointer: (e: { axesInfo?: { value?: number }[] }) => {
      const v = e?.axesInfo?.[0]?.value;
      if (typeof v === "number" && v >= 0 && v < bars.length) setHoverIdx(v);
    },
    globalout: () => setHoverIdx(null),
  }), [bars.length]);

  // 长按 0.5s 进入十字光标模式，松手退出；桌面鼠标移动直接跟随
  useEffect(() => {
    const inst = chartRef.current?.getEchartsInstance();
    if (!inst || !chartReady) return;
    const zr = inst.getZr();
    const HOLD_MS = 500;
    const MOVE_TOLERANCE = 10;
    let isTouchDown = false;
    let armed = false;
    let startX = 0, startY = 0, lastX = 0, lastY = 0;
    let timer: number | null = null;
    let lastTouchEnd = 0;
    let crosshairHidden = false;

    const clearTimer = () => { if (timer != null) { window.clearTimeout(timer); timer = null; } };
    const showAt = (x: number, y: number) => {
      if (crosshairHidden) { inst.setOption({ tooltip: { axisPointer: { type: "cross" } } }); crosshairHidden = false; }
      inst.dispatchAction({ type: "showTip", x, y });
    };
    const setPanDisabled = (v: boolean) => inst.setOption({ dataZoom: [{ disabled: v }] });
    const hide = () => {
      inst.setOption({ tooltip: { axisPointer: { type: "none" } } });
      crosshairHidden = true;
      setHoverIdx(null);
    };

    const onDown = (e: { offsetX: number; offsetY: number; zrByTouch?: boolean }) => {
      if (!e.zrByTouch) return;
      isTouchDown = true; armed = false;
      startX = lastX = e.offsetX; startY = lastY = e.offsetY;
      clearTimer();
      timer = window.setTimeout(() => { armed = true; setPanDisabled(true); showAt(lastX, lastY); }, HOLD_MS);
    };
    const onMove = (e: { offsetX: number; offsetY: number; zrByTouch?: boolean }) => {
      if (!e.zrByTouch) {
        if (Date.now() - lastTouchEnd < 200) return;
        showAt(e.offsetX, e.offsetY);
        return;
      }
      lastX = e.offsetX; lastY = e.offsetY;
      if (!isTouchDown) return;
      if (armed) { showAt(lastX, lastY); return; }
      if (Math.abs(e.offsetX - startX) > MOVE_TOLERANCE || Math.abs(e.offsetY - startY) > MOVE_TOLERANCE) clearTimer();
    };
    const onUp = () => {
      const wasTouch = isTouchDown;
      isTouchDown = false;
      if (armed) setPanDisabled(false);
      armed = false; clearTimer();
      if (wasTouch) lastTouchEnd = Date.now();
      hide();
    };

    zr.on("mousedown", onDown);
    zr.on("mousemove", onMove);
    zr.on("mouseup", onUp);
    zr.on("globalout", onUp);
    return () => {
      clearTimer();
      zr.off("mousedown", onDown);
      zr.off("mousemove", onMove);
      zr.off("mouseup", onUp);
      zr.off("globalout", onUp);
    };
  }, [bars.length, chartReady]);

  return (
    <Card
      title={
        <Space wrap size={[8, 4]}>
          <Segmented
            size="small"
            value={selectedCode}
            onChange={(v) => setSelectedCode(v as string)}
            options={INDICES.map((i) => ({ label: i.label, value: i.code }))}
          />
          <Segmented
            size="small"
            value={period}
            onChange={(v) => setPeriod(v as "day" | "week" | "month")}
            options={[{ label: "日线", value: "day" }, { label: "周线", value: "week" }, { label: "月线", value: "month" }]}
          />
        </Space>
      }
      style={{ marginTop: isMobile ? 8 : 16 }}
      extra={
        <Space size={4}>
          <Tag.CheckableTag checked={showVol} onChange={setShowVol}>量</Tag.CheckableTag>
          <Tag.CheckableTag checked={showMacd} onChange={setShowMacd}>MACD</Tag.CheckableTag>
          <Tag.CheckableTag checked={showKdj} onChange={setShowKdj}>KDJ</Tag.CheckableTag>
        </Space>
      }
    >
      {trendWeak && (
        <Alert
          type="warning"
          showIcon
          message="大盘近14个交易日出现中期反转信号，趋势偏弱，注意风险"
          style={{ marginBottom: 8 }}
          closable
        />
      )}
      {isLoading ? (
        <Spin />
      ) : bars.length ? (
        <>
          {active && <IndexInfoBar bar={active} prevClose={prevClose} />}
          <div style={{ position: "relative", marginTop: 8 }}>
            <ReactECharts
              ref={chartRef}
              option={option}
              style={{ height, touchAction: "pan-y" }}
              notMerge={false}
              onEvents={onEvents}
              onChartReady={() => setChartReady(true)}
            />
            {active && (
              <IndexSubLabels
                bar={active}
                showVol={showVol}
                showMacd={showMacd}
                showKdj={showKdj}
              />
            )}
            {(["buy", "sell"] as const).map((dir) => {
              const expanded = dir === "buy" ? buyExpanded : sellExpanded;
              const toggle = dir === "buy" ? toggleBuy : toggleSell;
              const top = dir === "buy" ? 28 : 52;
              return (
                <div
                  key={dir}
                  onClick={toggle}
                  style={{
                    position: "absolute", top, left: 4, zIndex: 10,
                    cursor: "pointer", userSelect: "none", fontSize: 11,
                    color: dark ? "#c9c9c9" : "#555",
                    background: dark ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.05)",
                    borderRadius: 3, padding: "1px 5px", lineHeight: "18px",
                  }}
                >
                  {dir === "buy" ? "买点" : "卖点"}{expanded ? "▲" : "▼"}
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <Empty description="暂无指数数据" />
      )}
    </Card>
  );
}

// ──────────────────────────────────────────────
// 主组件
// ──────────────────────────────────────────────

const DAY_OPTIONS = [
  { label: "今天", value: 1 },
  { label: "近3天", value: 3 },
  { label: "近7天", value: 7 },
  { label: "自定义", value: 0 },
];

// 分页页码用模块级缓存持久化：点股票跳转详情页再返回时，Dashboard 会重新挂载，
// useState 初始值会丢；从这里读初始值即可让页码在返回时保持原样。
const _heatPageCache = { stock: 1, board: 1 };

export default function Dashboard() {
  const [user, setUser] = useState<string | undefined>(undefined);
  const [heatTab, setHeatTab] = useState<"stock" | "industry" | "concept">("stock");
  const [dayPreset, setDayPreset] = useState<number>(7);
  const [customDays, setCustomDays] = useState<number>(14);
  const [stockPage, setStockPage] = useState(() => _heatPageCache.stock);
  const [boardPage, setBoardPage] = useState(() => _heatPageCache.board);
  const activeDays = dayPreset === 0 ? customDays : dayPreset;

  const handleStockPageChange = (p: number) => { _heatPageCache.stock = p; setStockPage(p); };
  const handleBoardPageChange = (p: number) => { _heatPageCache.board = p; setBoardPage(p); };

  // 筛选条件变了（大V/天数），数据集变了，页码归1；首次挂载（含从详情页返回）不归零，保持上次页码。
  const [filterKey, setFilterKey] = useState(() => `${user ?? ""}|${activeDays}`);
  useEffect(() => {
    const key = `${user ?? ""}|${activeDays}`;
    if (key === filterKey) return;
    setFilterKey(key);
    _heatPageCache.stock = 1;
    _heatPageCache.board = 1;
    setStockPage(1);
    setBoardPage(1);
  }, [user, activeDays, filterKey]);

  const { data: users } = useUsers();
  const { data, isLoading } = useOverview(user, activeDays);
  const { mode } = useThemeMode();
  const isMobile = useIsMobile();
  const dark = mode === "dark";
  const userName = users?.find((u) => u.id === user)?.name;

  const nameToId = useMemo<Map<string, string>>(() => {
    const m = new Map<string, string>();
    users?.forEach((u) => m.set(u.name, u.id));
    return m;
  }, [users]);

  const daysLabel = dayPreset === 1 ? "今天" : dayPreset === 0 ? `近${customDays}天` : `近${dayPreset}天`;

  usePageContext(
    data
      ? `用户在"看板"页。${userName ? `筛选大V：${userName}。` : "未筛选大V，看的是全站数据。"}` +
        `帖子总数 ${data.total}，大V数 ${data.user_count}，活跃天数 ${data.active_days}，` +
        `时间跨度 ${data.first} ~ ${data.last}。`
      : "用户在\"看板\"页，数据还在加载。",
  );

  const axisTextColor = dark ? "#9aa3ad" : "#666";

  const monthlyOpt = {
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 16, top: 20, bottom: 40 },
    xAxis: {
      type: "category", data: data?.monthly.map((m) => m.ym) ?? [],
      axisLabel: { rotate: 45, color: axisTextColor },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: axisTextColor },
      splitLine: { lineStyle: { color: dark ? "#2a2e33" : "#f0f0f0" } },
    },
    series: [{ type: "bar", data: data?.monthly.map((m) => m.n) ?? [], itemStyle: { color: "#1668dc" } }],
  };

  const days_data = data?.daily ?? [];
  const maxN = Math.max(1, ...days_data.map((d) => d.n));
  const years = Array.from(new Set(days_data.map((d) => d.date.slice(0, 4)))).sort();
  const calYear = years[years.length - 1] ?? new Date().getFullYear().toString();
  const levels = dark
    ? ["#1c2128", "#0d3a63", "#12508f", "#1668dc", "#5b9dff"]
    : ["#ebedf0", "#cfe3ff", "#8fbdfa", "#4c8ff0", "#1668dc"];
  const step = Math.max(1, Math.ceil(maxN / 4));
  const heatOpt = {
    tooltip: { formatter: (p: { value: [string, number] }) => `${p.value[0]}：${p.value[1]} 条` },
    visualMap: {
      show: false, type: "piecewise",
      pieces: [
        { min: 0, max: 0, color: levels[0] },
        { min: 1, max: step, color: levels[1] },
        { min: step + 1, max: step * 2, color: levels[2] },
        { min: step * 2 + 1, max: step * 3, color: levels[3] },
        { min: step * 3 + 1, color: levels[4] },
      ],
    },
    calendar: {
      range: calYear, cellSize: ["auto", 13], right: 16, left: 40, top: 30, bottom: 10,
      splitLine: { show: false },
      itemStyle: { borderWidth: 3, borderColor: "transparent", color: levels[0] },
      yearLabel: { show: false },
      monthLabel: { color: axisTextColor, fontSize: 11 },
      dayLabel: { color: axisTextColor, fontSize: 10, firstDay: 0 },
    },
    series: [{
      type: "heatmap", coordinateSystem: "calendar",
      data: days_data.filter((d) => d.date.startsWith(calYear)).map((d) => [d.date, d.n]),
    }],
  };


  return (
    <Spin spinning={isLoading}>
      {/* 顶部标题 + 大V 筛选 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 16, gap: 8 }}>
        <Typography.Title level={isMobile ? 4 : 3} style={{ margin: 0 }}>看板</Typography.Title>
        <Select
          allowClear placeholder="全部大V" style={{ width: isMobile ? 140 : 200 }} value={user}
          onChange={setUser}
          options={users?.map((u) => ({ value: u.id, label: u.name }))}
        />
      </Row>

      {/* 统计条 */}
      <Card styles={{ body: { padding: 0 } }}>
        <div className="stat-strip">
          <div className="stat-strip-item">
            <div className="stat-strip-icon" style={{ background: "#1668dc1a", color: "#1668dc" }}><FileTextOutlined /></div>
            <div>
              <div className="stat-strip-value">{data?.total ?? 0}</div>
              <div className="stat-strip-label">帖子总数</div>
            </div>
          </div>
          <div className="stat-strip-item">
            <div className="stat-strip-icon" style={{ background: "#722ed11a", color: "#722ed1" }}><TeamOutlined /></div>
            <div>
              <div className="stat-strip-value">{data?.user_count ?? 0}</div>
              <div className="stat-strip-label">大V数</div>
            </div>
          </div>
          <div className="stat-strip-item">
            <div className="stat-strip-icon" style={{ background: "#fa8c161a", color: "#fa8c16" }}><FireOutlined /></div>
            <div>
              <div className="stat-strip-value">{data?.active_days ?? 0}</div>
              <div className="stat-strip-label">活跃天数</div>
            </div>
          </div>
          <div className="stat-strip-item">
            <div className="stat-strip-icon" style={{ background: "#13c2c21a", color: "#13c2c2" }}><CalendarOutlined /></div>
            <div>
              <div className="stat-strip-value" style={{ fontSize: 14 }}>{data?.first ?? "-"} ~ {data?.last ?? "-"}</div>
              <div className="stat-strip-label">时间跨度</div>
            </div>
          </div>
        </div>
      </Card>

      {/* 热度榜 */}
      <Card
        style={{ marginTop: isMobile ? 8 : 16 }}
        styles={isMobile ? { header: { flexWrap: "wrap" } } : undefined}
        title={
          isMobile ? (
            <Space direction="vertical" size={8} style={{ width: "100%", padding: "8px 0" }}>
              <span>🔥 看多热度榜</span>
              <Space wrap size={[6, 6]}>
                <Segmented
                  size="small"
                  value={dayPreset}
                  onChange={(v) => setDayPreset(v as number)}
                  options={DAY_OPTIONS}
                />
                {dayPreset === 0 && (
                  <Space size={4}>
                    <InputNumber
                      size="small" min={1} max={90} value={customDays}
                      onChange={(v) => v && setCustomDays(v)}
                      style={{ width: 56 }}
                    />
                    <span style={{ fontSize: 12, color: "#888" }}>天</span>
                  </Space>
                )}
              </Space>
              <Segmented
                size="small"
                value={heatTab}
                onChange={(v) => setHeatTab(v as typeof heatTab)}
                options={[
                  { label: "个股", value: "stock" },
                  { label: "行业", value: "industry" },
                  { label: "概念", value: "concept" },
                ]}
              />
            </Space>
          ) : (
            <Space wrap size={[8, 8]}>
              <span>🔥 看多热度榜</span>
              <Segmented
                size="small"
                value={dayPreset}
                onChange={(v) => setDayPreset(v as number)}
                options={DAY_OPTIONS}
              />
              {dayPreset === 0 && (
                <Space size={4}>
                  <span style={{ fontSize: 12, color: "#888" }}>近</span>
                  <InputNumber
                    size="small" min={1} max={90} value={customDays}
                    onChange={(v) => v && setCustomDays(v)}
                    style={{ width: 56 }}
                  />
                  <span style={{ fontSize: 12, color: "#888" }}>天</span>
                </Space>
              )}
            </Space>
          )
        }
        extra={
          isMobile ? undefined : (
            <Segmented
              size="small"
              value={heatTab}
              onChange={(v) => setHeatTab(v as typeof heatTab)}
              options={[
                { label: "个股", value: "stock" },
                { label: "行业", value: "industry" },
                { label: "概念", value: "concept" },
              ]}
            />
          )
        }
      >
        {heatTab === "stock" && (
          <StockHeatList
            items={data?.bullish_heat ?? []}
            isLoading={isLoading}
            daysLabel={daysLabel}
            nameToId={nameToId}
            page={stockPage}
            onPageChange={handleStockPageChange}
          />
        )}
        {heatTab === "industry" && (
          <BoardHeatList
            boards={data?.bullish_heat_boards ?? []}
            isLoading={isLoading}
            daysLabel={daysLabel}
            kind="industry"
            nameToId={nameToId}
            page={boardPage}
            onPageChange={handleBoardPageChange}
          />
        )}
        {heatTab === "concept" && (
          <BoardHeatList
            boards={data?.bullish_heat_boards ?? []}
            isLoading={isLoading}
            daysLabel={daysLabel}
            kind="concept"
            nameToId={nameToId}
            page={boardPage}
            onPageChange={handleBoardPageChange}
          />
        )}
      </Card>

      {/* 图表区 */}
      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginTop: isMobile ? 8 : 16 }}>
        {!isMobile && (
          <Col xs={24} md={12}>
            <Card title="发帖热力（按天）">
              <div style={{ overflowX: "auto" }}>
                <div style={{ minWidth: 580 }}>
                  <ReactECharts option={heatOpt} style={{ height: 160 }} />
                </div>
              </div>
            </Card>
          </Col>
        )}
        <Col xs={24} md={12}>
          <Card title="月度发帖量">
            <ReactECharts option={monthlyOpt} style={{ height: isMobile ? 180 : 220 }} />
          </Card>
        </Col>
      </Row>

      {/* 大盘指数 */}
      <IndexChart dark={dark} isMobile={isMobile} />

      {/* 最新动态 */}
      <Card title="最新动态" style={{ marginTop: isMobile ? 8 : 16 }}>
        {data?.latest?.length ? (
          <List
            dataSource={data.latest}
            renderItem={(p) => (
              <List.Item
                style={isMobile ? { padding: "8px 0" } : undefined}
                extra={!isMobile && <a href={p.url} target="_blank" rel="noreferrer">原帖</a>}
              >
                <List.Item.Meta
                  title={
                    <Space wrap size={[4, 2]}>
                      <span style={{ fontWeight: 600 }}>{p.user_name}</span>
                      <span style={{ color: "#888", fontSize: 12 }}>{p.date}</span>
                      {p.title && <span>{p.title}</span>}
                      {isMobile && <a href={p.url} target="_blank" rel="noreferrer">原帖</a>}
                    </Space>
                  }
                  description={<div style={{ maxHeight: 44, overflow: "hidden", fontSize: 13, color: "#666" }}>{p.text}</div>}
                />
              </List.Item>
            )}
          />
        ) : <Empty description="暂无数据，请先在后台采集" />}
      </Card>
    </Spin>
  );
}
