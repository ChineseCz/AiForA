import { Card, DatePicker, Input, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";

import { usePosts, useUsers } from "@/api/hooks";
import type { PostItem } from "@/api/types";

export default function Posts() {
  const [user, setUser] = useState<string | undefined>();
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(30);

  const { data: users } = useUsers();
  const { data, isFetching } = usePosts({
    user,
    start: range?.[0] ? range[0].format("YYYY-MM-DD") : "",
    end: range?.[1] ? range[1].format("YYYY-MM-DD") : "",
    q,
    page,
    size,
  });

  const columns: ColumnsType<PostItem> = [
    { title: "大V", dataIndex: "user_name", width: 130 },
    { title: "日期", dataIndex: "date", width: 110 },
    {
      title: "内容",
      dataIndex: "text",
      render: (t: string, r) => (
        <div>
          {r.title && <div style={{ fontWeight: 600 }}>{r.title}</div>}
          <div style={{ color: "#444" }}>{t}</div>
        </div>
      ),
    },
    {
      title: "互动", width: 200,
      render: (_: unknown, r) => (
        <Space size={4} wrap>
          <Tag>赞{r.like_count}</Tag><Tag>转{r.retweet_count}</Tag>
          <Tag>评{r.reply_count}</Tag><Tag>收{r.fav_count}</Tag>
        </Space>
      ),
    },
    { title: "", width: 60, render: (_: unknown, r) => <a href={r.url} target="_blank" rel="noreferrer">原帖</a> },
  ];

  return (
    <Card
      title={<Typography.Title level={4} style={{ margin: 0 }}>帖子流</Typography.Title>}
      extra={
        <Space wrap>
          <Select allowClear placeholder="全部大V" style={{ width: 160 }} value={user}
            onChange={(v) => { setUser(v); setPage(1); }}
            options={users?.map((u) => ({ value: u.id, label: u.name }))} />
          <DatePicker.RangePicker value={range as never} onChange={(v) => { setRange(v as never); setPage(1); }} />
          <Input.Search placeholder="关键词，如 半导体" allowClear style={{ width: 220 }}
            onSearch={(v) => { setQ(v); setPage(1); }} />
        </Space>
      }
    >
      <Table<PostItem>
        rowKey="id"
        loading={isFetching}
        columns={columns}
        dataSource={data?.items ?? []}
        pagination={{
          current: page, pageSize: size, total: data?.total ?? 0,
          showSizeChanger: true, pageSizeOptions: [15, 30, 50, 100],
          onChange: (p, s) => { setPage(p); setSize(s); },
          showTotal: (t) => `共 ${t} 条`,
        }}
      />
    </Card>
  );
}
// dayjs 引入以确保 RangePicker 使用同一实例
void dayjs;
