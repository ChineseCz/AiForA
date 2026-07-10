// 菲比聊天窗口：Live2D 形象本身（见 live2d.ts）挂在 body 上、独立于 React 树，
// 这里只是点开她菜单里的"找菲比聊聊"之后弹出来的对话抽屉。挂在 App.tsx 顶层，
// 登录后任意页面都能用；ensureFeibiLive2d 内部做了单例保护，重复调用不会重复挂载模型。
import { SendOutlined } from "@ant-design/icons";
import { Button, Drawer, Input, Space, Spin, message } from "antd";
import { useEffect, useRef, useState } from "react";

import { api, errMsg } from "@/api/client";
import { ensureFeibiLive2d, getFeibiInstance, setFeibiOpenHandler } from "@/live2d";
import { getPageContext } from "@/pageContext";

interface FeibiMsg { role: "user" | "assistant"; content: string; }

export default function FeibiWidget() {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<FeibiMsg[]>([
    { role: "assistant", content: "站长好呀～我是菲比，有什么想问的都可以跟我说哦！" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setFeibiOpenHandler(() => setOpen(true));
    ensureFeibiLive2d().catch((e) => console.error("菲比加载失败", e));
  }, []);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, open]);

  // 打开聊天窗口就让形象滑出画面（stageSlideOut），关闭再滑回来——她本来就停在右下角，
  // 跟从右边弹出的 Drawer 抽屉抢同一块地方，之前那版没处理，对话框内容常被她挡住看不到。
  useEffect(() => {
    const inst = getFeibiInstance();
    if (!inst) return;
    if (open) inst.stageSlideOut(); else inst.stageSlideIn();
  }, [open]);

  const send = () => {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    setHistory((h) => [...h, { role: "user", content: question }]);
    setLoading(true);
    api.post("/api/feibi/ask", { question, history, page_context: getPageContext() })
      .then((r) => setHistory((h) => [...h, { role: "assistant", content: r.data.answer }]))
      .catch((e) => message.error(errMsg(e, "菲比好像走神了，稍后再试试")))
      .finally(() => setLoading(false));
  };

  return (
    <Drawer
      title="🎀 菲比"
      placement="right"
      width={360}
      open={open}
      onClose={() => setOpen(false)}
      styles={{ body: { display: "flex", flexDirection: "column", padding: 12 } }}
    >
      <div style={{ flex: 1, overflowY: "auto", marginBottom: 8 }}>
        {history.map((m, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: 8,
          }}>
            <div style={{
              maxWidth: "80%", padding: "8px 12px", borderRadius: 12, whiteSpace: "pre-wrap",
              background: m.role === "user" ? "#1668dc" : "var(--bg-elevated)",
              color: m.role === "user" ? "#fff" : "var(--text-primary)",
            }}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && <Spin size="small" />}
        <div ref={bottomRef} />
      </div>
      <Space.Compact style={{ width: "100%" }}>
        <Input placeholder="跟菲比说点什么…" value={input} onChange={(e) => setInput(e.target.value)}
          onPressEnter={send} disabled={loading} />
        <Button type="primary" icon={<SendOutlined />} onClick={send} loading={loading} />
      </Space.Compact>
    </Drawer>
  );
}
