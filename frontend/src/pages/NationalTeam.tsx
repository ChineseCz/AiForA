import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Card, Col, Empty, List, Row, Select, Space, Statistic, Table, Tag, Typography } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useNationalTeam } from "@/api/hooks";
import type { NationalTeamHolding } from "@/api/types";
import { useIsMobile } from "@/hooks/useIsMobile";

const colors: Record<string, string> = { 新进: "blue", 增持: "red", 减持: "green", 退出披露范围: "orange", 退出: "orange", 不变: "default" };
const fmtShares = (n?: number | null) => n == null ? "-" : n >= 1e8 ? `${(n / 1e8).toFixed(2)}亿` : n >= 1e4 ? `${(n / 1e4).toFixed(2)}万` : n.toLocaleString();

export default function NationalTeam() {
  const mobile = useIsMobile();
  const [reportDate, setReportDate] = useState<string>();
  const [institution, setInstitution] = useState<string>();
  const [changeType, setChangeType] = useState<string>();
  const { data, isLoading } = useNationalTeam(reportDate, institution, changeType);
  const summary = data?.summary;
  const counts = summary?.type_counts || {};
  const columns = [
    { title: "报告期", dataIndex: "report_date", width: 110 },
    { title: "机构", dataIndex: "institution", width: mobile ? 150 : 220, ellipsis: true },
    { title: "股票", key: "stock", render: (_: unknown, r: NationalTeamHolding) => <Link to={`/stock/${r.code}`}>{r.name || r.code}</Link> },
    { title: "持股数量", dataIndex: "shares", render: fmtShares, responsive: ["md"] as ("md")[] },
    { title: "持股比例", dataIndex: "holding_ratio", render: (v: number | null) => v == null ? "-" : `${v.toFixed(2)}%` },
    { title: "变化", dataIndex: "change_type", render: (v: string | null) => <Tag color={colors[v || ""]}>{v || "-"}</Tag> },
    { title: "变化数量", dataIndex: "change_shares", render: (v: number | null) => v == null ? "-" : fmtShares(v), responsive: ["lg"] as ("lg")[] },
  ];
  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Space direction="vertical" size={2}>
        <Typography.Title level={4} style={{ margin: 0 }}>国家队持仓分析</Typography.Title>
        <Typography.Text type="secondary">报告期末公开披露数据 · 当前报告期：{data?.selected_report_date || "暂无"} · {data?.last_updated_at ? `最近同步：${new Date(data.last_updated_at * 1000).toLocaleString()}` : "尚未同步"}</Typography.Text>
      </Space>
      {summary ? <Row gutter={[12, 12]}>
        <Col xs={12} sm={6}><Card><Statistic title="披露记录" value={summary.total_rows} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="涉及股票" value={summary.stock_count} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="涉及机构" value={summary.institution_count} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="增持 / 减持" value={`${counts["增持"] || 0} / ${counts["减持"] || 0}`} /></Card></Col>
      </Row> : null}
      {summary ? <Row gutter={[12, 12]}>
        <Col xs={24} lg={10}><Card size="small" title="变化分布">
          <Space wrap>{Object.entries(counts).map(([name, count]) => <Tag key={name} color={colors[name]}>{name} {count}</Tag>)}</Space>
          <List size="small" header="团队分布" dataSource={summary.team_counts} renderItem={(item) => <List.Item><span>{item.name}</span><Typography.Text strong>{item.count} 条</Typography.Text></List.Item>} />
        </Card></Col>
        <Col xs={24} lg={14}><Card size="small" title="重点变化（按数量排序）">
          <List size="small" dataSource={summary.top_changes} renderItem={(item) => <List.Item>
            <Space><Link to={`/stock/${item.code}`}>{item.name || item.code}</Link><Tag color={colors[item.change_type]}>{item.change_type}</Tag><Typography.Text type="secondary">{item.institution}</Typography.Text></Space>
            <Typography.Text type={item.change_shares >= 0 ? "danger" : "success"}>{item.change_shares >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {fmtShares(Math.abs(item.change_shares))}</Typography.Text>
          </List.Item>} />
        </Card></Col>
      </Row> : null}
      <Card size="small"><Space wrap>
        <Select allowClear placeholder="报告期" style={{ width: 140 }} value={reportDate} onChange={setReportDate} options={data?.report_dates.map((v) => ({ value: v, label: v }))} />
        <Select allowClear placeholder="机构" style={{ width: mobile ? 210 : 280 }} value={institution} onChange={setInstitution} options={data?.institutions.map((v) => ({ value: v, label: v }))} />
        <Select allowClear placeholder="变化类型" style={{ width: 120 }} value={changeType} onChange={setChangeType} options={Object.keys(colors).map((v) => ({ value: v, label: v }))} />
      </Space></Card>
      <Card size="small" title={`持仓记录${data ? `（${data.items.length} 条）` : ""}`}>
        {data?.items.length ? <Table rowKey={(r) => `${r.report_date}-${r.institution}-${r.code}`} loading={isLoading} columns={columns} dataSource={data.items} size="small" pagination={{ pageSize: 30, showSizeChanger: false }} scroll={{ x: mobile ? 620 : undefined }} /> : <Empty description={isLoading ? "加载中" : "暂无数据，请管理员先同步国家队持仓"} />}
      </Card>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>{data?.coverage_note || "说明：增持、减持、新进和退出依据相邻报告期披露推断，不代表准确成交日期、成交价格或实时持仓。"}</Typography.Text>
    </Space>
  );
}
