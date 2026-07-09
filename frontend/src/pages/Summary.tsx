import { Button, Card, Col, Empty, Input, List, Row, Select, Space, Tabs, Typography, message } from "antd";
import { useEffect, useState } from "react";

import { errMsg } from "@/api/client";
import { useAsk, useSummary, useSummaryKeys, useUsers } from "@/api/hooks";

const TABS = [
  { key: "daily", label: "日" }, { key: "weekly", label: "周" }, { key: "monthly", label: "月" },
  { key: "yearly", label: "年" }, { key: "highlights", label: "精华" },
];

export default function Summary() {
  const { data: users } = useUsers();
  const [user, setUser] = useState<string>("");
  const [type, setType] = useState("daily");
  const [key, setKey] = useState("");
  const [question, setQuestion] = useState("");

  useEffect(() => {
    if (!user && users?.length) setUser(users[0].id);
  }, [users, user]);

  const { data: keys } = useSummaryKeys(user, type);
  const { data: summary } = useSummary(user, type, key);
  const ask = useAsk();

  useEffect(() => { setKey(keys?.[0] ?? ""); }, [keys, type, user]);

  const doAsk = () => {
    if (!question.trim()) return;
    ask.mutate(
      { user, type, key, question },
      { onError: (e) => message.error(errMsg(e)) },
    );
  };

  return (
    <Card
      title={<Typography.Title level={4} style={{ margin: 0 }}>AI 总结</Typography.Title>}
      extra={
        <Select style={{ width: 200 }} value={user || undefined} placeholder="选择大V"
          onChange={setUser} options={users?.map((u) => ({ value: u.id, label: u.name }))} />
      }
    >
      <Tabs activeKey={type} onChange={setType} items={TABS.map((t) => ({ ...t, children: null }))} />
      <Row gutter={16}>
        <Col span={6}>
          <List
            size="small" bordered style={{ maxHeight: 480, overflow: "auto" }}
            dataSource={keys ?? []}
            locale={{ emptyText: "无总结，去后台生成" }}
            renderItem={(k) => (
              <List.Item
                onClick={() => setKey(k)}
                style={{ cursor: "pointer", background: k === key ? "#e6f0ff" : undefined }}
              >
                {k}
              </List.Item>
            )}
          />
        </Col>
        <Col span={18}>
          {summary?.found ? (
            <div className="markdown-body" dangerouslySetInnerHTML={{ __html: summary.html }} />
          ) : (
            <Empty description="选择左侧日期查看总结；若为空，请在管理后台生成" />
          )}
        </Col>
      </Row>

      <Card type="inner" title="向 AI 提问（基于当前总结）" style={{ marginTop: 16 }}>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            placeholder="例如：这段时间提到最多的是哪几只股票？"
            value={question} onChange={(e) => setQuestion(e.target.value)} onPressEnter={doAsk}
            disabled={!summary?.found}
          />
          <Button type="primary" loading={ask.isPending} onClick={doAsk} disabled={!summary?.found}>提问</Button>
        </Space.Compact>
        {ask.data && (
          <div className="markdown-body" style={{ marginTop: 12 }}
            dangerouslySetInnerHTML={{ __html: ask.data.html }} />
        )}
      </Card>
    </Card>
  );
}
