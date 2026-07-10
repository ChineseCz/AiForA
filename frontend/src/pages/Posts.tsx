import {
  CommentOutlined, LikeOutlined, RetweetOutlined, StarOutlined,
} from "@ant-design/icons";
import {
  Card, DatePicker, Empty, Grid, Input, Pagination, Select, Space, Typography,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";

import { usePosts, useUsers } from "@/api/hooks";
import type { PostItem } from "@/api/types";
import { usePageContext } from "@/pageContext";

const { useBreakpoint } = Grid;

// 信息流卡片，仿雪球动态列表：头像 + 大V/日期，标题+正文，配图缩略图，底部互动数据 + 原帖链接
function PostCard({ post }: { post: PostItem }) {
  return (
    <div className="post-card">
      <div className="post-card-head">
        <div className="post-avatar">{post.user_name.slice(0, 1)}</div>
        <div className="post-head-text">
          <div className="post-user">{post.user_name}</div>
          <div className="post-date">{post.date}</div>
        </div>
      </div>
      {post.title && <div className="post-title">{post.title}</div>}
      <div className="post-text">{post.text}</div>
      {post.images?.length ? (
        <div className="post-images">
          {post.images.map((src) => (
            <a key={src} href={src} target="_blank" rel="noreferrer">
              <img src={src} alt="配图" loading="lazy" />
            </a>
          ))}
        </div>
      ) : null}
      <div className="post-footer">
        <span className="post-action"><RetweetOutlined /> {post.retweet_count}</span>
        <span className="post-action"><CommentOutlined /> {post.reply_count}</span>
        <span className="post-action"><LikeOutlined /> {post.like_count}</span>
        <span className="post-action"><StarOutlined /> {post.fav_count}</span>
        <a className="post-action post-action-link" href={post.url} target="_blank" rel="noreferrer">原帖</a>
      </div>
    </div>
  );
}

export default function Posts() {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
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
  const userName = users?.find((u) => u.id === user)?.name;

  usePageContext(
    `用户在"帖子流"页。${userName ? `筛选大V：${userName}。` : "未筛选大V。"}` +
    `${q ? `关键词：${q}。` : ""}当前第 ${page} 页，共 ${data?.total ?? 0} 条帖子` +
    (data?.items?.length ? `，本页前几条标题/摘要：${
      data.items.slice(0, 5).map((p) => `「${p.title || p.text.slice(0, 20)}」`).join("、")
    }。` : "。"),
  );

  return (
    <Card
      title={<Typography.Title level={4} style={{ margin: 0 }}>帖子流</Typography.Title>}
      styles={{ body: { padding: isMobile ? "8px 12px" : "12px 20px" } }}
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
      {data?.items?.length ? (
        data.items.map((p) => <PostCard key={p.id} post={p} />)
      ) : <Empty description={isFetching ? "加载中…" : "暂无数据"} />}
      {!!data?.total && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
          <Pagination
            simple={isMobile} showSizeChanger={!isMobile} pageSizeOptions={[15, 30, 50, 100]}
            current={page} pageSize={size} total={data.total}
            onChange={(p, s) => { setPage(p); setSize(s); }}
          />
        </div>
      )}
    </Card>
  );
}
// dayjs 引入以确保 RangePicker 使用同一实例
void dayjs;
