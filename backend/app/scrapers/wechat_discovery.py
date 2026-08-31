"""低频发现微信公众号文章候选链接。"""
import time
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://weixin.sogou.com/weixin"


def discover(keyword: str, pages: int = 1) -> list[dict]:
    """Search Sogou slowly and return candidates whose publisher matches keyword."""
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://weixin.sogou.com/"}
    results: list[dict] = []
    seen: set[str] = set()
    for page_no in range(1, max(1, min(pages, 3)) + 1):
        response = session.get(
            SEARCH_URL,
            params={"type": 2, "query": keyword, "page": page_no},
            headers=headers,
            timeout=30,
        )
        soup = BeautifulSoup(response.text, "html.parser")
        for item in soup.select("ul.news-list li"):
            publisher = item.select_one(".all-time-y2")
            title_node = item.select_one("h3 a")
            link_node = item.select_one("h3 a[href]")
            if not publisher or not title_node or not link_node:
                continue
            publisher_name = publisher.get_text(" ", strip=True)
            if keyword not in publisher_name:
                continue
            sogou_url = urljoin(SEARCH_URL, link_node["href"])
            if sogou_url in seen:
                continue
            seen.add(sogou_url)
            timestamp = item.select_one(".s2")
            result = {
                "title": title_node.get_text(" ", strip=True),
                "publisher": publisher_name,
                "date": timestamp.get_text(" ", strip=True) if timestamp else "",
                "sogou_url": sogou_url,
                "url": "",
            }
            try:
                resolved = session.get(sogou_url, headers=headers, timeout=20, allow_redirects=True)
                if "mp.weixin.qq.com/s/" in resolved.url:
                    result["url"] = resolved.url.split("?", 1)[0].split("#", 1)[0]
            except requests.RequestException:
                pass
            results.append(result)
        if page_no < pages:
            time.sleep(5)
    return results
