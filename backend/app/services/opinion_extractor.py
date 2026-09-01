"""Extract factual, evidence-backed investment claims from article text."""
import json
import re

from app.services import summarizer


SYSTEM_PROMPT = """
你是严谨的财经文本结构化助手。只从文章原文提取作者明确表达的观点，不推测、不补充。
返回严格 JSON 数组，不要 Markdown，不要解释。每项字段：
code（明确出现的六位股票代码，否则空字符串）、name（股票名称或原文简称）、
direction（只能是看多、看空、中性、观察）、claim（不超过80字的观点）、
evidence（原文中支持该观点的短句，不超过120字）、confidence（0到1之间数字）。
只提取具体股票或明确证券标的；指数、板块、泛泛而谈的市场观点不要作为股票记录。
没有明确股票观点时返回 []。
""".strip()


def _parse_json(raw: str) -> list[dict]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    value = json.loads(cleaned)
    if not isinstance(value, list):
        raise ValueError("AI 返回的观点不是数组")
    allowed = {"看多", "看空", "中性", "观察"}
    result = []
    for item in value:
        if not isinstance(item, dict) or not (item.get("name") or item.get("code")):
            continue
        direction = item.get("direction") if item.get("direction") in allowed else "观察"
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        result.append({
            "code": str(item.get("code") or "")[:20], "name": str(item.get("name") or "")[:100],
            "direction": direction, "claim": str(item.get("claim") or "")[:500],
            "evidence": str(item.get("evidence") or "")[:500], "confidence": confidence,
        })
    return result[:50]


def extract(title: str, content: str) -> tuple[list[dict], str]:
    prompt = f"文章标题：{title}\n\n文章正文：\n{content[:16000]}"
    raw = summarizer.call_llm(prompt, system_prompt=SYSTEM_PROMPT)
    return _parse_json(raw), raw
