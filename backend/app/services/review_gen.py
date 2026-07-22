"""AI 每日复盘模板生成。"""
from openai import OpenAI

from app.core.config import settings


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.relay_api_key, base_url=settings.relay_api_url, max_retries=3)


def generate_daily_review(date: str, trades: list[dict], positions: dict) -> str:
    """同步调用 LLM，返回当日复盘模板字符串。应在 run_in_threadpool 里调用。"""
    if not trades:
        return f"# {date} 复盘\n\n今日无操作记录。\n"

    # 构建操作摘要
    lines = []
    for t in trades:
        direction = "买入" if t["direction"] == "buy" else "卖出"
        pos = positions.get(t["code"], {})
        extra = ""
        if t["direction"] == "buy":
            prev_qty = pos.get("hold_qty", 0) - t["quantity"]
            if prev_qty <= 0:
                extra = "（新建仓）"
            else:
                avg = pos.get("avg_cost", 0)
                extra = f"（加仓，当前均价约 {avg:.2f}）"
        else:
            avg = pos.get("avg_cost", 0)
            if avg:
                pnl = (float(t["price"]) - avg) * t["quantity"]
                sign = "+" if pnl >= 0 else ""
                extra = f"（vs 均价 {avg:.2f}，本次盈亏约 {sign}{pnl:.0f} 元）"
        lines.append(f"- {t['stock_name']}({t['code']}) {direction} {t['quantity']} 股 @ {t['price']} 元 {extra}")

    ops_text = "\n".join(lines)

    prompt = f"""你是一个严格的股票交易复盘助手。用户今日（{date}）操作如下：

{ops_text}

请为用户生成一份**中文复盘笔记模板**，严格遵守以下格式规则：

【括号格式】
- **单选**：【选项1/选项2/选项3】，例如【是/否】【上升/震荡/下降】
- **多选**：【选项1、选项2、选项3】（顿号分隔）
- **填写**：【____】，不要用"填写"两字

【关键规则：根据上方交易数据预先勾选】
- 凡是能从交易记录直接判断的选项，在正确选项前加 ✓，例如：买入方向写【✓买入/卖出】，新建仓写【✓新建仓/加仓/减仓/清仓】
- 能推断是盈利的卖出写【✓盈利/亏损】，亏损写【盈利/✓亏损】
- 无法从数据判断的主观评价（如"买点是否符合公式""操作是否冷静"）不要预选，保留原始格式让用户自行勾选

【内容结构】
- 每只股票单独一个段落，标题格式：## 股票名(代码)
- 包含：操作方向确认、买卖点纪律自评、趋势判断、本次操作评分
- 最后一段：## 今日总结，包含操作纪律、主要教训、明日关注
- 语言简练，不加废话
- 只输出正文，不要解释"""

    client = _get_client()
    resp = client.chat.completions.create(
        model=settings.relay_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1200,
        timeout=60,
    )
    return resp.choices[0].message.content or ""
