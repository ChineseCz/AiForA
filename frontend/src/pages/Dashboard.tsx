import { Card, Col, Empty, List, Row, Select, Spin, Statistic, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import { useState } from "react";

import { useOverview, useUsers } from "@/api/hooks";
import { usePageContext } from "@/pageContext";
import { useThemeMode } from "@/theme";

export default function Dashboard() {
  const [user, setUser] = useState<string | undefined>(undefined);
  const { data: users } = useUsers();
  const { data, isLoading } = useOverview(user);
  const { mode } = useThemeMode();
  const dark = mode === "dark";
  const userName = users?.find((u) => u.id === user)?.name;

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
    xAxis: { type: "category", data: data?.monthly.map((m) => m.ym) ?? [], axisLabel: { rotate: 45, color: axisTextColor } },
    yAxis: { type: "value", axisLabel: { color: axisTextColor }, splitLine: { lineStyle: { color: dark ? "#2a2e33" : "#f0f0f0" } } },
    series: [{ type: "bar", data: data?.monthly.map((m) => m.n) ?? [], itemStyle: { color: "#1668dc" } }],
  };

  // 仿 GitHub 贡献图：离散色阶方块 + 方块间留白缝隙，不用连续渐变的色块热力图
  const days = data?.daily ?? [];
  const maxN = Math.max(1, ...days.map((d) => d.n));
  const years = Array.from(new Set(days.map((d) => d.date.slice(0, 4)))).sort();
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
      data: days.filter((d) => d.date.startsWith(calYear)).map((d) => [d.date, d.n]),
    }],
  };

  return (
    <Spin spinning={isLoading}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>看板</Typography.Title>
        <Select
          allowClear placeholder="全部大V" style={{ width: 200 }} value={user}
          onChange={setUser}
          options={users?.map((u) => ({ value: u.id, label: u.name }))}
        />
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={12} sm={12} md={6}><Card><Statistic title="帖子总数" value={data?.total ?? 0} /></Card></Col>
        <Col xs={12} sm={12} md={6}><Card><Statistic title="大V数" value={data?.user_count ?? 0} /></Card></Col>
        <Col xs={12} sm={12} md={6}><Card><Statistic title="活跃天数" value={data?.active_days ?? 0} /></Card></Col>
        <Col xs={24} sm={12} md={6}><Card><Statistic title="时间跨度" value={`${data?.first ?? "-"} ~ ${data?.last ?? "-"}`} valueStyle={{ fontSize: 14 }} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="发帖热力（按天）"><ReactECharts option={heatOpt} style={{ height: 220 }} /></Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="月度发帖量"><ReactECharts option={monthlyOpt} style={{ height: 220 }} /></Card>
        </Col>
      </Row>

      <Card title="最新动态" style={{ marginTop: 16 }}>
        {data?.latest?.length ? (
          <List
            dataSource={data.latest}
            renderItem={(p) => (
              <List.Item extra={<a href={p.url} target="_blank" rel="noreferrer">原帖</a>}>
                <List.Item.Meta
                  title={<>{p.user_name} · <span style={{ color: "#888" }}>{p.date}</span> {p.title}</>}
                  description={<div style={{ maxHeight: 44, overflow: "hidden" }}>{p.text}</div>}
                />
              </List.Item>
            )}
          />
        ) : <Empty description="暂无数据，请先在后台采集" />}
      </Card>
    </Spin>
  );
}
