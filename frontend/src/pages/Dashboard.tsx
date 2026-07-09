import { Card, Col, Empty, List, Row, Select, Spin, Statistic, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import { useState } from "react";

import { useOverview, useUsers } from "@/api/hooks";

export default function Dashboard() {
  const [user, setUser] = useState<string | undefined>(undefined);
  const { data: users } = useUsers();
  const { data, isLoading } = useOverview(user);

  const monthlyOpt = {
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 16, top: 20, bottom: 40 },
    xAxis: { type: "category", data: data?.monthly.map((m) => m.ym) ?? [], axisLabel: { rotate: 45 } },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: data?.monthly.map((m) => m.n) ?? [], itemStyle: { color: "#1668dc" } }],
  };

  const days = data?.daily ?? [];
  const maxN = Math.max(1, ...days.map((d) => d.n));
  const years = Array.from(new Set(days.map((d) => d.date.slice(0, 4)))).sort();
  const calYear = years[years.length - 1] ?? new Date().getFullYear().toString();
  const heatOpt = {
    tooltip: { formatter: (p: { value: [string, number] }) => `${p.value[0]}：${p.value[1]} 条` },
    visualMap: { min: 0, max: maxN, show: false, inRange: { color: ["#e6f0ff", "#1668dc"] } },
    calendar: { range: calYear, cellSize: ["auto", 14], right: 16, left: 40, top: 20 },
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

      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="帖子总数" value={data?.total ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="大V数" value={data?.user_count ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="活跃天数" value={data?.active_days ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="时间跨度" value={`${data?.first ?? "-"} ~ ${data?.last ?? "-"}`} valueStyle={{ fontSize: 14 }} /></Card></Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card title="发帖热力（按天）"><ReactECharts option={heatOpt} style={{ height: 220 }} /></Card>
        </Col>
        <Col span={12}>
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
