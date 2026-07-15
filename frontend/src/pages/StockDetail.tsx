import { ArrowLeftOutlined, MobileOutlined } from "@ant-design/icons";
import { Button, Card, Col, Descriptions, Empty, List, Row, Space, Spin, Tag, Tooltip, Typography, message } from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { errMsg } from "@/api/client";
import { useFundamentals, useGenerateStockAiAnalysis, useKline, useNews, useQuote, useStockAiAnalysis } from "@/api/hooks";
import type { KlineBar } from "@/api/types";
import MarkdownContent from "@/components/MarkdownContent";
import { useIsMobile } from "@/hooks/useIsMobile";
import { usePageContext } from "@/pageContext";
import { useThemeMode } from "@/theme";
import { fmtNum, fmtYi } from "@/util";

// 买卖点信号：3 买(朝上、置于K线下方) + 2 卖(朝下、置于K线上方)，各一色，带图例
const SIGNALS = [
  { key: "strict_ok", name: "严格买点", color: "#e64545", dir: "buy" },
  { key: "loose_ok", name: "宽松买点", color: "#3b82f6", dir: "buy" },
  { key: "golden_ok", name: "金叉买点", color: "#06b6d4", dir: "buy" },
  { key: "mid_reverse_ok", name: "中期反转", color: "#f97316", dir: "sell" },
  { key: "stop_loss_ok", name: "短期止损", color: "#8b5cf6", dir: "sell" },
] as const;

const UP = "#e64545";   // A股惯例：红涨绿跌
const DOWN = "#2ba471";

// 新浪"新闻"资讯里一部分链接来自"新浪看点"域名，是给其 App 用的深链接跳转页——
// 部分手机系统浏览器（尤其国产定制ROM）打不开对应App时会短暂显示内容后跳转到404。
// 这不是我们能控制的（链接本身来自新浪），只能提示用户。
const DEEPLINK_NEWS_HOSTS = ["cj.sina.cn", "t.cj.sina.cn"];
function isDeepLinkNews(url: string): boolean {
  try {
    return DEEPLINK_NEWS_HOSTS.includes(new URL(url).hostname);
  } catch {
    return false;
  }
}

// 同一根K线可能同时命中多个买点/卖点信号。用固定像素 symbolOffset 把它们错开，
// 而不是按价格百分比偏移——后者在 dataZoom 缩放时 Y 轴范围会跟着变化，偏移量在屏幕上
// 忽大忽小，多个信号还会在同一根K线上重合到一起。
const BUY_KEYS = SIGNALS.filter((s) => s.dir === "buy").map((s) => s.key);
const SELL_KEYS = SIGNALS.filter((s) => s.dir === "sell").map((s) => s.key);
const STACK_STEP_PX = 13;

function buildOption(bars: KlineBar[], dark: boolean, compact: boolean) {
  const dates = bars.map((b) => b.trade_date);
  const candle = bars.map((b) => [b.open, b.close, b.low, b.high]);

  const signalSeries = SIGNALS.map((s) => {
    const order = s.dir === "buy" ? BUY_KEYS.indexOf(s.key) : SELL_KEYS.indexOf(s.key);
    const pxOffset = (order + 1) * STACK_STEP_PX * (s.dir === "buy" ? 1 : -1);
    return {
      name: s.name,
      type: "scatter",
      xAxisIndex: 0,
      yAxisIndex: 0,
      symbol: "triangle",
      symbolSize: 10,
      symbolRotate: s.dir === "sell" ? 180 : 0,
      symbolOffset: [0, pxOffset],
      itemStyle: { color: s.color },
      tooltip: { show: false },
      z: 6,
      data: bars
        .map((b, i) => (b[s.key] ? [i, s.dir === "buy" ? (b.low ?? b.close) : (b.high ?? b.close)] : null))
        .filter(Boolean) as [number, number][],
    };
  });

  const lineStyle = { width: 1 };
  const axisLabelColor = dark ? "#a6adb4" : "#666";
  const axisLineColor = dark ? "#3a3f45" : "#d9d9d9";
  const splitLineColor = dark ? "#2a2e33" : "#f0f0f0";
  const legendColor = dark ? "#c9c9c9" : "#333";
  const gridLeft = compact ? 40 : 52;
  const gridRight = compact ? 8 : 20;

  // 默认显示最近约1个月（22个交易日）；bars 不足22条时全显。
  const MONTH_BARS = 22;
  const defaultStart = bars.length > MONTH_BARS
    ? Math.round(((bars.length - MONTH_BARS) / bars.length) * 100)
    : 0;

  return {
    animation: false,
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    // 十字准星但不弹浮窗（showContent:false）；数值改由顶部表格展示。
    // triggerOn:"none" —— 关掉 echarts 自带的"碰一下/移过去就自动显示"，改成完全由我们手动
    // dispatchAction({type:'showTip'}) 驱动（见组件里的长按手势逻辑），这样才能真正做到
    // "触屏长按 2s 才出十字光标"；之前试过用 setOption 切 axisPointer.show 去压制自动触发，
    // 压不住——那是在跟 echarts 内部自己的显示逻辑抢时机，不如直接关掉自动触发。
    tooltip: { trigger: "axis", triggerOn: "none", axisPointer: { type: "cross" }, showContent: false },
    legend: {
      top: 4,
      data: ["K线", "MA5", "MA10", "MA20", ...SIGNALS.map((s) => s.name)],
      textStyle: { fontSize: compact ? 11 : 12, color: legendColor },
    },
    grid: [
      { left: gridLeft, right: gridRight, top: 40, height: "42%" },
      { left: gridLeft, right: gridRight, top: "50%", height: "12%" },
      { left: gridLeft, right: gridRight, top: "66%", height: "14%" },
      { left: gridLeft, right: gridRight, top: "83%", height: "14%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: axisLineColor } } },
      { type: "category", data: dates, gridIndex: 1, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: axisLineColor } } },
      { type: "category", data: dates, gridIndex: 2, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: axisLineColor } } },
      { type: "category", data: dates, gridIndex: 3, axisLabel: { fontSize: 10, color: axisLabelColor }, axisLine: { lineStyle: { color: axisLineColor } } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, axisLabel: { color: axisLabelColor }, splitLine: { lineStyle: { color: splitLineColor } } },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
      { scale: true, gridIndex: 2, axisLabel: { color: axisLabelColor }, splitLine: { show: false } },
      { scale: true, gridIndex: 3, axisLabel: { color: axisLabelColor }, splitLine: { show: false } },
    ],
    dataZoom: [
      // preventDefaultMouseMove:false —— 否则 echarts 会在每次拖动(不分方向)时都 preventDefault，
      // 手机上竖向滑动会被这里吞掉，导致页面上下滚不动（真正原因，不是长按手势那层的问题）。
      // zoomLock（手机端开）—— 关掉 echarts 自带的双指缩放响应（内置逻辑不看手指移动幅度，
      // 每次 pinch 事件固定缩 10%，手指划得快事件密集触发就显得"缩放贼快"）；缩放交给组件里
      // 自己写的 pinch 处理去接管，按真实的 pinchScale 幅度算，能单独调"多快"。
      { type: "inside", xAxisIndex: [0, 1, 2, 3], start: defaultStart, end: 100, zoomLock: compact, preventDefaultMouseMove: false },
      { type: "slider", xAxisIndex: [0, 1, 2, 3], bottom: 2, start: defaultStart, end: 100, height: 16, textStyle: { color: axisLabelColor } },
    ],
    series: [
      {
        name: "K线", type: "candlestick", data: candle,
        itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN },
      },
      { name: "MA5", type: "line", data: bars.map((b) => b.ma5), smooth: true, showSymbol: false, lineStyle, color: "#3b82f6" },
      { name: "MA10", type: "line", data: bars.map((b) => b.ma10), smooth: true, showSymbol: false, lineStyle, color: "#eab308" },
      { name: "MA20", type: "line", data: bars.map((b) => b.ma20), smooth: true, showSymbol: false, lineStyle, color: "#ec4899" },
      ...signalSeries,
      { name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1,
        data: bars.map((b) => ({ value: b.volume, itemStyle: { color: b.close >= b.open ? UP : DOWN } })) },
      { name: "DIF", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => b.dif), showSymbol: false, lineStyle, color: "#3b82f6" },
      { name: "DEA", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => b.dea), showSymbol: false, lineStyle, color: "#eab308" },
      { name: "MACD", type: "bar", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => ({ value: b.macd, itemStyle: { color: (b.macd ?? 0) >= 0 ? UP : DOWN } })) },
      { name: "K", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.k), showSymbol: false, lineStyle, color: "#3b82f6" },
      { name: "D", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.d), showSymbol: false, lineStyle, color: "#eab308" },
      { name: "J", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.j), showSymbol: false, lineStyle, color: "#ec4899" },
    ],
  };
}

// 顶部指标条：随悬停更新的当前 bar 数值（取代悬浮 tooltip）。
// 成交量 / KDJ / MACD 系列的数值不放在这里——挪到各自副图旁边的小字行，见 SubIndicatorLabels。
function InfoBar({ bar, prevClose }: { bar: KlineBar; prevClose?: number }) {
  const pct = prevClose ? ((bar.close - prevClose) / prevClose) * 100 : 0;
  const pctColor = pct > 0 ? UP : pct < 0 ? DOWN : undefined;
  const cells: { label: string; value: string; color?: string }[] = [
    { label: "日期", value: bar.trade_date },
    { label: "开盘", value: fmtNum(bar.open) },
    { label: "收盘", value: fmtNum(bar.close) },
    { label: "涨跌幅", value: `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`, color: pctColor },
    { label: "最高", value: fmtNum(bar.high) },
    { label: "最低", value: fmtNum(bar.low) },
    { label: "MA5", value: fmtNum(bar.ma5), color: "#3b82f6" },
    { label: "MA10", value: fmtNum(bar.ma10), color: "#eab308" },
    { label: "MA20", value: fmtNum(bar.ma20), color: "#ec4899" },
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

// 成交量 / MACD / KDJ 副图各自旁边的一小行实时数值（随主图 hover 联动），位置对齐 buildOption 里对应 grid 的 top
function SubIndicatorLabels({ bar, left }: { bar: KlineBar; left: number }) {
  const style = (top: string): CSSProperties => ({
    position: "absolute", left, top, fontSize: 11, color: "var(--text-secondary)",
    pointerEvents: "none", whiteSpace: "nowrap",
  });
  return (
    <>
      <div style={style("calc(50% + 2px)")}>
        成交量 <span style={{ color: bar.close >= bar.open ? UP : DOWN }}>{Number(bar.volume ?? 0).toLocaleString()} 手</span>
      </div>
      <div style={style("calc(66% + 2px)")}>
        DIF <span style={{ color: "#3b82f6" }}>{fmtNum(bar.dif)}</span>{" "}
        DEA <span style={{ color: "#eab308" }}>{fmtNum(bar.dea)}</span>{" "}
        MACD <span style={{ color: (bar.macd ?? 0) >= 0 ? UP : DOWN }}>{fmtNum(bar.macd)}</span>
      </div>
      <div style={style("calc(83% + 2px)")}>
        K <span style={{ color: "#3b82f6" }}>{fmtNum(bar.k)}</span>{" "}
        D <span style={{ color: "#eab308" }}>{fmtNum(bar.d)}</span>{" "}
        J <span style={{ color: "#ec4899" }}>{fmtNum(bar.j)}</span>
      </div>
    </>
  );
}

/** 6位代码 → 交易所前缀 */
function exchangePrefix(code: string): string {
  return /^[569]/.test(code) ? "SH" : /^[48]/.test(code) ? "BJ" : "SZ";
}

/**
 * 唤起雪球 App 并跳到对应股票页。
 *
 * 方案：URL Scheme（xueqiu://s/SH600000）。
 * - 本地服务（localhost）不在 xueqiu.com 域名，Universal Links 不会被 iOS 拦截，
 *   必须用 scheme 才能从 web app 直接打开原生 App。
 * - window.blur 降级：若 1.5s 内焦点没有转移（App 未安装/Scheme 未响应），
 *   则打开网页版作为兜底。
 *
 * 若 App 版本更新导致路径变化出现404，可替换 appUrl 里的路径后重新部署。
 */
function openXueqiu(code: string) {
  const symbol = `${exchangePrefix(code)}${code}`;
  const appUrl  = `xueqiu://s/${symbol}`;          // scheme 路径对应 web /S/
  const webUrl  = `https://xueqiu.com/S/${symbol}`; // 降级：App 未安装时打开网页

  let fallback: ReturnType<typeof setTimeout> | null = setTimeout(() => {
    window.open(webUrl, "_blank", "noreferrer");
  }, 1500);

  // App 成功接管时浏览器会触发 blur，取消降级
  const cancel = () => {
    if (fallback) { clearTimeout(fallback); fallback = null; }
    window.removeEventListener("blur", cancel);
  };
  window.addEventListener("blur", cancel, { once: true });

  window.location.href = appUrl;
}

function AiAnalysisCard({ code }: { code: string }) {
  const { data, isFetching } = useStockAiAnalysis(code, true);
  const gen = useGenerateStockAiAnalysis();
  const html = gen.data?.html ?? data?.html ?? "";
  const generated = gen.data?.generated ?? data?.generated ?? false;

  return (
    <Card
      title="AI综合解读"
      size="small"
      extra={generated && (
        <Button size="small" loading={gen.isPending}
          onClick={() => gen.mutate(code, { onError: (e) => message.error(errMsg(e, "生成失败")) })}>
          重新生成
        </Button>
      )}
    >
      <Spin spinning={isFetching || gen.isPending}>
        {generated ? (
          <MarkdownContent className="markdown-body" html={html} />
        ) : (
          <Empty description="还没有生成过技术面+基本面综合解读">
            <Button type="primary" loading={gen.isPending}
              onClick={() => gen.mutate(code, { onError: (e) => message.error(errMsg(e, "生成失败")) })}>
              生成解读
            </Button>
          </Empty>
        )}
      </Spin>
    </Card>
  );
}

export default function StockDetail() {
  const { code = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  // location.key === "default" 表示这是直接进入的（没有站内上一页可回，如刷新/外部链接直达）
  const canGoBack = location.key !== "default";
  const goBack = () => (canGoBack ? navigate(-1) : navigate("/screener"));
  const { data: kline, isLoading } = useKline(code);
  const { data: fund } = useFundamentals(code);
  const { data: news } = useNews(code);
  const { data: quote } = useQuote(code);
  const { mode } = useThemeMode();
  const isMobile = useIsMobile();
  const chartRef = useRef<ReactECharts>(null);
  // echarts-for-react 的图表实例是异步初始化的（getEchartsInstance 在 mount 那一刻同步读
  // 大概率还是 undefined）；用它自带的 onChartReady 拿到真正就绪的时机，而不是猜时机。
  const [chartReady, setChartReady] = useState(false);
  // 当前可见区间 [start,end]（百分比），双指缩放手势需要它算新窗口；随 datazoom 事件更新。
  const rangeRef = useRef({ start: 55, end: 100 });

  // ── bars：含实时报价合并，供顶部指标条 / hover 悬停显示用 ──
  const bars = useMemo(() => {
    const raw = kline?.bars ?? [];
    if (!quote || quote.error || !raw.length) return raw;
    const last = raw[raw.length - 1];
    if (last.trade_date !== quote.trade_date) return raw;
    const merged = {
      ...last,
      close: quote.close,
      high: Math.max(last.high, quote.high),
      low: Math.min(last.low, quote.low),
      volume: quote.volume ?? last.volume,
    };
    return [...raw.slice(0, -1), merged];
  }, [kline, quote]);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const activeIdx = hoverIdx != null && bars[hoverIdx] ? hoverIdx : bars.length - 1;
  const active = bars[activeIdx];
  const prevClose = activeIdx > 0 ? bars[activeIdx - 1]?.close : undefined;

  const dark = mode === "dark";

  // ── option：只依赖 kline/dark/isMobile，不依赖 quote ──
  // quote 实时更新不走 notMerge 全量重建（会重置 dataZoom），
  // 而是走下面的 useEffect 直接写入 ECharts 实例，保留缩放状态。
  const option = useMemo(() => buildOption(kline?.bars ?? [], dark, isMobile), [kline, dark, isMobile]);

  // ── 实时报价轻量更新：只改 K线和成交量两条系列的最后一根数据 ──
  useEffect(() => {
    if (!quote || quote.error || !chartReady) return;
    const inst = chartRef.current?.getEchartsInstance();
    if (!inst) return;
    const raw = kline?.bars ?? [];
    if (!raw.length) return;
    const last = raw[raw.length - 1];
    if (last.trade_date !== quote.trade_date) return;
    const merged = {
      ...last,
      close: quote.close,
      high: Math.max(last.high, quote.high),
      low: Math.min(last.low, quote.low),
      volume: quote.volume ?? last.volume,
    };
    const allBars = [...raw.slice(0, -1), merged];
    // setOption without notMerge → 仅合并变化的 series，dataZoom/zoom 状态完全保留
    inst.setOption({
      series: [
        { name: "K线", data: allBars.map((b) => [b.open, b.close, b.low, b.high]) },
        {
          name: "成交量",
          data: allBars.map((b) => ({
            value: b.volume,
            itemStyle: { color: b.close >= b.open ? UP : DOWN },
          })),
        },
      ],
    });
  }, [quote, kline, chartReady]);
  const onEvents = useMemo(
    () => ({
      // 悬停时读取当前索引，更新顶部指标条。因为 buildOption 里 tooltip.triggerOn 已经设成
      // "none"，这个事件只会在我们自己 dispatchAction({type:'showTip'}) 之后才触发
      // （见下面的长按手势 effect），不用再额外判断"是否长按解锁"。
      updateAxisPointer: (e: { axesInfo?: { value?: number }[] }) => {
        const v = e?.axesInfo?.[0]?.value;
        if (typeof v === "number" && v >= 0 && v < bars.length) setHoverIdx(v);
      },
      // 记录当前可见区间，供下面手机端的双指缩放手势用来算新窗口（锚点算法需要知道现在缩到哪儿了）
      datazoom: (e: { start?: number; end?: number; batch?: { start?: number; end?: number }[] }) => {
        const src = e.batch?.[0] ?? e;
        if (typeof src.start === "number" && typeof src.end === "number") {
          rangeRef.current = { start: src.start, end: src.end };
        }
      },
    }),
    [bars.length],
  );

  // 触屏手势：关掉 echarts 自带的自动触发（tooltip.triggerOn:"none"，见 buildOption）后，
  // 十字光标完全由我们手动 dispatchAction 驱动：
  // - 鼠标悬停：跟以前一样，每次 mousemove 立即 showTip，桌面体验不变。
  // - 触屏：手指按住不动 0.5s 才第一次 showTip；这 0.5s 内一旦位移超过阈值，就当作"划动/翻页"
  //   放弃这次长按（不再显示，也不会中途显示一下又消失）。松手/移出直接 hideTip。
  // - 长按解锁之后，拖动只应该挪动十字光标本身，不应该顺带把 dataZoom 的可见范围也拖动了——
  //   这两个手势原本共享同一串 touchmove，dataZoom(inside) 的 RoamController 不会管我们是不是
  //   进入了"十字光标模式"，照样跟着算 pan。这里用 dataZoom.disabled 在解锁瞬间关掉 pan
  //   （只改第一个 inside 类型的那项，滑块那项不受影响），松手再打开。
  // 之前两次都是想"压住"echarts 自己的自动显示（先试 hideTip，又试 setOption 切
  // axisPointer.show），都是在跟内部时机赛跑，压不干净；这次从根上关掉自动触发就没有这个问题了。
  useEffect(() => {
    const inst = chartRef.current?.getEchartsInstance();
    if (!inst) return;
    const zr = inst.getZr();
    const HOLD_MS = 500;
    const MOVE_TOLERANCE = 10;
    let isTouchDown = false;
    let armed = false;
    let startX = 0;
    let startY = 0;
    let lastX = 0;
    let lastY = 0;
    let timer: number | null = null;
    let lastTouchEnd = 0; // 记录最近一次 touch 抬手时刻，过滤浏览器合成的 mousemove

    const clearHoldTimer = () => {
      if (timer != null) { window.clearTimeout(timer); timer = null; }
    };
    let crosshairHidden = false; // 追踪十字线是否已切成 none 类型

    const showAt = (x: number, y: number) => {
      // 如果上一次 hide() 把 axisPointer type 切成了 none，先恢复再显示
      if (crosshairHidden) {
        inst.setOption({ tooltip: { axisPointer: { type: "cross" } } });
        crosshairHidden = false;
      }
      inst.dispatchAction({ type: "showTip", x, y });
    };
    const setPanDisabled = (v: boolean) => inst.setOption({ dataZoom: [{ disabled: v }] });
    const hide = () => {
      // 把 axisPointer type 切成 "none" —— 这是唯一能可靠清除十字线的方式。
      // hideTip 只藏 tooltip 浮层（本就是 showContent:false 所以看不到），
      // 而两条虚线是 axisPointer 独立绘制的，必须改 type 才会消失。
      // 下次 showAt 调用前会先切回 "cross"，对用户无感知。
      inst.setOption({ tooltip: { axisPointer: { type: "none" } } });
      crosshairHidden = true;
      setHoverIdx(null);
    };

    const onDown = (e: { offsetX: number; offsetY: number; zrByTouch?: boolean }) => {
      if (!e.zrByTouch) return; // 鼠标不走长按这套，交给下面 onMove 的鼠标分支
      isTouchDown = true;
      armed = false;
      startX = lastX = e.offsetX;
      startY = lastY = e.offsetY;
      clearHoldTimer();
      timer = window.setTimeout(() => {
        armed = true;
        setPanDisabled(true);
        showAt(lastX, lastY);
      }, HOLD_MS);
    };
    const onMove = (e: { offsetX: number; offsetY: number; zrByTouch?: boolean }) => {
      if (!e.zrByTouch) {
        // 手指松开后浏览器会合成一个 mousemove（zrByTouch=false），200ms 内忽略，
        // 防止 hide() 之后立刻被这个合成事件又把十字光标召回来。
        if (Date.now() - lastTouchEnd < 200) return;
        showAt(e.offsetX, e.offsetY);
        return;
      }
      lastX = e.offsetX;
      lastY = e.offsetY;
      if (!isTouchDown) return;
      if (armed) { showAt(lastX, lastY); return; } // 已经长按解锁，跟手移动，日线图范围不动
      const moved = Math.abs(e.offsetX - startX) > MOVE_TOLERANCE || Math.abs(e.offsetY - startY) > MOVE_TOLERANCE;
      if (moved) clearHoldTimer();
    };
    const onUp = () => {
      const wasTouch = isTouchDown;
      isTouchDown = false;
      if (armed) setPanDisabled(false);
      armed = false;
      clearHoldTimer();
      // 无论是否进入过 armed 状态，只要是 touch 抬手就记录时刻，
      // 阻断后续浏览器合成的 mousemove（zrByTouch=false）召回十字光标。
      if (wasTouch) lastTouchEnd = Date.now();
      hide();
    };

    zr.on("mousedown", onDown);
    zr.on("mousemove", onMove);
    zr.on("mouseup", onUp);
    zr.on("globalout", onUp);
    return () => {
      clearHoldTimer();
      zr.off("mousedown", onDown);
      zr.off("mousemove", onMove);
      zr.off("mouseup", onUp);
      zr.off("globalout", onUp);
    };
  }, [bars.length, chartReady]);

  // 手机端双指缩放：buildOption 里对应给 inside dataZoom 设了 zoomLock:true 关掉内置响应——
  // echarts 自己的 pinch 处理不看手指移动幅度，每次 pinch 事件不管捏得快慢都固定缩 10%
  // （见 zrender RoamController._pinchHandler: scale = pinchScale>1 ? 1.1 : 1/1.1），手指划
  // 快一点事件触发密集，缩放就跟着"贼快"。这里接管：用 e.pinchScale 的真实幅度算，且乘一个
  // <1 的阻尼系数把每帧的缩放量压小，同样的手指动作，缩得更慢更可控。
  useEffect(() => {
    if (!isMobile) return;
    const inst = chartRef.current?.getEchartsInstance();
    if (!inst || bars.length < 2) return;
    const zr = inst.getZr();
    const DAMPING = 0.35;

    const onPinch = (e: { pinchScale?: number; pinchX?: number; pinchY?: number }) => {
      if (!e.pinchScale || e.pinchX == null || e.pinchY == null) return;
      const { start, end } = rangeRef.current;
      const width = end - start;
      if (width <= 0) return;
      let anchorPercent = start + width / 2;
      try {
        const idx = inst.convertFromPixel({ xAxisIndex: 0 }, [e.pinchX, e.pinchY])?.[0];
        if (typeof idx === "number" && bars.length > 1) {
          anchorPercent = Math.min(100, Math.max(0, (idx / (bars.length - 1)) * 100));
        }
      } catch {
        // 转换失败（比如捏在坐标系外）就用窗口中心兜底
      }
      const effectiveScale = 1 + (e.pinchScale - 1) * DAMPING;
      const newWidth = Math.min(100, Math.max(2, width / effectiveScale));
      const relPos = (anchorPercent - start) / width;
      let newStart = anchorPercent - relPos * newWidth;
      let newEnd = newStart + newWidth;
      if (newStart < 0) { newEnd -= newStart; newStart = 0; }
      if (newEnd > 100) { newStart -= newEnd - 100; newEnd = 100; }
      newStart = Math.max(0, newStart);
      rangeRef.current = { start: newStart, end: newEnd };
      inst.dispatchAction({ type: "dataZoom", start: newStart, end: newEnd });
    };

    zr.on("pinch", onPinch);
    return () => zr.off("pinch", onPinch);
  }, [bars.length, chartReady, isMobile]);

  const fin = fund?.finance as Record<string, unknown> | null;
  const subLabelLeft = (isMobile ? 40 : 52) + 4;

  usePageContext(
    `用户在"股票详情"页，看的是 ${kline?.name || code}（${code}）。` +
    (active ? `最新（或当前hover）一天 ${active.trade_date}：收盘 ${active.close}，MA5/10/20 ${fmtNum(active.ma5)}/${fmtNum(active.ma10)}/${fmtNum(active.ma20)}。` : "") +
    (fund ? `市盈率 ${fmtNum(fund.quote.pe_ttm)}，市净率 ${fmtNum(fund.quote.pb)}，总市值 ${fmtYi(fund.quote.total_mv)}。` +
      (fund.sectors?.length ? `所属板块：${fund.sectors.map((s) => s.sector).join("、")}。` : "") : ""),
  );

  return (
    <Space direction="vertical" size={isMobile ? 12 : 16} style={{ width: "100%" }}>
      <Space wrap>
        <Button icon={<ArrowLeftOutlined />} onClick={goBack} size={isMobile ? "small" : "middle"}>返回</Button>
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>
          {kline?.name || code} <Typography.Text type="secondary">{code}</Typography.Text>
        </Typography.Title>
        {code && (
          <Button
            size="small"
            icon={<MobileOutlined />}
            onClick={() => openXueqiu(code)}
          >
            雪球
          </Button>
        )}
      </Space>

      <Card styles={{ body: { padding: isMobile ? 6 : 12 } }}>
        <Spin spinning={isLoading}>
          {bars.length ? (
            <>
              {active && <InfoBar bar={active} prevClose={prevClose} />}
              <div style={{ position: "relative", marginTop: 8 }}>
                <ReactECharts
                  ref={chartRef}
                  option={option}
                  style={{ height: isMobile ? 460 : 640, touchAction: "pan-y" }}
                  notMerge
                  onEvents={onEvents}
                  onChartReady={() => setChartReady(true)}
                />
                {active && <SubIndicatorLabels bar={active} left={subLabelLeft} />}
              </div>
            </>
          ) : <Empty description="暂无K线数据（需先在后台回补历史K线）" />}
        </Spin>
      </Card>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={24} sm={24} md={8}>
          <Card title="估值与财务" size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="市盈率(动)">{fmtNum(fund?.quote.pe_ttm)}</Descriptions.Item>
              <Descriptions.Item label="市净率">{fmtNum(fund?.quote.pb)}</Descriptions.Item>
              <Descriptions.Item label="总市值">{fmtYi(fund?.quote.total_mv)}</Descriptions.Item>
              {fin && <>
                <Descriptions.Item label="EPS">{fmtNum(fin.eps)}</Descriptions.Item>
                <Descriptions.Item label="ROE(%)">{fmtNum(fin.roe)}</Descriptions.Item>
                <Descriptions.Item label="净利润同比(%)">{fmtNum(fin.net_profit_yoy)}</Descriptions.Item>
                <Descriptions.Item label="营收同比(%)">{fmtNum(fin.revenue_yoy)}</Descriptions.Item>
                <Descriptions.Item label="毛利率(%)">{fmtNum(fin.gross_margin)}</Descriptions.Item>
                <Descriptions.Item label="报告期">{String(fin.report_date ?? "-")}</Descriptions.Item>
              </>}
            </Descriptions>
            <div style={{ marginTop: 12 }}>
              <Typography.Text type="secondary">所属板块：</Typography.Text>
              <div style={{ marginTop: 6 }}>
                {fund?.sectors?.length
                  ? fund.sectors.map((s) => (
                      <Tag key={s.sector} color={s.kind === "industry" ? "geekblue" : "purple"}>{s.sector}</Tag>
                    ))
                  : <Typography.Text type="secondary">（需先在后台全量同步板块成分股）</Typography.Text>}
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={24} md={8}>
          <Card title="大V提及" size="small" styles={{ body: { maxHeight: 420, overflow: "auto" } }}>
            {fund?.mentions?.length ? (
              <List size="small" dataSource={fund.mentions}
                renderItem={(p) => (
                  <List.Item extra={<a href={p.url} target="_blank" rel="noreferrer">原帖</a>}>
                    <List.Item.Meta title={`${p.user_name} · ${p.date}`}
                      description={<div style={{ maxHeight: 40, overflow: "hidden" }}>{p.text}</div>} />
                  </List.Item>
                )} />
            ) : <Empty description="近期无大V提及" />}
          </Card>
        </Col>
        <Col xs={24} sm={24} md={8}>
          <Card title="相关新闻" size="small" styles={{ body: { maxHeight: 420, overflow: "auto" } }}>
            {news?.items?.length ? (
              <List size="small" dataSource={news.items}
                renderItem={(n) => (
                  <List.Item>
                    <a href={n.url} target="_blank" rel="noreferrer">
                      <Typography.Text type="secondary">{n.date}</Typography.Text> {n.title}
                    </a>
                    {isDeepLinkNews(n.url) && (
                      <Tooltip title="该链接来自新浪资讯App跳转页，部分手机浏览器可能打不开或短暂显示后404">
                        <MobileOutlined style={{ marginLeft: 6, color: "#faad14" }} />
                      </Tooltip>
                    )}
                  </List.Item>
                )} />
            ) : <Empty description="暂无新闻" />}
          </Card>
        </Col>
      </Row>

      {code && <AiAnalysisCard code={code} />}
    </Space>
  );
}
