"""微信公众号文章解析。"""
import hashlib
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

WECHAT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.34(0x16082222) NetType/WIFI Language/zh_CN"
)


def _article_id(url: str) -> str:
    parsed = urlparse(url)
    # WeChat article URLs use /s?..., so the query identifies the article.
    canonical = f"https://mp.weixin.qq.com{parsed.path}?{parsed.query}"
    return "wechat:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _timestamp(value: str | None) -> int:
    try:
        return int(str(value or 0).strip())
    except (TypeError, ValueError):
        return 0


_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _article_timestamp(html: str, publish_node, publish_time: str) -> int:
    """Extract the original publication timestamp from the several WeChat formats."""
    # Older pages expose the timestamp directly on #publish_time.
    ts = _timestamp(publish_node.get("data-time") if publish_node else None)
    if ts:
        return ts

    # On current pages #publish_time is often empty and is filled by JS.  The
    # original values are still embedded in the page, e.g.:
    #   var oriCreateTime = '1787734620';
    #   var createTime = '2026-08-26 16:57';
    for pattern in (
        r"\boriCreateTime\s*=\s*['\"](\d{9,})['\"]",
        r"\bcreate_timestamp\s*[:=]\s*['\"]?(\d{9,})['\"]?",
    ):
        match = re.search(pattern, html)
        if match:
            ts = _timestamp(match.group(1))
            if ts:
                return ts

    # Keep a textual fallback for pages that provide createTime but no epoch.
    for value in (publish_time,):
        match = re.search(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})", value or "")
        if match:
            return int(datetime.strptime("-".join(match.groups()), "%Y-%m-%d").replace(tzinfo=_SHANGHAI).timestamp())

    match = re.search(r"\bcreateTime\s*=\s*['\"](20\d{2})-(\d{1,2})-(\d{1,2})(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?['\"]", html)
    if match:
        return int(datetime.strptime("-".join(match.groups()), "%Y-%m-%d").replace(tzinfo=_SHANGHAI).timestamp())
    return 0


def parse_article(url: str) -> dict:
    """Fetch one public article with the WeChat mobile-browser user agent."""
    parsed = urlparse(url)
    if parsed.netloc not in {"mp.weixin.qq.com", "mp.weixin.qq.com."} or not (
        parsed.path == "/s" or parsed.path.startswith("/s/")
    ):
        raise ValueError("请输入 mp.weixin.qq.com/s/... 格式的公众号文章链接")

    response = requests.get(
        url,
        headers={"User-Agent": WECHAT_UA, "Referer": "https://mp.weixin.qq.com/"},
        timeout=45,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    body_text = soup.get_text(" ", strip=True)
    if "环境异常" in body_text or "完成验证" in body_text or "wappoc_appmsgcaptcha" in response.url:
        raise RuntimeError("微信触发环境验证，请稍后降低频率再试")

    title_node = soup.select_one("#activity-name")
    content_node = soup.select_one("#js_content")
    if not title_node or not content_node:
        raise RuntimeError("未找到文章标题或正文，可能是文章已删除或页面结构变化")

    title = title_node.get_text(" ", strip=True)
    content = content_node.get_text("\n", strip=True)
    if not title or not content:
        raise RuntimeError("文章标题或正文为空")
    author = soup.select_one("#js_name")
    author_name = author.get_text(" ", strip=True) if author else "微信公众号"
    publish_node = soup.select_one("#publish_time")
    publish_time = publish_node.get_text(" ", strip=True) if publish_node else ""
    ts = _article_timestamp(response.text, publish_node, publish_time)
    if not ts:
        ts = int(time.time())
    images = [
        src for img in content_node.select("img")
        if (src := img.get("data-src") or img.get("src"))
    ]
    return {
        "id": _article_id(url),
        "user_id": "wechat:" + author_name,
        "user_name": author_name,
        "created_at": ts * 1000,
        "date": datetime.fromtimestamp(ts, _SHANGHAI).strftime("%Y-%m-%d"),
        "text": content,
        "title": title,
        "url": url,
        "like_count": 0,
        "retweet_count": 0,
        "reply_count": 0,
        "fav_count": 0,
        "raw_json": json.dumps({"source": "wechat", "publish_time": publish_time}, ensure_ascii=False),
        "images": json.dumps(images, ensure_ascii=False),
        "fetched_at": int(time.time() * 1000),
    }
