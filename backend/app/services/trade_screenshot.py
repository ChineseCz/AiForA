"""Extract visible trade rows from screenshots with the configured vision model."""
import base64
import json
import re

from openai import OpenAI

from app.core.config import settings


def _json_text(raw: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw or "", re.S)
    if not match:
        raise ValueError("视觉模型未返回结构化交易记录")
    value = json.loads(match.group(0))
    if not isinstance(value, list):
        raise ValueError("视觉模型返回格式不正确")
    return [item for item in value if isinstance(item, dict)]


def extract_trades(images: list[tuple[bytes, str]]) -> list[dict]:
    if not settings.effective_image_key:
        raise RuntimeError("未配置视觉模型 API Key")
    content: list[dict] = [{
        "type": "text",
        "text": (
            "请识别证券交易软件截图中完整可见的成交记录，只输出合法 JSON 数组，不要 Markdown。"
            "字段必须为 trade_date(YYYY-MM-DD或null), trade_time(HH:MM:SS), stock_name, "
            "direction(买入/卖出或buy/sell), price(数字), quantity(整数), amount(数字或null)。"
            "历史成交从截图日期读取；当日成交若截图没有日期必须返回 null。"
            "只识别完整可见的成交记录，不识别表头、委托记录或底部被截断的行，不要猜证券代码。"
        ),
    }]
    for data, mime in images:
        encoded = base64.b64encode(data).decode("ascii")
        content.append({"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"})
    client = OpenAI(api_key=settings.effective_image_key, base_url=settings.relay_api_url, timeout=120)
    # gpt-5.6-luna is Responses-only on the configured relay endpoint.
    response = client.responses.create(
        model=settings.effective_vision_model,
        input=[{"role": "user", "content": content}],
    )
    return _json_text(response.output_text or "")
