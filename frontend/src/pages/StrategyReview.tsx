import { Button, Card, Col, Collapse, DatePicker, Empty, Input, InputNumber, Popconfirm, Row, Select, Space, Statistic, Table, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import dayjs from "dayjs";
import { Link } from "react-router-dom";

import { useDeleteStrategyCombination, useSaveStrategyCombination, useSavedStrategyCombinations, useStartStrategyCombination, useStrategyCombinationStatus, useStrategyReview } from "@/api/hooks";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useVisitorAuth } from "@/visitorAuth";

const labels: Record<string, string> = {
  ma_cross: "严格买点", ma_cross2: "宽松买点", golden_cross: "金叉买点", fund_ok: "基本面", volume_breakout: "放量突破",
  pullback_low_volume: "缩量回踩", boll_breakout: "布林突破", rsi_oversold_bounce: "RSI反弹", turnover_surge: "换手放量",
  volume_price_up: "量价齐升", sell_ma_death_cross: "均线死叉", sell_break_ma20: "跌破MA20", sell_rsi_overbought: "RSI超买", sell_high_volume_drop: "放量下跌",
};
const pct = (v: number | null) => v == null ? "-" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
const stockLabel = (row: { name?: string | null; code: string }) => {
  const name = (row.name || "")
    .replace(/[（(]\s*\d{6}\s*[）)]\s*$/, "")
    .trim();
  const validName = name && name !== row.code && !/^\d+$/.test(name) ? name : "";
  return validName ? `${validName}（${row.code}）` : row.code;
};

export default function StrategyReview() {
  const mobile = useIsMobile();
  const [strategy, setStrategy] = useState<string>();
  const [reviewExpanded, setReviewExpanded] = useState<string[]>([]);
  const { data, isLoading } = useStrategyReview({ strategy }, reviewExpanded.length > 0);
  const [buyStrategies, setBuyStrategies] = useState(["ma_cross"]);
  const [sellStrategies, setSellStrategies] = useState(["sell_break_ma20"]);
  const [buyOperator, setBuyOperator] = useState("OR");
  const [sellOperator, setSellOperator] = useState("OR");
  const [saveName, setSaveName] = useState("");
  const [capital, setCapital] = useState(100000);
  const [maxPositions, setMaxPositions] = useState(10);
  const [allowSecondEntry, setAllowSecondEntry] = useState(true);
  const [secondEntryDrawdownPct, setSecondEntryDrawdownPct] = useState(8);
  const [ranking, setRanking] = useState("change_pct_desc");
  const [excludeChinext, setExcludeChinext] = useState(true);
  const [excludeStar, setExcludeStar] = useState(true);
  const [excludeSt, setExcludeSt] = useState(true);
  const [minChangePct, setMinChangePct] = useState<number | null>(null);
  const [maxChangePct, setMaxChangePct] = useState<number | null>(null);
  const [minTotalMv, setMinTotalMv] = useState<number | null>(null);
  const [maxTotalMv, setMaxTotalMv] = useState<number | null>(null);
  const [tp1Pct, setTp1Pct] = useState(10);
  const [tp1Fraction, setTp1Fraction] = useState(25);
  const [tp2Pct, setTp2Pct] = useState(20);
  const [tp2Fraction, setTp2Fraction] = useState(25);
  const [tp3Pct, setTp3Pct] = useState(30);
  const [tp3Fraction, setTp3Fraction] = useState(25);
  const [selectedSavedId, setSelectedSavedId] = useState<number | null>(null);
  const [period, setPeriod] = useState("1y");
  const [customStart, setCustomStart] = useState(dayjs().subtract(1, "year"));
  const [customEnd, setCustomEnd] = useState(dayjs());
  const [runStarted, setRunStarted] = useState(false);
  const [statusRefreshKey, setStatusRefreshKey] = useState(0);
  const { loggedIn, isGuest } = useVisitorAuth();
  const periodStart = period === "1w" ? dayjs().subtract(1, "week").format("YYYY-MM-DD") : period === "1m" ? dayjs().subtract(1, "month").format("YYYY-MM-DD") : period === "3m" ? dayjs().subtract(3, "month").format("YYYY-MM-DD") : period === "6m" ? dayjs().subtract(6, "month").format("YYYY-MM-DD") : period === "custom" ? customStart.format("YYYY-MM-DD") : dayjs().subtract(1, "year").format("YYYY-MM-DD");
  const periodEnd = period === "custom" ? customEnd.format("YYYY-MM-DD") : dayjs().format("YYYY-MM-DD");
  const executionConfig = {
    initial_capital: capital, max_positions: maxPositions, ranking,
    allow_second_entry: allowSecondEntry, second_entry_drawdown_pct: secondEntryDrawdownPct,
    exclude_chinext: excludeChinext, exclude_star: excludeStar, exclude_st: excludeSt,
    min_change_pct: minChangePct, max_change_pct: maxChangePct,
    min_total_mv: minTotalMv, max_total_mv: maxTotalMv,
    take_profit_1_pct: tp1Pct, take_profit_1_fraction: tp1Fraction / 100,
    take_profit_2_pct: tp2Pct, take_profit_2_fraction: tp2Fraction / 100,
    take_profit_3_pct: tp3Pct, take_profit_3_fraction: tp3Fraction / 100,
    start: periodStart, end: periodEnd,
  };
  const startCombination = useStartStrategyCombination();
  const { data: combinationStatus } = useStrategyCombinationStatus(runStarted, statusRefreshKey);
  const combination = combinationStatus?.parameters?.result;
  const combinationLoading = startCombination.isPending || runStarted || combinationStatus?.running === true;
  const { data: saved } = useSavedStrategyCombinations(loggedIn && !isGuest);
  const saveCombination = useSaveStrategyCombination();
  const deleteCombination = useDeleteStrategyCombination();
  const columns = [
    { title: "策略", dataIndex: "strategy_key", render: (v: string) => labels[v] || v, fixed: "left" as const },
    { title: "信号数", dataIndex: "pick_count" },
    ...[1, 3, 5, 10, 20].map((n) => ({ title: `${n}日均收益`, dataIndex: `d${n}_avg`, render: (v: number | null) => <span className={v != null && v >= 0 ? "positive" : "negative"}>{pct(v)}</span> })),
    { title: "5日胜率", dataIndex: "d5_win_rate", render: (v: number | null) => v == null ? "-" : `${v.toFixed(1)}%` },
  ];
  const detailColumns = [
    { title: "日期", dataIndex: "trade_date", width: 105 },
    { title: "策略", dataIndex: "strategy_key", render: (v: string) => labels[v] || v },
    { title: "股票", render: (_: unknown, r: any) => <Link to={`/stock/${r.code}`}>{stockLabel(r)}</Link> },
    ...[1, 3, 5, 10, 20].map((n) => ({ title: `${n}日`, render: (_: unknown, r: any) => pct(r.returns[String(n)]) })),
    { title: "最高", dataIndex: "max_gain", render: pct },
    { title: "回撤", dataIndex: "max_drawdown", render: pct },
  ];
  const dailyColumns = [
    { title: "信号日期", dataIndex: "trade_date", width: 110 },
    { title: "策略", dataIndex: "strategy_key", render: (v: string) => labels[v] || v },
    { title: "选股数", dataIndex: "pick_count" },
    { title: "5日平均收益", dataIndex: "d5_avg", render: pct },
    { title: "5日胜率", dataIndex: "d5_win_rate", render: (v: number | null) => v == null ? "待观察" : `${v.toFixed(1)}%` },
  ];
  const comboColumns = [
    { title: "信号日", dataIndex: "signal_date", sorter: (a: any, b: any) => String(a.signal_date || "").localeCompare(String(b.signal_date || "")), defaultSortOrder: "descend" as const },
    { title: "买入日", dataIndex: "buy_date" },
    { title: "股票", render: (_: unknown, r: any) => <Link to={`/stock/${r.code}`}>{stockLabel(r)}</Link> },
    { title: "卖出日", dataIndex: "sell_date", render: (v: string | null) => v || <Tag color="blue">持有中</Tag> },
    { title: "持有交易日", dataIndex: "holding_days" },
    { title: "收益", dataIndex: "return_pct", sorter: (a: any, b: any) => Number(a.return_pct || 0) - Number(b.return_pct || 0), render: (v: number) => <span className={v >= 0 ? "positive" : "negative"}>{pct(v)}</span> },
  ];
  const executionColumns = [
    { title: "信号日", dataIndex: "signal_date", sorter: (a: any, b: any) => String(a.signal_date || "").localeCompare(String(b.signal_date || "")), defaultSortOrder: "descend" as const },
    { title: "买入日", dataIndex: "buy_date" },
    { title: "股票", render: (_: unknown, r: any) => <Link to={`/stock/${r.code}`}>{stockLabel(r)}</Link> },
    { title: "卖出日", dataIndex: "sell_date", render: (v: string | null) => v || <Tag color="blue">持有中</Tag> },
    { title: "持有交易日", dataIndex: "holding_days" },
    { title: "卖出数量", dataIndex: "shares", render: (v: number | undefined) => v ? `${v} 股` : "-" },
    { title: "买入价", dataIndex: "entry_close", render: (v: number) => v?.toFixed(2) },
    { title: "当前/卖出价", dataIndex: "exit_close", render: (v: number) => v?.toFixed(2) },
    { title: "卖出原因", dataIndex: "sell_reason", render: (v: string | undefined) => v === "take_profit" ? <Tag color="gold">分档止盈</Tag> : v === "sell_signal" ? <Tag color="red">卖点清仓</Tag> : v === "end_of_period" ? <Tag color="blue">期末持有</Tag> : "-" },
    { title: "实际收益", dataIndex: "return_pct", sorter: (a: any, b: any) => Number(a.return_pct || 0) - Number(b.return_pct || 0), render: (v: number) => <span className={v >= 0 ? "positive" : "negative"}>{pct(v)}</span> },
  ];
  const mobileTradeCards = (rows: any[], execution: boolean) => rows?.length ? <div className="strategy-trade-list">
    {rows.map((row) => <div className="strategy-trade-card" key={`${row.buy_date}-${row.code}-${row.sell_date || "open"}`}>
      <div className="strategy-trade-head">
        <Link to={`/stock/${row.code}`} className="strategy-trade-stock">{stockLabel(row)}</Link>
        {row.sell_date ? <Tag color={row.sell_reason === "sell_signal" ? "red" : "gold"}>{execution && row.sell_reason === "sell_signal" ? "卖点清仓" : "已卖出"}</Tag> : <Tag color="blue">持有中</Tag>}
      </div>
      <div className="strategy-trade-meta">
        <span><label>信号日</label>{row.signal_date || "-"}</span>
        <span><label>买入日</label>{row.buy_date || "-"}</span>
        <span><label>卖出日</label>{row.sell_date || "-"}</span>
        <span><label>持有</label>{row.holding_days ?? "-"} 日</span>
      </div>
      <div className="strategy-trade-foot">
        <span>{execution ? `成交 ${row.shares || 0} 股` : "信号交易"}</span>
        <strong className={Number(row.return_pct) >= 0 ? "positive" : "negative"}>{pct(Number(row.return_pct))}</strong>
      </div>
    </div>)}
  </div> : <Empty description="暂无交易记录" />;
  const mobileDailyCards = (rows: any[]) => rows?.length ? <div className="strategy-trade-list">
    {rows.map((row) => <div className="strategy-trade-card" key={`${row.trade_date}-${row.strategy_key}`}>
      <div className="strategy-trade-head"><strong>{labels[row.strategy_key] || row.strategy_key}</strong><span className="strategy-card-date">{row.trade_date}</span></div>
      <div className="strategy-trade-meta"><span><label>选股数</label>{row.pick_count}</span><span><label>5日平均收益</label><strong className={Number(row.d5_avg) >= 0 ? "positive" : "negative"}>{pct(row.d5_avg)}</strong></span><span><label>5日胜率</label>{row.d5_win_rate == null ? "待观察" : `${row.d5_win_rate.toFixed(1)}%`}</span></div>
    </div>)}
  </div> : <Empty description="暂无复盘批次" />;
  const mobileSummaryCards = (rows: any[]) => rows?.length ? <div className="strategy-trade-list">
    {rows.map((row) => <div className="strategy-trade-card" key={row.strategy_key}>
      <div className="strategy-trade-head"><strong>{labels[row.strategy_key] || row.strategy_key}</strong><span>{row.pick_count} 个信号</span></div>
      <div className="strategy-return-grid">{[1, 3, 5, 10, 20].map((n) => <span key={n}><label>{n}日均收益</label><strong className={Number(row[`d${n}_avg`]) >= 0 ? "positive" : "negative"}>{pct(row[`d${n}_avg`])}</strong></span>)}</div>
    </div>)}
  </div> : <Empty description="暂无策略汇总" />;
  const mobileDetailCards = (rows: any[]) => rows?.length ? <div className="strategy-trade-list">
    {rows.map((row) => <div className="strategy-trade-card" key={`${row.trade_date}-${row.strategy_key}-${row.code}`}>
      <div className="strategy-trade-head"><Link to={`/stock/${row.code}`} className="strategy-trade-stock">{stockLabel(row)}</Link><span className="strategy-card-date">{row.trade_date}</span></div>
      <div className="strategy-card-subtitle">{labels[row.strategy_key] || row.strategy_key}</div>
      <div className="strategy-return-grid">{[1, 3, 5, 10, 20].map((n) => <span key={n}><label>{n}日</label><strong className={Number(row.returns?.[String(n)]) >= 0 ? "positive" : "negative"}>{pct(row.returns?.[String(n)])}</strong></span>)}</div>
    </div>)}
  </div> : <Empty description="暂无信号明细" />;
  const strategyOptions = (keys?: string[]) => (keys || []).map((v) => ({ value: v, label: labels[v] || v }));
  const buyOptions = strategyOptions(["ma_cross", "ma_cross2", "golden_cross", "volume_breakout", "boll_breakout", "rsi_oversold_bounce"]);
  const sellOptions = strategyOptions(["sell_ma_death_cross", "sell_break_ma20", "sell_rsi_overbought", "sell_high_volume_drop"]);
  const field = (label: string, control: ReactNode, className = "") => <div className={`strategy-control ${className}`}>
    <span className="strategy-control-label">{label}</span>
    <div className="strategy-control-input">{control}</div>
  </div>;
  useEffect(() => {
    if (runStarted && combinationStatus && !combinationStatus.running && combinationStatus.status) setRunStarted(false);
  }, [runStarted, combinationStatus]);
  useEffect(() => {
    const e = saved?.items?.find((x) => x.id === selectedSavedId)?.buy_expression.execution;
    if (!e) return;
    setTp1Pct(Number(e.take_profit_1_pct) || 10); setTp1Fraction((Number(e.take_profit_1_fraction) || 0.25) * 100);
    setTp2Pct(Number(e.take_profit_2_pct) || 20); setTp2Fraction((Number(e.take_profit_2_fraction) || 0.25) * 100);
    setTp3Pct(Number(e.take_profit_3_pct) || 30); setTp3Fraction((Number(e.take_profit_3_fraction) || 0.25) * 100);
  }, [saved, selectedSavedId]);
  useEffect(() => {
    const x = saved?.items?.find((item) => item.buy_expression.operator === buyOperator
      && item.sell_expression.operator === sellOperator
      && JSON.stringify(item.buy_expression.strategies) === JSON.stringify(buyStrategies)
      && JSON.stringify(item.sell_expression.strategies) === JSON.stringify(sellStrategies)
      && Number(item.buy_expression.execution?.initial_capital) === capital
      && Number(item.buy_expression.execution?.max_positions) === maxPositions);
    if (x && x.id !== selectedSavedId) setSelectedSavedId(x.id);
  }, [saved, buyOperator, sellOperator, buyStrategies, sellStrategies, capital, maxPositions, selectedSavedId]);
  return <Space className="strategy-review-page" direction="vertical" size={12} style={{ width: "100%" }}>
    <div><Typography.Title level={mobile ? 5 : 4} style={{ margin: 0 }}>每日选股策略复盘</Typography.Title><Typography.Text type="secondary">收盘后自动保存各策略信号，并按后续交易日计算收益。</Typography.Text></div>
    <Card size="small"><Space wrap><Select allowClear placeholder="选择策略" style={{ width: 180 }} value={strategy} onChange={setStrategy} options={(data?.strategies || []).map((v) => ({ value: v, label: labels[v] || v }))} /><Tag color="blue">自动记录全部内置策略</Tag></Space></Card>
    <Collapse activeKey={reviewExpanded} onChange={(keys) => setReviewExpanded(Array.isArray(keys) ? keys : [keys])} items={[{ key: "daily", label: "每日信号批次", children: mobile ? mobileDailyCards(data?.daily_summary || []) : <Table rowKey={(r) => `${r.trade_date}-${r.strategy_key}`} loading={isLoading} columns={dailyColumns} dataSource={data?.daily_summary || []} size="small" pagination={{ pageSize: 15 }} /> }]} />
    <Collapse activeKey={reviewExpanded} onChange={(keys) => setReviewExpanded(Array.isArray(keys) ? keys : [keys])} items={[{ key: "summary", label: "策略汇总", children: mobile ? mobileSummaryCards(data?.summary || []) : <Table rowKey="strategy_key" loading={isLoading} columns={columns} dataSource={data?.summary || []} size="small" pagination={false} scroll={{ x: 900 }} /> }]} />
    <Collapse activeKey={reviewExpanded} onChange={(keys) => setReviewExpanded(Array.isArray(keys) ? keys : [keys])} items={[{ key: "detail", label: "信号明细", children: mobile ? mobileDetailCards(data?.items || []) : <Table rowKey={(r) => `${r.trade_date}-${r.strategy_key}-${r.code}`} loading={isLoading} columns={detailColumns} dataSource={data?.items || []} size="small" pagination={{ pageSize: 30 }} locale={{ emptyText: <Empty description="暂无复盘快照，请等待收盘自动记录或运行一次任务" /> }} /> }]} />
    <Card className="strategy-combination-card" size="small" title="组合策略回测"><Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>无需先选股。系统会扫描全市场历史日线，逐只股票计算买入/卖出信号；当前资金和最大持仓仅用于组合执行层统计。</Typography.Paragraph><div className="strategy-controls">
      {field("买入策略", <Select mode="multiple" value={buyStrategies} onChange={setBuyStrategies} options={buyOptions} placeholder="选择买入策略" />)}
      {field("买入逻辑", <Select value={buyOperator} onChange={setBuyOperator} options={["OR", "AND"].map((v) => ({ value: v, label: v }))} />)}
      {field("卖出策略", <Select mode="multiple" value={sellStrategies} onChange={setSellStrategies} options={sellOptions} placeholder="选择卖出策略" />)}
      {field("卖出逻辑", <Select value={sellOperator} onChange={setSellOperator} options={["OR", "AND"].map((v) => ({ value: v, label: v }))} />)}
      {field("初始资金", <Input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value) || 100000)} />)}
      {field("最大持仓", <Input type="number" value={maxPositions} onChange={(e) => setMaxPositions(Number(e.target.value) || 10)} />)}
      {field("二次建仓", <Select value={allowSecondEntry ? "enabled" : "disabled"} onChange={(v) => setAllowSecondEntry(v === "enabled")} options={[{ value: "enabled", label: "允许二次建仓" }, { value: "disabled", label: "不补仓" }]} />)}
      {allowSecondEntry ? field("补仓回撤", <InputNumber min={0} max={50} value={secondEntryDrawdownPct} onChange={(v) => setSecondEntryDrawdownPct(Number(v) || 0)} addonAfter="%" />) : null}
      {field("候选排序", <Select value={ranking} onChange={setRanking} options={[{ value: "change_pct_desc", label: "涨幅降序" }, { value: "change_pct_asc", label: "涨幅升序" }, { value: "amount", label: "按成交额排序" }, { value: "code", label: "按代码排序" }]} />)}
      {field("板块过滤", <Select mode="multiple" value={[...(excludeChinext ? ["chinext"] : []), ...(excludeStar ? ["star"] : [])]} onChange={(v: string[]) => { setExcludeChinext(v.includes("chinext")); setExcludeStar(v.includes("star")); }} options={[{ value: "chinext", label: "排除创业板" }, { value: "star", label: "排除科创板" }]} placeholder="选择板块过滤" />)}
      {field("ST过滤", <Select value={excludeSt ? "st" : undefined} onChange={(v) => setExcludeSt(v === "st")} options={[{ value: "st", label: "排除 ST" }]} allowClear placeholder="不限制" />)}
      {field("最低涨幅", <InputNumber value={minChangePct} onChange={setMinChangePct} addonAfter="%" placeholder="不限制" />)}
      {field("最高涨幅", <InputNumber value={maxChangePct} onChange={setMaxChangePct} addonAfter="%" placeholder="不限制" />)}
      {field("最小市值", <InputNumber min={0} value={minTotalMv} onChange={setMinTotalMv} addonAfter="万元" placeholder="不限制" />)}
      {field("最大市值", <InputNumber min={0} value={maxTotalMv} onChange={setMaxTotalMv} addonAfter="万元" placeholder="不限制" />)}
      {field("止盈一档", <InputNumber min={0} value={tp1Pct} onChange={(v) => setTp1Pct(Number(v) || 0)} addonAfter="%" />)}
      {field("一档卖出", <InputNumber min={0} max={100} value={tp1Fraction} onChange={(v) => setTp1Fraction(Number(v) || 0)} addonAfter="%" />)}
      {field("止盈二档", <InputNumber min={0} value={tp2Pct} onChange={(v) => setTp2Pct(Number(v) || 0)} addonAfter="%" />)}
      {field("二档卖出", <InputNumber min={0} max={100} value={tp2Fraction} onChange={(v) => setTp2Fraction(Number(v) || 0)} addonAfter="%" />)}
      {field("止盈三档", <InputNumber min={0} value={tp3Pct} onChange={(v) => setTp3Pct(Number(v) || 0)} addonAfter="%" />)}
      {field("三档卖出", <InputNumber min={0} max={100} value={tp3Fraction} onChange={(v) => setTp3Fraction(Number(v) || 0)} addonAfter="%" />)}
      {field("回测周期", <Select value={period} onChange={setPeriod} options={[{ value: "1w", label: "近一周" }, { value: "1m", label: "近一个月" }, { value: "3m", label: "近3个月" }, { value: "6m", label: "近6个月" }, { value: "1y", label: "近1年" }, { value: "custom", label: "自定义" }]} />)}
      {period === "custom" ? field("开始日期", <DatePicker value={customStart} onChange={(v) => v && setCustomStart(v)} />) : null}
      {period === "custom" ? field("结束日期", <DatePicker value={customEnd} onChange={(v) => v && setCustomEnd(v)} />) : null}
      {field("执行回测", <Button type="primary" loading={combinationLoading} onClick={() => { setRunStarted(true); setStatusRefreshKey((v) => v + 1); startCombination.mutate({ buy_strategies: buyStrategies.join(","), sell_strategies: sellStrategies.join(","), buy_operator: buyOperator, sell_operator: sellOperator, initial_capital: capital, max_positions: maxPositions, ranking, exclude_chinext: excludeChinext, exclude_star: excludeStar, exclude_st: excludeSt, min_change_pct: minChangePct ?? undefined, max_change_pct: maxChangePct ?? undefined, min_total_mv: minTotalMv ?? undefined, max_total_mv: maxTotalMv ?? undefined, take_profit_1_pct: tp1Pct, take_profit_1_fraction: tp1Fraction / 100, take_profit_2_pct: tp2Pct, take_profit_2_fraction: tp2Fraction / 100, take_profit_3_pct: tp3Pct, take_profit_3_fraction: tp3Fraction / 100, start: periodStart, end: periodEnd, limit: 500 }, { onError: () => setRunStarted(false) }); }}>开始回测</Button>)}
      {runStarted && combinationStatus?.progress?.message ? <div className="strategy-control-info">{combinationStatus.progress.message}</div> : null}
      {combination ? <div className="strategy-control-info"><Tag color="blue">交易 {combination.summary.total_trades} 笔 · 胜率 {combination.summary.win_rate == null ? "-" : `${combination.summary.win_rate}%`} · 平均收益 {pct(combination.summary.avg_return_pct)}</Tag></div> : null}
      {field("组合名称", <Input value={saveName} onChange={(e) => setSaveName(e.target.value)} placeholder="输入名称" />)}
      {field("保存操作", <Button loading={saveCombination.isPending} onClick={() => {
        if (!saveName.trim()) { message.warning("请输入组合名称"); return; }
        saveCombination.mutate({ name: saveName, buy_expression: { operator: buyOperator, strategies: buyStrategies }, sell_expression: { operator: sellOperator, strategies: sellStrategies }, execution: executionConfig }, { onSuccess: () => { message.success("组合策略已保存"); setSaveName(""); } });
      }}>保存组合</Button>)}
      {saved?.items?.length ? field("加载组合", <Select placeholder="选择已保存组合" options={saved.items.map((x) => ({ value: x.id, label: x.name }))} onChange={(id) => { const x = saved.items.find((v) => v.id === id); if (x) { setBuyStrategies(x.buy_expression.strategies); setBuyOperator(x.buy_expression.operator); setSellStrategies(x.sell_expression.strategies); setSellOperator(x.sell_expression.operator); const e = x.buy_expression.execution; if (e) { setCapital(Number(e.initial_capital) || 100000); setMaxPositions(Number(e.max_positions) || 10); setRanking(String(e.ranking || "change_pct_desc")); setExcludeChinext(e.exclude_chinext !== false); setExcludeStar(e.exclude_star !== false); setExcludeSt(e.exclude_st !== false); setMinChangePct(e.min_change_pct === "" || e.min_change_pct == null ? null : Number(e.min_change_pct)); setMaxChangePct(e.max_change_pct === "" || e.max_change_pct == null ? null : Number(e.max_change_pct)); setMinTotalMv(e.min_total_mv === "" || e.min_total_mv == null ? null : Number(e.min_total_mv)); setMaxTotalMv(e.max_total_mv === "" || e.max_total_mv == null ? null : Number(e.max_total_mv)); } } }} />) : null}
      {saved?.items?.length ? field("删除组合", <Space><Select value={selectedSavedId ?? undefined} placeholder="选择组合" options={saved.items.map((x) => ({ value: x.id, label: x.name }))} onChange={setSelectedSavedId} /><Popconfirm title="确定删除这个组合？" onConfirm={() => { if (selectedSavedId != null) deleteCombination.mutate(selectedSavedId, { onSuccess: () => setSelectedSavedId(null) }); }}><Button danger disabled={selectedSavedId == null} loading={deleteCombination.isPending}>删除</Button></Popconfirm></Space>) : null}
    </div>
    {combination ? <Row gutter={[8, 8]} style={{ marginTop: 10 }}>
      <Col xs={12} sm={6}><Card size="small"><Statistic title="逐股票信号交易" value={combination.summary.total_trades} suffix="笔" /></Card></Col>
      <Col xs={12} sm={6}><Card size="small"><Statistic title="资金约束实际执行" value={combination.summary.portfolio_trades ?? 0} suffix="笔" /></Card></Col>
      <Col xs={12} sm={6}><Card size="small"><Statistic title="组合最终收益" value={combination.summary.portfolio_return_pct ?? 0} precision={2} suffix="%" valueStyle={{ color: (combination.summary.portfolio_return_pct ?? 0) >= 0 ? "#cf1322" : "#3f8600" }} /></Card></Col>
      <Col xs={12} sm={6}><Card size="small"><Statistic title="组合最大回撤" value={combination.summary.portfolio_max_drawdown_pct ?? 0} precision={2} suffix="%" valueStyle={{ color: "#cf1322" }} /></Card></Col>
    </Row> : null}
    {combination ? <Typography.Text type="secondary" style={{ display: "block", marginTop: 8 }}>上方交易明细是逐股票信号结果；“资金约束实际执行”已按资金、最大持仓数、排序和交易费用筛选。</Typography.Text> : null}
    <Collapse defaultActiveKey={["execution"]} items={[{ key: "execution", label: `实际执行交易（${combination?.summary.portfolio_trades ?? 0} 笔）`, children: mobile ? mobileTradeCards(combination?.portfolio_trades || [], true) : <Table rowKey={(r) => `${r.buy_date}-${r.code}-${r.sell_date || "open"}`} loading={combinationLoading} columns={executionColumns} dataSource={combination?.portfolio_trades || []} size="small" pagination={{ pageSize: 15 }} locale={{ emptyText: "暂无符合资金约束的实际交易" }} /> }]} />
    <Collapse items={[{ key: "signals", label: `逐股票信号交易明细（${combination?.summary.total_trades ?? 0} 笔）`, children: mobile ? mobileTradeCards(combination?.trades || [], false) : <Table rowKey={(r) => `${r.buy_date}-${r.code}-${r.sell_date || "open"}`} loading={combinationLoading} columns={comboColumns} dataSource={combination?.trades || []} size="small" pagination={{ pageSize: 15 }} /> }]} />
    </Card>
  </Space>;
}
