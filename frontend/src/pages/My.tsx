import { DeleteOutlined, FolderOutlined, PlusOutlined, StarFilled, StarOutlined, UploadOutlined } from "@ant-design/icons";
import {
  AutoComplete, Button, Col, DatePicker, Empty, Form, Input, InputNumber,
  Modal, Pagination, Popconfirm, Progress, Row, Select, Space, Spin, Table, Tabs,
  Tag, Tooltip, Typography, Upload, message, theme,
} from "antd";
import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { errMsg, api } from "../api/client";
import { useQueryClient } from "@tanstack/react-query";
import { useGroupMembers, useGroupMutations, useGroups, useDeleteNote, useFavoriteNote, useGenerateNote, useNote, useNoteList, useNoteMutation, useTradeMutations, useTrades, useTradeStats } from "../api/hooks";
import { getToken, getVisitorToken } from "../api/client";
import type { GroupItem, GroupMember, TradeNote, TradeRecord } from "../api/types";
import { useIsMobile } from "../hooks/useIsMobile";
import dayjs from "dayjs";

const { Text } = Typography;

const AUTO_GROUP_NAMES = new Set(["持仓", "清仓"]);

// ─── 自选股 ──────────────────────────────────────────────────────────────────

function WatchlistTab({ isPaper = false }: { isPaper?: boolean }) {
  const isMobile = useIsMobile();
  const { token } = theme.useToken();
  const { data: groupsData, isLoading: loadingGroups } = useGroups(isPaper);
  const groups = (groupsData?.groups ?? []) as GroupItem[];
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: membersData, isLoading: loadingMembers } = useGroupMembers(selectedId);
  const members = (membersData?.items ?? []) as GroupMember[];
  const muts = useGroupMutations(isPaper);

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [addCode, setAddCode] = useState("");
  const [addStockName, setAddStockName] = useState("");

  const handleCreate = () => {
    const name = newName.trim();
    if (!name) { message.warning("请输入分组名"); return; }
    muts.create.mutate(name, {
      onSuccess: (resp) => {
        message.success("已创建");
        setCreateOpen(false);
        setNewName("");
        const g = (resp as any)?.group;
        if (g?.id) setSelectedId(g.id);
      },
      onError: (e) => message.error(errMsg(e, "创建失败")),
    });
  };

  const handleDeleteGroup = (id: number) => {
    muts.remove.mutate(id, {
      onSuccess: () => {
        message.success("已删除");
        if (selectedId === id) setSelectedId(null);
      },
      onError: (e) => message.error(errMsg(e, "删除失败")),
    });
  };

  const handleAddMember = () => {
    if (!selectedId) return;
    const code = addCode.trim();
    if (!code) { message.warning("请输入股票代码"); return; }
    muts.addMembers.mutate(
      { id: selectedId, stocks: [{ code, name: addStockName.trim() }] },
      {
        onSuccess: () => { message.success("已添加"); setAddOpen(false); setAddCode(""); setAddStockName(""); },
        onError: (e) => message.error(errMsg(e, "添加失败")),
      },
    );
  };

  const memberCols = [
    { title: "代码", dataIndex: "code", width: 90 },
    {
      title: "名称",
      dataIndex: "name",
      ellipsis: true,
      render: (name: string, row: GroupMember) => <Link to={`/stock/${row.code}`}>{name}</Link>,
    },
    {
      title: "最新价",
      dataIndex: "close",
      width: 80,
      render: (v: number) => (v != null ? v.toFixed(2) : "–"),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 90,
      render: (v: number) => {
        if (v == null) return "–";
        const color = v > 0 ? token.colorError : v < 0 ? token.colorSuccess : undefined;
        return <Text style={{ color }}>{v > 0 ? "+" : ""}{v.toFixed(2)}%</Text>;
      },
    },
    {
      title: "",
      dataIndex: "code",
      key: "del",
      width: 50,
      render: (code: string) => {
        const isAuto = !isPaper && AUTO_GROUP_NAMES.has(selectedGroup?.name ?? "");
        if (isAuto) return null;
        return (
          <Popconfirm title="移除该股票？" onConfirm={() =>
            muts.removeMember.mutate(
              { groupId: selectedId!, code },
              { onError: (e) => message.error(errMsg(e, "移除失败")) },
            )
          }>
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        );
      },
    },
  ];

  const selectedGroup = groups.find((g) => g.id === selectedId);

  return (
    <Row gutter={[16, 16]}>
      {/* 左：分组列表 */}
      <Col xs={24} sm={8}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <Text strong>我的分组</Text>
          <Button size="small" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建</Button>
        </div>
        {loadingGroups ? (
          <Spin />
        ) : groups.length === 0 ? (
          <Empty description="暂无分组" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {groups.map((g) => {
              const active = selectedId === g.id;
              const isAuto = !isPaper && AUTO_GROUP_NAMES.has(g.name ?? "");
              return (
                <div
                  key={g.id}
                  onClick={() => setSelectedId(g.id)}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 6,
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    background: active ? token.colorPrimaryBg : token.colorFillQuaternary,
                    border: `1px solid ${active ? token.colorPrimary : "transparent"}`,
                    transition: "all 0.15s",
                  }}
                >
                  <Space>
                    <FolderOutlined style={{ color: active ? token.colorPrimary : undefined }} />
                    <span>{g.name}</span>
                    <Tag style={{ margin: 0 }}>{g.member_count}</Tag>
                  </Space>
                  {isAuto ? (
                    <Tooltip title="自动维护，不可手动删除">
                      <Button type="text" size="small" icon={<DeleteOutlined />} disabled onClick={(e) => e.stopPropagation()} />
                    </Tooltip>
                  ) : (
                    <Popconfirm
                      title="删除该分组及其成员？"
                      onConfirm={() => handleDeleteGroup(g.id)}
                    >
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Col>

      {/* 右：成员列表 */}
      <Col xs={24} sm={16}>
        {selectedId == null ? (
          <Empty description="选择左侧分组查看成员" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 40 }} />
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <Text strong>{selectedGroup?.name ?? "成员列表"}</Text>
              {(!isPaper && !AUTO_GROUP_NAMES.has(selectedGroup?.name ?? "")) && (
                <Button size="small" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>添加股票</Button>
              )}
            </div>
            <Table
              dataSource={members}
              columns={memberCols}
              rowKey="code"
              loading={loadingMembers}
              size="small"
              pagination={false}
              locale={{ emptyText: (!isPaper && AUTO_GROUP_NAMES.has(selectedGroup?.name ?? "")) ? "暂无数据（交易记录同步后自动更新）" : "暂无成员，点击「添加股票」" }}
              scroll={{ x: isMobile ? 360 : undefined }}
            />
          </>
        )}
      </Col>

      {/* 新建分组 Modal */}
      <Modal
        title="新建分组"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        confirmLoading={muts.create.isPending}
      >
        <Input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="分组名称"
          onPressEnter={handleCreate}
          maxLength={20}
        />
      </Modal>

      {/* 添加股票 Modal */}
      <Modal
        title="添加股票"
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        onOk={handleAddMember}
        confirmLoading={muts.addMembers.isPending}
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input
            value={addCode}
            onChange={(e) => setAddCode(e.target.value)}
            placeholder="股票代码（如 600519）"
            maxLength={10}
          />
          <Input
            value={addStockName}
            onChange={(e) => setAddStockName(e.target.value)}
            placeholder="股票名称（选填，系统自动匹配）"
            maxLength={20}
          />
        </Space>
      </Modal>
    </Row>
  );
}

// ─── 操作复盘 ─────────────────────────────────────────────────────────────────

function pnlSummary(trades: TradeRecord[]) {
  // 均价法：买入时更新持仓均价，卖出时才计算已实现盈亏
  const sorted = [...trades].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  const map: Record<string, { name: string; avgCost: number; holdQty: number; realized: number }> = {};
  for (const t of sorted) {
    if (!map[t.code]) map[t.code] = { name: t.stock_name, avgCost: 0, holdQty: 0, realized: 0 };
    const m = map[t.code];
    if (t.direction === "buy") {
      const totalCost = m.avgCost * m.holdQty + t.price * t.quantity;
      m.holdQty += t.quantity;
      m.avgCost = m.holdQty > 0 ? totalCost / m.holdQty : 0;
    } else {
      m.realized += (t.price - m.avgCost) * t.quantity;
      m.holdQty = Math.max(0, m.holdQty - t.quantity);
    }
  }
  return Object.entries(map)
    .filter(([, v]) => v.holdQty > 0)
    .map(([code, v]) => ({
      code,
      name: v.name,
      realized: v.realized,
      netQty: v.holdQty,
      avgCost: v.avgCost,
    }));
}

function StatsCards({ isPaper = false }: { isPaper?: boolean }) {
  const { token } = theme.useToken();
  const { data } = useTradeStats(isPaper);
  const s = data?.stats;
  if (!s || s.total_sell_trades === 0) return null;
  const pnlColor = s.total_realized_pnl > 0 ? token.colorError : s.total_realized_pnl < 0 ? token.colorSuccess : undefined;
  const prefix = isPaper ? "(模拟)" : "";
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
      {[
        { label: `${prefix}胜率`, value: `${(s.win_rate * 100).toFixed(1)}%`, sub: `${s.wins}只盈利 ${s.losses}只亏损 / ${s.total_stocks ?? s.wins + s.losses}只股票` },
        { label: "平均盈", value: `+${s.avg_win.toFixed(0)}`, sub: "元/笔", color: token.colorError },
        { label: "平均亏", value: `-${s.avg_loss.toFixed(0)}`, sub: "元/笔", color: token.colorSuccess },
        { label: "盈亏比", value: s.profit_factor != null ? s.profit_factor.toFixed(2) : "–", sub: "盈/亏" },
        { label: `${prefix}总已实现盈亏`, value: `${s.total_realized_pnl > 0 ? "+" : ""}${s.total_realized_pnl.toFixed(0)}`, sub: "元", color: pnlColor },
      ].map(({ label, value, sub, color }) => (
        <div key={label} style={{
          background: token.colorFillQuaternary,
          borderRadius: 8, padding: "8px 14px", minWidth: 100, flex: "1 0 auto",
        }}>
          <div style={{ fontSize: 11, color: token.colorTextSecondary }}>{label}</div>
          <div style={{ fontSize: 20, fontWeight: 600, color }}>{value}</div>
          <div style={{ fontSize: 11, color: token.colorTextTertiary }}>{sub}</div>
        </div>
      ))}
    </div>
  );
}

function ReviewTab({ isPaper = false }: { isPaper?: boolean }) {
  const isMobile = useIsMobile();
  const { token } = theme.useToken();
  const [filterCode, setFilterCode] = useState<string | undefined>(undefined);
  const { data, isLoading } = useTrades(filterCode, isPaper);
  const trades = (data?.items ?? []) as TradeRecord[];
  const muts = useTradeMutations(isPaper);

  const [addOpen, setAddOpen] = useState(false);
  const [form] = Form.useForm();
  const [stockOpts, setStockOpts] = useState<{ value: string; label: string; code: string }[]>([]);

  const handleStockSearch = async (q: string) => {
    if (!q) { setStockOpts([]); return; }
    try {
      const res = await api.get<{ items: { code: string; name: string }[] }>("/api/stock/search", { params: { q } });
      setStockOpts(res.data.items.map((it) => ({ value: it.name, label: `${it.name}（${it.code}）`, code: it.code })));
    } catch { setStockOpts([]); }
  };

  const handleStockSelect = (_val: string, opt: { code: string }) => {
    form.setFieldValue("code", opt.code);
  };

  const handleAdd = () => {
    form.validateFields().then((vals) => {
      muts.create.mutate(
        { ...vals, trade_date: vals.trade_date.format("YYYY-MM-DD"), note: vals.note ?? "" },
        {
          onSuccess: () => { message.success("已记录"); setAddOpen(false); form.resetFields(); },
          onError: (e) => message.error(errMsg(e, "记录失败")),
        },
      );
    });
  };

  const tradeCols = [
    { title: "日期", dataIndex: "trade_date", width: 100 },
    { title: "代码", dataIndex: "code", width: 80 },
    { title: "名称", dataIndex: "stock_name", ellipsis: true },
    {
      title: "方向",
      dataIndex: "direction",
      width: 60,
      render: (v: string) => (
        <Tag color={v === "buy" ? "red" : "green"}>{v === "buy" ? "买入" : "卖出"}</Tag>
      ),
    },
    { title: "价格", dataIndex: "price", width: 80, render: (v: number) => v?.toFixed(2) },
    { title: "数量", dataIndex: "quantity", width: 70 },
    {
      title: "金额",
      key: "amount",
      width: 90,
      render: (_: unknown, r: TradeRecord) => (((r.price ?? 0) * (r.quantity ?? 0)).toFixed(0)),
    },
    { title: "备注", dataIndex: "note", ellipsis: true },
    {
      title: "",
      key: "del",
      width: 50,
      render: (_: unknown, r: TradeRecord) => (
        <Popconfirm
          title="删除该记录？"
          onConfirm={() =>
            muts.remove.mutate(r.id, { onError: (e) => message.error(errMsg(e, "删除失败")) })
          }
        >
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const summary = !filterCode ? pnlSummary(trades) : [];

  return (
    <>
      <StatsCards isPaper={isPaper} />
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <Input.Search
          placeholder="按代码筛选"
          allowClear
          style={{ width: 160 }}
          onSearch={(v) => setFilterCode(v || undefined)}
          onChange={(e) => { if (!e.target.value) setFilterCode(undefined); }}
        />
        <Button icon={<PlusOutlined />} type="primary" onClick={() => setAddOpen(true)}>
          添加记录
        </Button>
        {!isPaper && (
          <Upload
            accept=".txt"
            showUploadList={false}
            customRequest={({ file }) => {
              muts.importTxt.mutate(file as File, {
                onSuccess: (res) => message.success(`导入 ${res.imported} 条（共识别 ${res.total} 条）`),
                onError: (e) => message.error(errMsg(e, "导入失败")),
              });
            }}
          >
            <Button icon={<UploadOutlined />} loading={muts.importTxt.isPending}>导入TXT</Button>
          </Upload>
        )}
      </div>

      <Table
        dataSource={trades}
        columns={tradeCols}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: false }}
        locale={{ emptyText: "暂无交易记录" }}
        scroll={{ x: isMobile ? 560 : undefined }}
      />

      {summary.length > 0 && (
        <>
          <div style={{ marginTop: 20, marginBottom: 8 }}>
            <Text strong>持仓概览</Text>
          </div>
          <Table
            dataSource={summary}
            rowKey="code"
            size="small"
            pagination={false}
            columns={[
              { title: "代码", dataIndex: "code", width: 80 },
              { title: "名称", dataIndex: "name", ellipsis: true },
              {
                title: "持仓均价",
                dataIndex: "avgCost",
                width: 100,
                render: (v: number | null) => v != null ? v.toFixed(2) : "–",
              },
              {
                title: "持仓股数",
                dataIndex: "netQty",
                width: 90,
                render: (v: number) => (
                  <Text type={v > 0 ? "warning" : v < 0 ? "danger" : "secondary"}>{v}</Text>
                ),
              },
              {
                title: "已实现盈亏",
                dataIndex: "realized",
                width: 120,
                render: (v: number) => {
                  if (v === 0) return <Text type="secondary">–</Text>;
                  const color = v > 0 ? token.colorError : token.colorSuccess;
                  return <Text style={{ color }}>{v > 0 ? "+" : ""}{v.toFixed(0)}</Text>;
                },
              },
            ]}
          />
        </>
      )}

      <Modal
        title="添加交易记录"
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        onOk={handleAdd}
        confirmLoading={muts.create.isPending}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="stock_name" label="股票名称（输入名称自动匹配代码）">
            <AutoComplete
              options={stockOpts}
              onSearch={handleStockSearch}
              onSelect={handleStockSelect}
              placeholder="输入名称或代码搜索，如 贵州茅台"
              allowClear
            />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="code" label="股票代码" rules={[{ required: true, message: "必填" }]}>
                <Input placeholder="如 600519" maxLength={10} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="direction" label="方向" rules={[{ required: true, message: "必填" }]}>
                <Select
                  options={[
                    { value: "buy", label: "买入" },
                    { value: "sell", label: "卖出" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="trade_date" label="交易日期" rules={[{ required: true, message: "必填" }]}>
                <DatePicker style={{ width: "100%" }} format="YYYY-MM-DD" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="price" label="成交价格" rules={[{ required: true, message: "必填" }]}>
                <InputNumber min={0.01} precision={2} style={{ width: "100%" }} placeholder="元" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quantity" label="数量（股）" rules={[{ required: true, message: "必填" }]}>
                <InputNumber min={1} step={100} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="note" label="备注">
            <Input.TextArea rows={2} maxLength={200} placeholder="选填" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

// ─── 复盘笔记 ─────────────────────────────────────────────────────────────────

function renderBracketToken(key: string, inner: string, replaceAt: (s: string) => void): React.ReactNode {
  if (inner === "✓是") {
    return <span key={key} style={{ background: "#f6ffed", color: "#52c41a", border: "1px solid #b7eb8f", borderRadius: 4, padding: "0 6px", cursor: "pointer", fontSize: 12, margin: "0 2px" }} onClick={() => replaceAt("【是/否】")}>✓ 是</span>;
  }
  if (inner === "✗否") {
    return <span key={key} style={{ background: "#fff2f0", color: "#ff4d4f", border: "1px solid #ffccc7", borderRadius: 4, padding: "0 6px", cursor: "pointer", fontSize: 12, margin: "0 2px" }} onClick={() => replaceAt("【是/否】")}>✗ 否</span>;
  }
  if (inner.includes("/") || inner.includes("、")) {
    const sep = inner.includes("/") ? "/" : "、";
    const singleSelect = sep === "/";
    const opts = inner.split(sep);
    const handleClick = (oi: number) => {
      const isSel = opts[oi].startsWith("✓");
      const newOpts = opts.map((o, i) => {
        const clean = o.startsWith("✓") ? o.slice(1) : o;
        if (i !== oi) return singleSelect ? clean : o;
        return isSel ? clean : "✓" + clean;
      });
      replaceAt("【" + newOpts.join(sep) + "】");
    };
    return (
      <span key={key} style={{ display: "inline-flex", flexWrap: "wrap", gap: 2, margin: "0 2px" }}>
        {opts.map((opt, oi) => {
          const isSel = opt.startsWith("✓");
          const label = isSel ? opt.slice(1) : opt;
          return (
            <span key={oi} onClick={() => handleClick(oi)}
              style={{ background: isSel ? "#f6ffed" : "transparent", color: isSel ? "#52c41a" : "#595959", border: `1px solid ${isSel ? "#b7eb8f" : "#d9d9d9"}`, borderRadius: 4, padding: "0 5px", cursor: "pointer", fontSize: 12, whiteSpace: "nowrap" }}>
              {isSel ? "✓ " : ""}{label}
            </span>
          );
        })}
      </span>
    );
  }
  if (/^_+$/.test(inner) || inner.startsWith("~") || inner === "填写" || inner === "请填写" || inner === "输入") {
    const val = inner.startsWith("~") ? inner.slice(1) : "";
    return (
      <input key={key} type="text" value={val} placeholder="____"
        onChange={(e) => { const v = e.target.value; replaceAt(v ? "【~" + v + "】" : "【____】"); }}
        style={{ border: "none", borderBottom: "1px solid #aaa", background: "transparent", fontSize: 13, color: "inherit", outline: "none", padding: "0 2px", width: Math.max(40, val.length * 14 + 16) + "px" }}
      />
    );
  }
  return <span key={key} style={{ color: "#d48806", background: "#fffbe6", borderRadius: 3, padding: "0 3px", fontSize: 13 }}>{"【" + inner + "】"}</span>;
}

function renderNoteContent(
  content: string,
  onChange: (s: string) => void,
): React.ReactNode {
  const lines = content.split("\n");
  return (
    <>
      {lines.map((line, li) => {
        let lineStart = 0;
        for (let i = 0; i < li; i++) lineStart += lines[i].length + 1;

        const hm = line.match(/^##\s+(.+?)(?:\s*\((\d{6})\))?\s*$/);
        if (hm) {
          const [, title, code] = hm;
          return (
            <div key={li} style={{ fontSize: 14, fontWeight: 600, marginTop: li > 0 ? 10 : 0, marginBottom: 2, borderLeft: "3px solid #1677ff", paddingLeft: 8 }}>
              {code ? <Link to={`/stock/${code}`} style={{ color: "inherit" }}>{title}({code})</Link> : title}
            </div>
          );
        }

        const parts: React.ReactNode[] = [];
        let last = 0;
        let ti = 0;
        let match: RegExpExecArray | null;
        const re = /【([^】]*)】|\*\*([^*\n]+)\*\*|==([^=\n]+)==/g;
        while ((match = re.exec(line)) !== null) {
          if (match.index > last)
            parts.push(<span key={`${li}_s${last}`}>{line.slice(last, match.index)}</span>);
          const absPos = lineStart + match.index;
          if (match[1] !== undefined) {
            const inner = match[1];
            const full = match[0];
            const replaceAt = (next: string) => onChange(content.slice(0, absPos) + next + content.slice(absPos + full.length));
            parts.push(renderBracketToken(`${li}_t${ti++}`, inner, replaceAt));
          } else if (match[2] !== undefined) {
            parts.push(<strong key={`${li}_b${ti++}`}>{match[2]}</strong>);
          } else {
            parts.push(<mark key={`${li}_m${ti++}`} style={{ background: "#fff3cd", color: "#d46b08", borderRadius: 2, padding: "0 2px" }}>{match[3]}</mark>);
          }
          last = re.lastIndex;
        }
        if (last < line.length)
          parts.push(<span key={`${li}_s${last}`}>{line.slice(last)}</span>);

        return <div key={li} style={{ minHeight: "1.4em" }}>{parts}</div>;
      })}
    </>
  );
}

function NotesTab({ isPaper = false }: { isPaper?: boolean }) {
  const isMobile = useIsMobile();
  const { token } = theme.useToken();
  const today = dayjs().format("YYYY-MM-DD");
  const [selectedDate, setSelectedDate] = useState(today);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState(false);
  const [batchRange, setBatchRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; date: string } | null>(null);
  const [regenLoading, setRegenLoading] = useState(false);
  const [regenProgress, setRegenProgress] = useState<{ current: number; total: number; date: string } | null>(null);
  const [searchRange, setSearchRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [page, setPage] = useState(1);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const PAGE_SIZE = 20;

  const { data: listData } = useNoteList(
    searchRange?.[0]?.format("YYYY-MM-DD"),
    searchRange?.[1]?.format("YYYY-MM-DD"),
    page,
    PAGE_SIZE,
    favoriteOnly,
    isPaper,
  );
  const noteList = (listData?.items ?? []) as TradeNote[];
  const noteTotal = listData?.total ?? 0;

  useEffect(() => {
    if (noteTotal > 0 && noteList.length === 0 && page > 1) setPage(page - 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [noteTotal, noteList.length]);

  const handleSearchRangeChange = (v: [dayjs.Dayjs, dayjs.Dayjs] | null) => {
    setSearchRange(v);
    setPage(1);
  };
  const { data: noteData } = useNote(selectedDate, isPaper);
  const saveMut = useNoteMutation(isPaper);
  const genMut = useGenerateNote(isPaper);
  const deleteMut = useDeleteNote(isPaper);
  const favoriteMut = useFavoriteNote(isPaper);
  const qc = useQueryClient();
  const batchAbortRef = useRef<AbortController | null>(null);
  const regenAbortRef = useRef<AbortController | null>(null);

  const handleBatchGenerate = async () => {
    if (!batchRange) return;
    setBatchLoading(true);
    setBatchProgress(null);
    const ac = new AbortController();
    batchAbortRef.current = ac;
    try {
      const token = getToken() || getVisitorToken();
      const resp = await fetch("/api/notes/batch-generate", {
        method: "POST",
        signal: ac.signal,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          start_date: batchRange[0].format("YYYY-MM-DD"),
          end_date: batchRange[1].format("YYYY-MM-DD"),
          is_paper: isPaper,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        message.error(err?.error || err?.detail || "批量生成失败");
        return;
      }
      const reader = resp.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.done) {
            if (data.generated === 0) {
              message.info("所选时间段内无交易记录");
            } else {
              message.success(`已生成 ${data.generated} 天的笔记`);
              qc.invalidateQueries({ queryKey: ["notes"] });
            }
            setBatchRange(null);
          } else {
            setBatchProgress({ current: data.progress, total: data.total, date: data.date });
            qc.invalidateQueries({ queryKey: ["notes"] });
          }
        }
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") {
        message.info("已停止生成");
        qc.invalidateQueries({ queryKey: ["notes"] });
      } else {
        message.error("批量生成失败");
      }
    } finally {
      setBatchLoading(false);
      setBatchProgress(null);
      batchAbortRef.current = null;
    }
  };

  const handleRegenAll = async () => {
    setRegenLoading(true);
    setRegenProgress(null);
    const ac = new AbortController();
    regenAbortRef.current = ac;
    try {
      const token = getToken() || getVisitorToken();
      const resp = await fetch(`/api/notes/regen-all${isPaper ? "?is_paper=true" : ""}`, {
        method: "POST",
        signal: ac.signal,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        message.error(err?.error || err?.detail || "更新失败");
        return;
      }
      const reader = resp.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.done) {
            message.success(`已更新 ${data.generated} 篇笔记`);
            qc.invalidateQueries({ queryKey: ["notes"] });
            qc.invalidateQueries({ queryKey: ["note"] });
          } else {
            setRegenProgress({ current: data.progress, total: data.total, date: data.date });
            qc.invalidateQueries({ queryKey: ["notes"] });
          }
        }
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") {
        message.info("已停止更新");
        qc.invalidateQueries({ queryKey: ["notes"] });
        qc.invalidateQueries({ queryKey: ["note"] });
      } else {
        message.error("更新失败");
      }
    } finally {
      setRegenLoading(false);
      setRegenProgress(null);
      regenAbortRef.current = null;
    }
  };

  useEffect(() => {
    if (!dirty) setContent(noteData?.note?.content ?? "");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [noteData?.note?.content, selectedDate]);

  const handleSelectDate = (d: string) => {
    setSelectedDate(d);
    setDirty(false);
  };

  const handleSave = () => {
    saveMut.mutate(
      { date: selectedDate, content },
      {
        onSuccess: () => { message.success("已保存"); setDirty(false); },
        onError: (e) => message.error(errMsg(e, "保存失败")),
      },
    );
  };

  return (
    <Row gutter={[16, 16]}>
      {/* 左：历史列表 */}
      <Col xs={24} sm={7}>
        <Text strong style={{ display: "block", marginBottom: 8 }}>历史笔记</Text>
        <DatePicker.RangePicker
          size="small"
          format="YYYY-MM-DD"
          placeholder={["按日期搜索", "结束日期"]}
          value={searchRange}
          onChange={(v) => handleSearchRangeChange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
          allowClear
          style={{ marginBottom: 8, width: "100%" }}
        />
        <Button
          size="small"
          type={favoriteOnly ? "primary" : "default"}
          icon={favoriteOnly ? <StarFilled /> : <StarOutlined />}
          onClick={() => { setFavoriteOnly((v) => !v); setPage(1); }}
          style={{ marginBottom: 8 }}
        >
          只看收藏
        </Button>
        <Space style={{ marginBottom: 8, flexWrap: "wrap" }}>
          <DatePicker.RangePicker
            size="small"
            format="YYYY-MM-DD"
            value={batchRange}
            onChange={(v) => setBatchRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            allowClear
          />
          <Button
            size="small"
            loading={batchLoading}
            disabled={!batchRange || regenLoading}
            onClick={handleBatchGenerate}
          >
            {batchProgress ? `生成中 ${batchProgress.current}/${batchProgress.total}` : "批量AI生成"}
          </Button>
          {batchLoading && (
            <Button size="small" danger onClick={() => batchAbortRef.current?.abort()}>
              停止
            </Button>
          )}
          <Button
            size="small"
            loading={regenLoading}
            disabled={batchLoading || noteList.length === 0}
            onClick={handleRegenAll}
          >
            {regenProgress ? `更新中 ${regenProgress.current}/${regenProgress.total}` : "一键更新"}
          </Button>
          {regenLoading && (
            <Button size="small" danger onClick={() => regenAbortRef.current?.abort()}>
              停止
            </Button>
          )}
        </Space>
        {(batchProgress || regenProgress) && (
          <div style={{ marginBottom: 8 }}>
            <Progress
              percent={
                batchProgress
                  ? Math.round((batchProgress.current / batchProgress.total) * 100)
                  : Math.round((regenProgress!.current / regenProgress!.total) * 100)
              }
              size="small"
              status="active"
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {batchProgress
                ? `正在生成 ${batchProgress.date}（${batchProgress.current}/${batchProgress.total}）`
                : `正在更新 ${regenProgress!.date}（${regenProgress!.current}/${regenProgress!.total}）`}
            </Text>
          </div>
        )}
        {noteList.length === 0 ? (
          <Empty description="暂无笔记" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div style={{
            display: "flex", flexDirection: "column", gap: 4,
            maxHeight: isMobile ? 180 : 440, overflowY: "auto",
          }}>
            {noteList.map((n) => {
              const active = selectedDate === n.note_date;
              return (
                <div
                  key={n.note_date}
                  onClick={() => handleSelectDate(n.note_date)}
                  style={{
                    padding: "6px 10px", borderRadius: 6, cursor: "pointer",
                    background: active ? token.colorPrimaryBg : token.colorFillQuaternary,
                    border: `1px solid ${active ? token.colorPrimary : "transparent"}`,
                    display: "flex", justifyContent: "space-between", alignItems: "flex-start",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: active ? 600 : undefined, fontSize: 13 }}>{n.note_date}</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {n.content.split("\n")[0].slice(0, 24)}{n.content.length > 24 ? "…" : ""}
                    </Text>
                  </div>
                  <Button
                    type="text" size="small"
                    icon={n.is_favorite ? <StarFilled style={{ color: "#faad14" }} /> : <StarOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      favoriteMut.mutate(n.note_date, { onError: (err) => message.error(errMsg(err, "操作失败")) });
                    }}
                  />
                  <Popconfirm
                    title="删除该笔记？"
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      deleteMut.mutate(n.note_date, {
                        onSuccess: () => {
                          message.success("已删除");
                          if (selectedDate === n.note_date) { setContent(""); setDirty(false); }
                        },
                        onError: (err) => message.error(errMsg(err, "删除失败")),
                      });
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      type="text" danger size="small" icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                </div>
              );
            })}
          </div>
        )}
        {noteTotal > PAGE_SIZE && (
          <div style={{ marginTop: 8, textAlign: "center" }}>
            <Pagination
              size="small"
              current={page}
              total={noteTotal}
              pageSize={PAGE_SIZE}
              onChange={setPage}
              showSizeChanger={false}
            />
          </div>
        )}
      </Col>

      {/* 右：编辑区 */}
      <Col xs={24} sm={17}>
        <Space style={{ marginBottom: 10, flexWrap: "wrap" }}>
          <DatePicker
            value={dayjs(selectedDate)}
            onChange={(d) => d && handleSelectDate(d.format("YYYY-MM-DD"))}
            format="YYYY-MM-DD"
            allowClear={false}
          />
          <Button type="primary" onClick={handleSave} loading={saveMut.isPending} disabled={!dirty}>
            保存
          </Button>
          <Button
            onClick={() => {
              genMut.mutate(selectedDate, {
                onSuccess: (res) => { setContent(res.content ?? ""); setDirty(true); setPreview(true); },
                onError: (e) => message.error(errMsg(e, "生成失败")),
              });
            }}
            loading={genMut.isPending}
          >
            AI生成模板
          </Button>
          <Button onClick={() => setPreview((p) => !p)}>
            {preview ? "编辑" : "预览"}
          </Button>
          {dirty && <Text type="secondary" style={{ fontSize: 12 }}>有未保存的修改</Text>}
        </Space>
        {preview ? (
          <div style={{
            border: `1px solid ${token.colorBorder}`,
            borderRadius: 8,
            padding: "10px 14px",
            minHeight: isMobile ? 300 : 440,
            fontSize: 14,
            lineHeight: 2,
            overflowY: "auto",
            background: token.colorBgContainer,
            cursor: "text",
          }}>
            {content
              ? renderNoteContent(content, (s) => { setContent(s); setDirty(true); })
              : <Text type="secondary">暂无内容，点击"编辑"开始记录或"AI生成模板"。</Text>}
          </div>
        ) : (
          <Input.TextArea
            value={content}
            onChange={(e) => { setContent(e.target.value); setDirty(true); }}
            rows={isMobile ? 14 : 22}
            placeholder={"记录今日复盘思路…\n\n例：\n000063 中兴通讯\n买点符合公式，卖点止盈执行良好。"}
            style={{ resize: "vertical" }}
          />
        )}
      </Col>
    </Row>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function My() {
  const innerItems = (isPaper: boolean) => [
    { key: "watchlist", label: "自选股", children: <WatchlistTab isPaper={isPaper} /> },
    { key: "review", label: "操作复盘", children: <ReviewTab isPaper={isPaper} /> },
    { key: "notes", label: "复盘笔记", children: <NotesTab isPaper={isPaper} /> },
  ];
  return (
    <Tabs
      defaultActiveKey="real"
      destroyInactiveTabPane
      items={[
        {
          key: "real",
          label: "实盘",
          children: (
            <Tabs defaultActiveKey="watchlist" destroyInactiveTabPane items={innerItems(false)} />
          ),
        },
        {
          key: "paper",
          label: "模拟盘",
          children: (
            <Tabs defaultActiveKey="watchlist" destroyInactiveTabPane items={innerItems(true)} />
          ),
        },
      ]}
    />
  );
}
