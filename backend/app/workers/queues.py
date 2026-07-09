"""队列名常量（Phase 1 预留，Phase 2 使用）。

关键：QUEUE_BROWSER 隔离浏览器依赖任务（抓取 / K线回补），由 Windows 宿主 worker 消费
（真实 Edge + 持久化 profile，无法容器化）。其余任务走 QUEUE_DEFAULT / QUEUE_LLM，可容器化。
"""
QUEUE_DEFAULT = "default"      # 快照 / 财务 / 板块同步（纯 requests，可容器化）
QUEUE_BROWSER = "browser"      # 抓取 / K线回补（真实 Edge，Windows 宿主专用）
QUEUE_LLM = "llm"              # AI 总结（LLM 调用）
