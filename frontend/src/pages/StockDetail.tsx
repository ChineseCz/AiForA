import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Card, Col, Descriptions, Empty, List, Row, Space, Spin, Tag, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import { Link, useParams } from "react-router-dom";

import { useFundamentals, useKline, useNews } from "@/api/hooks";
import type { KlineBar } from "@/api/types";
import { fmtNum, fmtYi } from "@/util";

function buildOption(bars: KlineBar[]) {
  const dates = bars.map((b) => b.trade_date);
  const candle = bars.map((b) => [b.open, b.close, b.low, b.high]);
  const buys: { name: string; coord: [string, number]; itemStyle: { color: string } }[] = [];
  const sells: typeof buys = [];
  bars.forEach((b) => {
    if (b.strict_ok || b.loose_ok || b.golden_ok)
      buys.push({ name: b.strict_ok ? "严格买点" : b.golden_ok ? "金叉" : "宽松买点", coord: [b.trade_date, b.low], itemStyle: { color: "#cf1322" } });
    if (b.mid_reverse_ok || b.stop_loss_ok)
      sells.push({ name: b.mid_reverse_ok ? "中期反转" : "止损", coord: [b.trade_date, b.high], itemStyle: { color: "#389e0d" } });
  });

  return {
    animation: false,
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    legend: { data: ["K线", "MA5", "MA10", "MA20", "DIF", "DEA", "MACD", "K", "D", "J"], top: 0 },
    grid: [
      { left: 50, right: 20, top: 30, height: "38%" },
      { left: 50, right: 20, top: "46%", height: "12%" },
      { left: 50, right: 20, top: "62%", height: "16%" },
      { left: 50, right: 20, top: "82%", height: "16%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false }, boundaryGap: true },
      { type: "category", data: dates, gridIndex: 1, axisLabel: { show: false } },
      { type: "category", data: dates, gridIndex: 2, axisLabel: { show: false } },
      { type: "category", data: dates, gridIndex: 3, axisLabel: { rotate: 30 } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0 },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
      { scale: true, gridIndex: 2 },
      { scale: true, gridIndex: 3 },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1, 2, 3], start: 60, end: 100 },
      { type: "slider", xAxisIndex: [0, 1, 2, 3], bottom: 0, start: 60, end: 100, height: 16 },
    ],
    series: [
      {
        name: "K线", type: "candlestick", data: candle,
        itemStyle: { color: "#cf1322", color0: "#389e0d", borderColor: "#cf1322", borderColor0: "#389e0d" },
        markPoint: { symbolSize: 44, data: [...buys, ...sells], label: { fontSize: 9 } },
      },
      { name: "MA5", type: "line", data: bars.map((b) => b.ma5), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: "MA10", type: "line", data: bars.map((b) => b.ma10), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: "MA20", type: "line", data: bars.map((b) => b.ma20), smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: bars.map((b) => b.volume), itemStyle: { color: "#8090a6" } },
      { name: "DIF", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => b.dif), showSymbol: false, lineStyle: { width: 1 } },
      { name: "DEA", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => b.dea), showSymbol: false, lineStyle: { width: 1 } },
      { name: "MACD", type: "bar", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => b.macd),
        itemStyle: { color: (p: { data: number }) => (p.data >= 0 ? "#cf1322" : "#389e0d") } },
      { name: "K", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.k), showSymbol: false, lineStyle: { width: 1 } },
      { name: "D", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.d), showSymbol: false, lineStyle: { width: 1 } },
      { name: "J", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.j), showSymbol: false, lineStyle: { width: 1 } },
    ],
  };
}

export default function StockDetail() {
  const { code = "" } = useParams();
  const { data: kline, isLoading } = useKline(code);
  const { data: fund } = useFundamentals(code);
  const { data: news } = useNews(code);

  const fin = fund?.finance as Record<string, unknown> | null;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Space>
        <Link to="/screener"><Button icon={<ArrowLeftOutlined />}>返回</Button></Link>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {kline?.name || code} <Typography.Text type="secondary">{code}</Typography.Text>
        </Typography.Title>
      </Space>

      <Card title="日线 · MA / MACD / KDJ · 买卖点">
        <Spin spinning={isLoading}>
          {kline?.bars?.length ? (
            <ReactECharts option={buildOption(kline.bars)} style={{ height: 620 }} notMerge />
          ) : <Empty description="暂无K线数据（需先在后台回补历史K线）" />}
        </Spin>
      </Card>

      <Row gutter={16}>
        <Col span={8}>
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
        <Col span={8}>
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
        <Col span={8}>
          <Card title="相关新闻" size="small" styles={{ body: { maxHeight: 420, overflow: "auto" } }}>
            {news?.items?.length ? (
              <List size="small" dataSource={news.items}
                renderItem={(n) => (
                  <List.Item>
                    <a href={n.url} target="_blank" rel="noreferrer">
                      <Typography.Text type="secondary">{n.date}</Typography.Text> {n.title}
                    </a>
                  </List.Item>
                )} />
            ) : <Empty description="暂无新闻" />}
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
