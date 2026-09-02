import { Button, Card, Collapse, Empty, Input, List, Select, Space, Tabs, Typography, message, theme } from "antd";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { errMsg } from "@/api/client";
import { useAsk, useSummary, useSummaryKeys, useUsers } from "@/api/hooks";
import MarkdownContent from "@/components/MarkdownContent";
import { useIsMobile } from "@/hooks/useIsMobile";
import { usePageContext } from "@/pageContext";
import { displayPeriodKey } from "@/utils/period";

const TABS = [
  { key: "daily", label: "日" }, { key: "weekly", label: "周" }, { key: "monthly", label: "月" },
  { key: "yearly", label: "年" }, { key: "highlights", label: "精华" },
];

function displayKey(type: string, key: string): string {
  return displayPeriodKey(type, key);
}

export default function Summary() {
  const { token } = theme.useToken();
  const isMobile = useIsMobile();
  const { data: users } = useUsers();
  const [user, setUser] = useState<string>("");
  const [type, setType] = useState("daily");
  const [key, setKey] = useState("");
  const [question, setQuestion] = useState("");
  const [listOpen, setListOpen] = useState(false);
  const loc = useLocation();

  useEffect(() => {
    if (!users?.length) return;
    // 从看板热度榜点击大V名字跳转过来时，location.state 带有 userId，直接预选该大V
    const fromState = (loc.state as { userId?: string } | null)?.userId;
    if (fromState) {
      setUser(fromState);
      return;
    }
    if (user) return;
    const preferred = users.find((u) => u.name === "冰冰小美");
    setUser((preferred ?? users[0]).id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [users]);

  const { data: keys } = useSummaryKeys(user, type);
  const { data: summary } = useSummary(user, type, key);
  const ask = useAsk();

  useEffect(() => { setKey(keys?.[0] ?? ""); }, [keys, type, user]);

  const userName = users?.find((u) => u.id === user)?.name;
  usePageContext(
    `用户在"AI总结"页，看的是大V「${userName ?? user}」的${type}总结，当前日期/期号：${key || "（未选）"}。` +
    (summary?.found ? `总结正文（markdown原文）：\n${summary.raw?.slice(0, 1500) ?? ""}` : "这份总结还没生成或为空。"),
  );

  const doAsk = () => {
    if (!question.trim()) return;
    ask.mutate(
      { user, type, key, question },
      { onError: (e) => message.error(errMsg(e)) },
    );
  };

  return (
    <Card
      title={<Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>AI 总结</Typography.Title>}
      extra={
        <Select style={{ width: isMobile ? 130 : 200 }} value={user || undefined} placeholder="选择大V"
          onChange={setUser} options={users?.map((u) => ({ value: u.id, label: u.name }))} />
      }
    >
      <Tabs activeKey={type} onChange={setType} size={isMobile ? "small" : "middle"} items={TABS.map((t) => ({ ...t, children: null }))} />
      <Collapse
        size="small"
        style={{ marginBottom: isMobile ? 8 : 16 }}
        activeKey={listOpen ? ["dates"] : []}
        onChange={(k) => setListOpen((k as string[]).includes("dates"))}
        items={[{
          key: "dates",
          label: key ? `日期：${displayKey(type, key)}` : "选择日期",
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
                  {displayKey(type, k)}
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
