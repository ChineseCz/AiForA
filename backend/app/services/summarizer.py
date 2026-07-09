"""AI 总结（LLM 队列 worker 用）：从旧 summarizer.py 忠实移植。配置读 settings，缓存写 sync_data。"""
import base64
import json

import requests
from openai import OpenAI

from app.core.config import settings
from app.repositories import sync_data as db

DISCLAIMER = (
    "> ⚠️ 本报告由 AI 自动整理自公开帖子，仅为对该作者观点的客观摘要，"
    "**不构成任何投资建议**。模型可能出错或遗漏，请回看原帖并独立判断。投资有风险。\n"
)

SYSTEM_PROMPT = (
    "你是一名严谨的中文财经内容分析助理。任务是阅读某位雪球用户的帖子，"
    "客观提炼其观点与提到的标的。严格遵守：\n"
    "1. 只整理'作者说了什么'，不替读者做买卖决策，不输出你自己的投资建议。\n"
    "2. 不编造帖子中没有的信息；不确定就标注'（不确定/未明说）'。\n"
    "3. 区分'作者的事实陈述'和'作者的主观判断'。\n"
    "4. 输出简洁的中文 Markdown，按要求的结构组织。"
)

ASK_SYSTEM_PROMPT = (
    "你是一名中文财经助理，会看到一份关于某位雪球用户观点的AI总结，以及用户针对这份总结提出的问题。"
    "严格只依据总结内容作答，不要引入总结之外的信息或你自己的投资建议；"
    "如果总结里没有能回答问题的信息，直接说明总结中未提及，不要编造。"
)


def get_client() -> OpenAI:
    if not settings.relay_api_key:
        raise RuntimeError("未配置 RELAY_API_KEY")
    return OpenAI(api_key=settings.relay_api_key, base_url=settings.relay_api_url)


def call_llm(user_content: str, system_prompt: str = SYSTEM_PROMPT) -> str:
    client = get_client()
    resp = client.chat.completions.create(
        model=settings.relay_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def ask_about_summary(summary_md: str, question: str) -> str:
    prompt = f"【总结内容】\n{summary_md}\n\n【用户问题】\n{question}"
    return call_llm(prompt, system_prompt=ASK_SYSTEM_PROMPT)


def _image_to_data_url(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️  下载配图失败 {url}：{e}")
        return None
    mime = r.headers.get("content-type", "image/jpeg").split(";")[0].strip() or "image/jpeg"
    b64 = base64.b64encode(r.content).decode("ascii")
    return f"data:{mime};base64,{b64}"


def describe_images(image_urls: list[str]) -> str:
    if not image_urls:
        return ""
    data_urls = [u for u in (_image_to_data_url(url) for url in image_urls) if u]
    if not data_urls:
        return ""
    client = get_client()
    content = [{
        "type": "text",
        "text": "请客观描述这张/这些图片的内容（如截图里的文字、图表数据、K线形态等），"
                "不要评论或给建议，直接陈述图中信息，中文回答，控制在150字以内。",
    }]
    for data_url in data_urls:
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    resp = client.chat.completions.create(
        model=settings.effective_vision_model,
        messages=[{"role": "user", "content": content}],
    )
    return (resp.choices[0].message.content or "").strip()


def ensure_image_desc(post: dict) -> str:
    cached = post.get("image_desc")
    if cached:
        return cached
    try:
        images = json.loads(post.get("images") or "[]")
    except (ValueError, TypeError):
        images = []
    if not images:
        return ""
    try:
        desc = describe_images(images)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  帖子 {post.get('id')} 配图描述失败：{e}")
        return ""
    if desc:
        db.save_image_desc(post["id"], desc)
        post["image_desc"] = desc
    return desc


def _format_posts(posts: list[dict]) -> str:
    blocks = []
    for p in posts:
        head = (
            f"【{p['date']} 互动:赞{p['like_count']}/转{p['retweet_count']}"
            f"/评{p['reply_count']}/收{p['fav_count']}】"
        )
        parts = [head]
        if p.get("title"):
            parts.append(f"标题：{p['title']}")
        parts.append(p["text"] or "（无正文）")
        img_desc = ensure_image_desc(p)
        if img_desc:
            parts.append(f"【配图内容】{img_desc}")
        blocks.append("\n".join(parts))
    return "\n\n----------\n\n".join(blocks)


def _images_appendix(posts: list[dict]) -> str:
    sections = []
    for p in posts:
        try:
            images = json.loads(p.get("images") or "[]")
        except (ValueError, TypeError):
            images = []
        if not images:
            continue
        head = f"[{p.get('date', '')} 原帖]({p.get('url', '')})"
        pics = "\n".join(f"![配图]({url})" for url in images)
        sections.append(f"{head}\n\n{pics}")
    if not sections:
        return ""
    return "\n\n### 配图\n\n" + "\n\n".join(sections) + "\n"


_STOCK_TABLE = (
    "### 提到的标的\n"
    "| 名称 | 代码 | 方向(看多/看空/中性/观察) | 作者理由 |\n"
    "|---|---|---|---|\n"
    "（按帖子内容填写；如未提到任何标的，写一行：无）\n"
)


def summarize_daily(user_name: str, date_str: str, posts: list[dict]) -> str:
    body = _format_posts(posts)
    prompt = f"""以下是【{user_name}】在 {date_str} 发布的全部帖子（共 {len(posts)} 条），请做"当日总结"。

严格按以下 Markdown 结构输出：

## {date_str} {user_name} 日总结
### 核心观点
（要点列表，3-6 条）
{_STOCK_TABLE}### 操作 / 仓位线索
（作者是否提到买入/卖出/加仓/减仓/空仓等；没有就写"未提及"）
### 风险与分歧
（作者自己提到的风险，或值得注意的不确定点）
### 一句话总结

帖子原文如下：

{body}
"""
    return call_llm(prompt) + _images_appendix(posts)


def reduce_period(user_name, period_label, period_key, parts, sub_unit) -> str:
    joined = "\n\n========== {sep} ==========\n\n".format(sep="").join(
        f"### 〔{label}〕\n{content}" for label, content in parts
    )
    prompt = f"""下面是【{user_name}】在 {period_key} 期间，按{sub_unit}拆分的多份总结。
请综合成一份"{period_label}"，关注趋势与变化，不要简单堆叠。

严格按以下 Markdown 结构输出：

## {period_key} {user_name} {period_label}
### 本期主线 / 观点演变
（作者关注的核心主题，以及观点在本期内是否发生变化）
{_STOCK_TABLE}### 持续看好 / 转向 / 新增 / 移除的标的
（对比本期内不同时间点，标的态度的变化）
### 操作 / 仓位变化
### 风险与分歧
### 本期一句话总结

各{sub_unit}总结如下：

{joined}
"""
    return call_llm(prompt)


def summarize_highlights(user_name: str, period_label: str, posts: list[dict]) -> str:
    body = _format_posts(posts)
    prompt = f"""下面是【{user_name}】在 {period_label} 互动量最高的 {len(posts)} 条帖子。
请提炼这些"精华帖"的看点。

严格按以下 Markdown 结构输出：

## {user_name} 精华帖（{period_label}）
### 为什么这些帖子受关注
（逐条简述看点，标注互动量）
{_STOCK_TABLE}### 反复强调的核心逻辑
### 一句话总结

帖子原文如下：

{body}
"""
    return call_llm(prompt) + _images_appendix(posts)
