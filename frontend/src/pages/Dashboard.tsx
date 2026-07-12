import { CalendarOutlined, FileTextOutlined, FireOutlined, TeamOutlined } from "@ant-design/icons";
import {
  Card, Col, Empty, InputNumber, List, Row, Segmented, Select,
  Space, Spin, Statistic, Tag, Tooltip, Typography,
} from "antd";
import ReactECharts from "echarts-for-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useOverview, useUsers } from "@/api/hooks";
import type { BullishHeatBoard, BullishHeatItem } from "@/api/types";
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
        flex: 1, height: 6, borderRadius: 3,
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
        onClick={() => navigate("/summary", { state: { userId: uid } })}
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
  items, isLoading, daysLabel, nameToId,
}: {
  items: BullishHeatItem[];
  isLoading: boolean;
  daysLabel: string;
  nameToId: Map<string, string>;
}) {
  const HEAT_PAGE_SIZE = 8;
  const [page, setPage] = useState(1);
  const maxCount = items[0]?.bullish_count ?? 1;

  if (!items.length) {
    return <Empty description={isLoading ? "加载中" : `${daysLabel}暂无大V看多判定`} />;
  }
  return (
    <List<BullishHeatItem>
      dataSource={items}
      pagination={{ pageSize: HEAT_PAGE_SIZE, size: "small", hideOnSinglePage: true, current: page, onChange: setPage }}
      renderItem={(it, i) => {
        const rank = (page - 1) * HEAT_PAGE_SIZE + i + 1;
        return (
          <List.Item style={{ padding: "10px 0" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10, width: "100%" }}>
              <div style={{ paddingTop: 2 }}><RankBadge rank={rank} /></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                {/* 股票名 + 价格 + 看多人数 */}
                <Space wrap size={[6, 4]} style={{ marginBottom: 4 }}>
                  <Link to={`/stock/${it.code}`} style={{ fontWeight: 600, fontSize: 14 }}>{it.name}</Link>
                  {it.close != null && (
                    <span className={pctClass(it.change_pct)} style={{ fontSize: 13 }}>
                      {fmtNum(it.close)}&nbsp;{fmtPct(it.change_pct)}
                    </span>
                  )}
                  <Tag color="volcano" style={{ marginInlineEnd: 0 }}>
                    🔥 {it.bullish_count} 位大V
                  </Tag>
                </Space>
                {/* 热度条 */}
                <HeatBar value={it.bullish_count} max={maxCount} />
                {/* 大V Tag（可点击跳转总结） */}
                <Space size={[4, 4]} wrap style={{ marginTop: 6 }}>
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
// 热度榜：行业 / 概念 Tab
// ──────────────────────────────────────────────
function BoardHeatList({
  boards, isLoading, daysLabel, kind, nameToId,
}: {
  boards: BullishHeatBoard[];
  isLoading: boolean;
  daysLabel: string;
  kind: "industry" | "concept";
  nameToId: Map<string, string>;
}) {
  const navigate = useNavigate();
  const HEAT_PAGE_SIZE = 6;
  const [page, setPage] = useState(1);
  const filtered = boards.filter((b) => b.kind === kind);
  const maxCount = filtered[0]?.bullish_stock_count ?? 1;

  const goScreener = (sectorName: string) => {
    Object.assign(screenerState, {
      sectorOn: true,
      sectorMode: "manual",
      sectorNames: [sectorName],
      // 重置无关的筛选，避免带入上次的条件干扰
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
      pagination={{ pageSize: HEAT_PAGE_SIZE, size: "small", hideOnSinglePage: true, current: page, onChange: setPage }}
      renderItem={(it, i) => {
        const rank = (page - 1) * HEAT_PAGE_SIZE + i + 1;
        return (
          <List.Item style={{ padding: "10px 0" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10, width: "100%" }}>
              <div style={{ paddingTop: 2 }}><RankBadge rank={rank} /></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                {/* 板块名（点击 → 选股预填该板块）+ 统计 Tag */}
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
                {/* 热度条 */}
                <HeatBar value={it.bullish_stock_count} max={maxCount} color="#722ed1" />
                {/* 个股 Tag（点击 → 个股详情） */}
                <Space size={[4, 4]} wrap style={{ marginTop: 6 }}>
                  {it.bullish_stocks.map((s) => (
                    <Tag key={s.code} color="default">
                      <Link to={`/stock/${s.code}`}>{s.name}</Link>
                    </Tag>
                  ))}
                </Space>
                {/* 大V Tag（可点击跳转总结） */}
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
// 主组件
// ──────────────────────────────────────────────

const DAY_OPTIONS = [
  { label: "今天", value: 1 },
  { label: "近3天", value: 3 },
  { label: "近7天", value: 7 },
  { label: "自定义", value: 0 },
];

export default function Dashboard() {
  const [user, setUser] = useState<string | undefined>(undefined);
  const [heatTab, setHeatTab] = useState<"stock" | "industry" | "concept">("stock");
  const [dayPreset, setDayPreset] = useState<number>(7);          // 0 = 自定义
  const [customDays, setCustomDays] = useState<number>(14);
  const activeDays = dayPreset === 0 ? customDays : dayPreset;

  const { data: users } = useUsers();
  const { data, isLoading } = useOverview(user, activeDays);
  const { mode } = useThemeMode();
  const isMobile = useIsMobile();
  const dark = mode === "dark";
  const userName = users?.find((u) => u.id === user)?.name;

  /** 大V 名称 → user_id 映射，用于点击姓名跳转 AI 总结 */
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

  // ── 月度柱状图 ──
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

  // ── 日历热力图（PC 端） ──
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

  // ── 移动端：近12周条形图 ──
  const last12weeks = useMemo(() => {
    const map = new Map<string, number>();
    days_data.forEach((d) => {
      // 取"年-周"分组
      const dt = new Date(d.date);
      const year = dt.getFullYear();
      // ISO 周数近似（取一年第几周）
      const start = new Date(year, 0, 1);
      const week = Math.ceil(((dt.getTime() - start.getTime()) / 86400000 + start.getDay() + 1) / 7);
      const key = `${year}-W${String(week).padStart(2, "0")}`;
      map.set(key, (map.get(key) ?? 0) + d.n);
    });
    return Array.from(map.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-12);
  }, [days_data]);

  const weekBarOpt = {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 8, top: 8, bottom: 36 },
    xAxis: {
      type: "category", data: last12weeks.map(([k]) => k.replace(/\d{4}-/, "")),
      axisLabel: { rotate: 45, color: axisTextColor, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: axisTextColor, fontSize: 10 },
      splitLine: { lineStyle: { color: dark ? "#2a2e33" : "#f0f0f0" } },
    },
    series: [{
      type: "bar", data: last12weeks.map(([, v]) => v),
      itemStyle: { color: "#1668dc", borderRadius: [3, 3, 0, 0] },
    }],
  };

  const isMobile = useIsMobile();

  return (
    <Spin spinning={isLoading}>
<<<<<<< HEAD
      {/* 顶部标题 + 大V 筛选 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>看板</Typography.Title>
=======
      <Row justify="space-between" align="middle" style={{ marginBottom: 16, gap: 8 }}>
        <Typography.Title level={isMobile ? 4 : 3} style={{ margin: 0 }}>看板</Typography.Title>
>>>>>>> feature/mobile-ui-polish
        <Select
          allowClear placeholder="全部大V" style={{ width: isMobile ? 140 : 200 }} value={user}
          onChange={setUser}
          options={users?.map((u) => ({ value: u.id, label: u.name }))}
        />
      </Row>

<<<<<<< HEAD
      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={12} md={6}><Card><Statistic title="帖子总数" value={data?.total ?? 0} /></Card></Col>
        <Col xs={12} sm={12} md={6}><Card><Statistic title="大V数" value={data?.user_count ?? 0} /></Card></Col>
        <Col xs={12} sm={12} md={6}><Card><Statistic title="活跃天数" value={data?.active_days ?? 0} /></Card></Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="时间跨度" value={`${data?.first ?? "-"} ~ ${data?.last ?? "-"}`} valueStyle={{ fontSize: 14 }} /></Card>
        </Col>
      </Row>
=======
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
>>>>>>> feature/mobile-ui-polish

      {/* 热度榜 */}
      <Card
<<<<<<< HEAD
        style={{ marginTop: 16 }}
        title={
          <Space wrap size={[8, 8]}>
            <span>🔥 看多热度榜</span>
            {/* 时间段选择 */}
            <Segmented
              size="small"
              value={dayPreset}
              onChange={(v) => setDayPreset(v as number)}
              options={DAY_OPTIONS}
            />
            {/* 自定义天数输入 */}
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
        }
=======
        title={isMobile ? "看多热度榜" : "看多热度榜（近7天）"}
        style={{ marginTop: isMobile ? 8 : 16 }}
>>>>>>> feature/mobile-ui-polish
        extra={
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
        }
      >
        {heatTab === "stock" && (
<<<<<<< HEAD
          <StockHeatList
            items={data?.bullish_heat ?? []}
            isLoading={isLoading}
            daysLabel={daysLabel}
            nameToId={nameToId}
          />
        )}
        {heatTab === "industry" && (
          <BoardHeatList
            boards={data?.bullish_heat_boards ?? []}
            isLoading={isLoading}
            daysLabel={daysLabel}
            kind="industry"
            nameToId={nameToId}
          />
        )}
        {heatTab === "concept" && (
          <BoardHeatList
            boards={data?.bullish_heat_boards ?? []}
            isLoading={isLoading}
            daysLabel={daysLabel}
            kind="concept"
            nameToId={nameToId}
          />
        )}
      </Card>

      {/* 图表区：热力图 + 月度柱状图 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="发帖热力（按天）">
            {isMobile ? (
              /* 移动端：近12周条形图，无需横向滚动 */
              <ReactECharts option={weekBarOpt} style={{ height: 180 }} />
            ) : (
              /* PC端：保留完整年度日历热力图，加横向滚动兜底 */
              <div style={{ overflowX: "auto" }}>
                <div style={{ minWidth: 580 }}>
                  <ReactECharts option={heatOpt} style={{ height: 160 }} />
                </div>
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="月度发帖量">
            <ReactECharts option={monthlyOpt} style={{ height: isMobile ? 180 : 160 }} />
          </Card>
        </Col>
      </Row>

      {/* 最新动态 */}
      <Card title="最新动态" style={{ marginTop: 16 }}>
=======
          (data?.bullish_heat?.length ? (
            <List<BullishHeatItem>
              key="stock"
              dataSource={data.bullish_heat}
              pagination={{
                pageSize: HEAT_PAGE_SIZE, size: "small", hideOnSinglePage: true,
                current: heatPage, onChange: setHeatPage,
              }}
              renderItem={(it, i) => (
                <List.Item style={isMobile ? { padding: "8px 0" } : undefined}>
                  <List.Item.Meta
                    title={
                      <Space size={isMobile ? 4 : 8} wrap>
                        <span style={{ color: "#888" }}>{(heatPage - 1) * HEAT_PAGE_SIZE + i + 1}</span>
                        <Link to={`/stock/${it.code}`}>{it.name}</Link>
                        <span className={pctClass(it.change_pct)}>{fmtNum(it.close)} {fmtPct(it.change_pct)}</span>
                        <Tag color="volcano">{it.bullish_count} 位大V看多</Tag>
                      </Space>
                    }
                    description={<Space size={[4, 4]} wrap>{it.bullish_users.map((u) => <Tag key={u}>{u}</Tag>)}</Space>}
                  />
                </List.Item>
              )}
            />
          ) : <Empty description={isLoading ? "加载中" : "近7天暂无大V看多判定"} />)
        )}
        {(heatTab === "industry" || heatTab === "concept") && (() => {
          const boards = (data?.bullish_heat_boards ?? []).filter((b) =>
            heatTab === "industry" ? b.kind === "industry" : b.kind === "concept"
          );
          return boards.length ? (
            <List<BullishHeatBoard>
              key={heatTab}
              dataSource={boards}
              pagination={{
                pageSize: HEAT_PAGE_SIZE, size: "small", hideOnSinglePage: true,
                current: heatPage, onChange: setHeatPage,
              }}
              renderItem={(it, i) => (
                <List.Item style={isMobile ? { padding: "8px 0" } : undefined}>
                  <List.Item.Meta
                    title={
                      <Space size={isMobile ? 4 : 8} wrap>
                        <span style={{ color: "#888" }}>{(heatPage - 1) * HEAT_PAGE_SIZE + i + 1}</span>
                        <span>{it.sector}</span>
                        <Tag color="volcano">{it.bullish_stock_count} 只股票被看多</Tag>
                        <Tag>{it.bullish_user_count} 位大V</Tag>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={2} style={{ width: "100%" }}>
                        <Space size={[4, 4]} wrap>
                          {it.bullish_stocks.map((s) => (
                            <Tag key={s.code}><Link to={`/stock/${s.code}`}>{s.name}</Link></Tag>
                          ))}
                        </Space>
                        <Space size={[4, 4]} wrap>
                          {it.bullish_users.map((u) => <Tag key={u}>{u}</Tag>)}
                        </Space>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          ) : <Empty description={isLoading ? "加载中" : "近7天暂无数据"} />;
        })()}
      </Card>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginTop: isMobile ? 8 : 16 }}>
        <Col xs={24} md={12}>
          <Card title="发帖热力（按天）"><ReactECharts option={heatOpt} style={{ height: isMobile ? 180 : 220 }} /></Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="月度发帖量"><ReactECharts option={monthlyOpt} style={{ height: isMobile ? 180 : 220 }} /></Card>
        </Col>
      </Row>

      <Card title="最新动态" style={{ marginTop: isMobile ? 8 : 16 }}>
>>>>>>> feature/mobile-ui-polish
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
<<<<<<< HEAD
                    <Space wrap size={[4, 2]}>
                      <span style={{ fontWeight: 600 }}>{p.user_name}</span>
                      <span style={{ color: "#888", fontSize: 12 }}>{p.date}</span>
                      {p.title && <span>{p.title}</span>}
                    </Space>
                  }
                  description={<div style={{ maxHeight: 40, overflow: "hidden", fontSize: 13, color: "#666" }}>{p.text}</div>}
=======
                    <>
                      {p.user_name} · <span style={{ color: "#888" }}>{p.date}</span> {p.title}
                      {isMobile && <a href={p.url} target="_blank" rel="noreferrer" style={{ marginLeft: 8 }}>原帖</a>}
                    </>
                  }
                  description={<div style={{ maxHeight: 44, overflow: "hidden" }}>{p.text}</div>}
>>>>>>> feature/mobile-ui-polish
                />
              </List.Item>
            )}
          />
        ) : <Empty description="暂无数据，请先在后台采集" />}
      </Card>
    </Spin>
  );
}
