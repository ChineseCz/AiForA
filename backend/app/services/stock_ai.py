"""个股AI综合分析：把K线技术指标 + 财务基本面组装成 prompt，调用 relay LLM 生成中文解读。"""
from openai import OpenAI

from app.core.config import settings
from app.services import views

DISCLAIMER = (
    "> ⚠️ 本报告由 AI 自动整理自公开的技术指标与财务数据，仅供参考，"
    "**不构成任何投资建议**。模型可能出错或遗漏，请独立判断，投资有风险。\n"
)

SYSTEM_PROMPT = (
    "你是一名严谨的中文股票分析助理。任务是阅读某只A股的技术指标数据和财务数据，"
    "客观解读当前技术面与基本面状况。严格遵守：\n"
    "1. 只基于给定的数据做客观解读，不编造数据中没有的信息。\n"
    "2. 不给出'建议买入/卖出/加仓/减仓'等具体操作指令，只描述现状和可能的含义。\n"
    "3. 区分'技术面信号'和'基本面数据'两部分分别解读，再给一个综合小结。\n"
    "4. 输出简洁的中文 Markdown，按要求的结构组织，不要输出免责声明（由系统统一附加）。"
)


def _build_prompt(code: str, kline: dict, fund: dict) -> str | None:
    bars = kline.get("bars") or []
    if not bars:
        return None
    latest = bars[-1]
    recent = bars[-10:]
    trend_lines = "\n".join(
        f"- {b['trade_date']}: 收盘{b['close']} MA5={b['ma5']} MA10={b['ma10']} MA20={b['ma20']} "
        f"MACD={b['macd']} K={b['k']} D={b['d']} 严格买点={b['strict_ok']} 宽松买点={b['loose_ok']} "
        f"金叉买点={b['golden_ok']} 中期反转={b['mid_reverse_ok']} 短期止损={b['stop_loss_ok']}"
        for b in recent
    )

    fin = fund.get("finance") or {}
    quote = fund.get("quote") or {}
    sectors = [s.get("sector") for s in (fund.get("sectors") or []) if s.get("sector")]

    return f"""股票：{kline.get('name') or code}（{code}）

【最新一日技术指标】
收盘价 {latest['close']}，MA5/10/20：{latest['ma5']}/{latest['ma10']}/{latest['ma20']}
MACD DIF/DEA/MACD：{latest['dif']}/{latest['dea']}/{latest['macd']}
KDJ K/D/J：{latest['k']}/{latest['d']}/{latest['j']}

【近10日走势与信号】
{trend_lines}

【估值与财务】
市盈率(动) {quote.get('pe_ttm')}，市净率 {quote.get('pb')}，总市值(万元) {quote.get('total_mv')}
EPS {fin.get('eps')}，ROE(%) {fin.get('roe')}，净利润同比(%) {fin.get('net_profit_yoy')}
营收同比(%) {fin.get('revenue_yoy')}，毛利率(%) {fin.get('gross_margin')}，报告期 {fin.get('report_date')}
所属板块：{'、'.join(sectors) if sectors else '未知'}

请按以下结构输出中文解读：

## {kline.get('name') or code} 技术面+基本面解读
### 技术面
（均线排列、MACD/KDJ状态、近期买卖点信号的含义）
### 基本面
（估值水平、盈利能力、成长性的客观解读；若财务数据为空，注明"暂无财务数据"）
### 综合小结
（两者结合的客观现状描述，不给操作建议）
"""


def generate_stock_analysis(code: str) -> dict:
    """同步调用 LLM，返回 {"content": str, "error": str}。应在 run_in_threadpool 里调用。"""
    kline = views.get_kline_view(code)
    fund = views.get_fundamentals_view(code)

    prompt = _build_prompt(code, kline, fund)
    if prompt is None:
        return {"content": "", "error": "暂无K线数据，无法生成分析（需先在后台回补历史K线）"}

    client = OpenAI(api_key=settings.relay_api_key, base_url=settings.relay_api_url)
    resp = client.chat.completions.create(
        model=settings.relay_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )
    content = (resp.choices[0].message.content or "").strip()
    return {"content": content + "\n\n" + DISCLAIMER if content else "", "error": "" if content else "生成失败，请重试"}
