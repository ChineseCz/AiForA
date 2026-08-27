import { ReloadOutlined, WifiOutlined } from "@ant-design/icons";
import { Alert, Button, Result } from "antd";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

type NetworkIssue = "offline" | "server" | "timeout" | null;

function issueText(issue: NetworkIssue) {
  if (issue === "offline") return { title: "当前没有网络连接", description: "请检查手机网络或 Wi-Fi，网络恢复后点击重试。" };
  if (issue === "timeout") return { title: "服务器响应超时", description: "服务器或网络线路响应较慢，请稍后重试。" };
  return { title: "服务器暂时不可用", description: "接口连接失败，可能正在部署或重启，请稍后重试。" };
}

export default function NetworkStatus() {
  const queryClient = useQueryClient();
  const [issue, setIssue] = useState<NetworkIssue>(() => (navigator.onLine === false ? "offline" : null));
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    const offline = () => setIssue("offline");
    const online = () => setIssue((current) => current === "offline" ? null : current);
    const failed = (event: Event) => {
      const kind = (event as CustomEvent<{ kind?: NetworkIssue }>).detail?.kind;
      setIssue(kind === "timeout" ? "timeout" : "server");
    };
    const recovered = () => setIssue(null);
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    window.addEventListener("natapp-network-error", failed);
    window.addEventListener("natapp-network-recovered", recovered);
    return () => {
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
      window.removeEventListener("natapp-network-error", failed);
      window.removeEventListener("natapp-network-recovered", recovered);
    };
  }, []);

  const retry = async () => {
    if (navigator.onLine === false) {
      setIssue("offline");
      return;
    }
    setRetrying(true);
    try {
      await queryClient.refetchQueries({ type: "active" });
      setIssue(null);
    } catch {
      setIssue("server");
    } finally {
      setRetrying(false);
    }
  };

  if (!issue) return null;
  const text = issueText(issue);

  if (issue === "offline") {
    return (
      <div className="network-error-page">
        <Result
          icon={<WifiOutlined />}
          title={text.title}
          subTitle={text.description}
          extra={<Button type="primary" icon={<ReloadOutlined />} onClick={retry} loading={retrying}>重试连接</Button>}
        />
      </div>
    );
  }

  return (
    <Alert
      className="network-error-banner"
      type="warning"
      showIcon
      message={text.title}
      description={text.description}
      action={
        <Button size="small" icon={<ReloadOutlined />} onClick={retry} loading={retrying}>重试</Button>
      }
    />
  );
}
