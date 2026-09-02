import {
  CommentOutlined, DownOutlined, LikeOutlined, RetweetOutlined, SearchOutlined, StarOutlined, UpOutlined,
} from "@ant-design/icons";
import {
  Button, Card, Collapse, DatePicker, Empty, Input, List, Pagination, Select, Space, Tabs, Typography, message, theme,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { errMsg } from "@/api/client";
import { useAsk, usePosts, useSummary, useSummaryKeys, useUsers } from "@/api/hooks";
import MarkdownContent from "@/components/MarkdownContent";
import BigvReviewPanel from "@/components/BigvReviewPanel";
import { useIsMobile } from "@/hooks/useIsMobile";
import { usePageContext } from "@/pageContext";
import type { PostItem } from "@/api/types";
import { displayPeriodKey } from "@/utils/period";

// ──────────────────────────────────────────────
// 帖子流 Tab
// ──────────────────────────────────────────────

function PostCard({ post }: { post: PostItem }) {
  const [expanded, setExpanded] = useState(false);
  const hasBrief = !!post.brief;
  const showFull = expanded || !hasBrief;

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
      <div className="post-text">{showFull ? post.text : post.brief}</div>
      {post.images?.length ? (
        <div className={showFull ? "post-images" : "post-images post-images-thumb"}>
          {post.images.map((src) => (
            <a key={src} href={src} target="_blank" rel="noreferrer">
              <img src={src} alt="配图" loading="lazy" />
            </a>
          ))}
        </div>
      ) : null}
      {hasBrief && (
        <button type="button" className="post-expand-btn" onClick={() => setExpanded((v) => !v)}>
          {expanded ? <>收起 <UpOutlined /></> : <>展开阅读全文 <DownOutlined /></>}
        </button>
      )}
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

function PostsTab({ active }: { active: boolean }) {
  const isMobile = useIsMobile();
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
    active
      ? `用户在"帖子流"。${userName ? `筛选大V：${userName}。` : "未筛选大V。"}` +
        `${q ? `关键词：${q}。` : ""}当前第 ${page} 页，共 ${data?.total ?? 0} 条帖子` +
        (data?.items?.length
          ? `，本页前几条标题/摘要：${data.items.slice(0, 5).map((p) => `「${p.title || p.text.slice(0, 20)}」`).join("、")}。`
          : "。")
      : "",
  );

  return (
    <Card styles={{ body: { padding: isMobile ? "8px 12px" : "12px 20px" } }}>
      <div className="post-filter-bar">
        <Select allowClear placeholder="全部大V" style={{ width: isMobile ? 120 : 160 }} value={user}
          onChange={(v) => { setUser(v); setPage(1); }}
          options={users?.map((u) => ({ value: u.id, label: u.name }))} />
        <DatePicker.RangePicker value={range as never} onChange={(v) => { setRange(v as never); setPage(1); }}
          style={{ flex: isMobile ? "1 1 100%" : undefined }} />
        <Input.Search prefix={<SearchOutlined style={{ color: "var(--text-secondary)" }} />}
          placeholder="关键词，如 半导体" allowClear
          style={{ width: isMobile ? "100%" : 220, flex: isMobile ? "1 1 100%" : undefined }}
          onSearch={(v) => { setQ(v); setPage(1); }} />
      </div>
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

// ──────────────────────────────────────────────
// AI 总结 Tab
// ──────────────────────────────────────────────

const SUMMARY_PERIOD_TABS = [
  { key: "daily", label: "日" }, { key: "weekly", label: "周" }, { key: "monthly", label: "月" },
  { key: "yearly", label: "年" }, { key: "highlights", label: "精华" },
];

function SummaryTab({ active, initialUserId }: { active: boolean; initialUserId?: string }) {
  const { token } = theme.useToken();
  const isMobile = useIsMobile();
  const { data: users } = useUsers();
  const [user, setUser] = useState<string>("");
  const [type, setType] = useState("daily");
  const [key, setKey] = useState("");
  const [question, setQuestion] = useState("");
  const [listOpen, setListOpen] = useState(false);
  const initialSet = useRef(false);

  useEffect(() => {
    if (!users?.length || initialSet.current) return;
    initialSet.current = true;
    if (initialUserId) { setUser(initialUserId); return; }
    const preferred = users.find((u) => u.name === "冰冰小美");
    setUser((preferred ?? users[0]).id);
  }, [users, initialUserId]);

  const { data: keys } = useSummaryKeys(user, type);
  const { data: summary } = useSummary(user, type, key);
  const ask = useAsk();

  useEffect(() => { setKey(keys?.[0] ?? ""); }, [keys, type, user]);

  const userName = users?.find((u) => u.id === user)?.name;
  usePageContext(
    active
      ? `用户在"AI总结"，看的是大V「${userName ?? user}」的${type}总结，当前日期/期号：${key || "（未选）"}。` +
        (summary?.found ? `总结正文（markdown原文）：\n${summary.raw?.slice(0, 1500) ?? ""}` : "这份总结还没生成或为空。")
      : "",
  );

  const doAsk = () => {
    if (!question.trim()) return;
    ask.mutate({ user, type, key, question }, { onError: (e) => message.error(errMsg(e)) });
  };

  return (
    <Card
      extra={
        <Select style={{ width: isMobile ? 130 : 200 }} value={user || undefined} placeholder="选择大V"
          onChange={setUser} options={users?.map((u) => ({ value: u.id, label: u.name }))} />
      }
    >
      <Tabs activeKey={type} onChange={setType} size={isMobile ? "small" : "middle"}
        items={SUMMARY_PERIOD_TABS.map((t) => ({ ...t, children: null }))} />
      <Collapse
        size="small"
        style={{ marginBottom: isMobile ? 8 : 16 }}
        activeKey={listOpen ? ["dates"] : []}
        onChange={(k) => setListOpen((k as string[]).includes("dates"))}
        items={[{
          key: "dates",
          label: key ? `日期：${displayPeriodKey(type, key)}` : "选择日期",
          children: (
            <List
              size="small" style={{ maxHeight: 360, overflow: "auto" }}
              dataSource={keys ?? []}
              locale={{ emptyText: "无总结，去后台生成" }}
              renderItem={(k) => (
                <List.Item
                  onClick={() => { setKey(k); setListOpen(false); }}
                  style={{ cursor: "pointer", background: k === key ? token.colorPrimaryBg : undefined }}
                >
                  {displayPeriodKey(type, k)}
                </List.Item>
              )}
            />
          ),
        }]}
      />
      {summary?.found ? (
        <MarkdownContent className="markdown-body" html={summary.html} />
      ) : (
        <Empty description="点击上方展开选择日期查看总结；若为空，请在管理后台生成" />
      )}
      <Card type="inner" title={isMobile ? "AI 问答" : "向 AI 提问（基于当前总结）"} style={{ marginTop: isMobile ? 8 : 16 }}>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            placeholder="例如：这段时间提到最多的是哪几只股票？"
            value={question} onChange={(e) => setQuestion(e.target.value)} onPressEnter={doAsk}
            disabled={!summary?.found}
          />
          <Button type="primary" loading={ask.isPending} onClick={doAsk} disabled={!summary?.found}>提问</Button>
        </Space.Compact>
        {ask.data && (
          <MarkdownContent className="markdown-body" style={{ marginTop: 12 }} html={ask.data.html} />
        )}
      </Card>
    </Card>
  );
}

// ──────────────────────────────────────────────
// 大V动态主页
// ──────────────────────────────────────────────

export default function Feed() {
  const isMobile = useIsMobile();
  const loc = useLocation();
  const stateUserId = (loc.state as { userId?: string } | null)?.userId;
  const [activeTab, setActiveTab] = useState("summary");

  return (
    <Space direction="vertical" size={0} style={{ width: "100%" }}>
      <Typography.Title level={isMobile ? 5 : 4} style={{ margin: "0 0 12px" }}>大V动态</Typography.Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size={isMobile ? "small" : "middle"}
        destroyInactiveTabPane
        items={[
          { key: "posts", label: "帖子流", children: <PostsTab active={activeTab === "posts"} /> },
          { key: "summary", label: "AI 总结", children: <SummaryTab active={activeTab === "summary"} initialUserId={stateUserId} /> },
          { key: "review", label: "观点复盘", children: <BigvReviewPanel /> },
        ]}
      />
    </Space>
  );
}

void dayjs;
