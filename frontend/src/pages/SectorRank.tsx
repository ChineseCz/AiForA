import { Card, Empty, Input, Segmented, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useSectorRank } from "@/api/hooks";
import type { SectorRankItem } from "@/api/types";
import { fmtPct, pctClass } from "@/util";
import { screenerState } from "./screenerState";

export default function SectorRank() {
  const { data, isLoading } = useSectorRank();
  const nav = useNavigate();
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
    nav("/screener", { state: { autoRun: true } });
  };

  const columns: ColumnsType<SectorRankItem> = [
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
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>板块行情</Typography.Title>

      <Card size="small">
        <Space wrap style={{ marginBottom: 12 }}>
          <Segmented value={kind} onChange={(v) => setKind(v as "industry" | "concept")}
            options={[{ label: "行业", value: "industry" }, { label: "概念题材", value: "concept" }]} />
          <Input placeholder="搜索板块名" allowClear value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 200 }} />
          {data?.trade_date && <Tag color="blue">行情日 {data.trade_date}</Tag>}
        </Space>
        {items.length ? (
          <Table<SectorRankItem> rowKey="sector" size="small" columns={columns} dataSource={items}
            loading={isLoading} pagination={{ pageSize: 30, showSizeChanger: true }} />
        ) : <Empty description={isLoading ? "加载中" : "暂无数据"} />}
      </Card>
    </Space>
  );
}
