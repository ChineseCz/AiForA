"""Markdown 渲染：与旧 web.py _render_md 完全一致的扩展集，保证输出逐字节相同。"""
import re

import markdown as md
from bs4 import BeautifulSoup, NavigableString

_STOCK_TABLE_HEADING = "提到的标的"


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _extract_mentioned_names(text: str) -> set[str]:
    """从"提到的标的"表格里取出全部"名称"列的值（不筛方向），供正文里给标的名称标蓝用。

    解析逻辑与 services/matching.py::parse_bullish_names 相同的表格定位方式，
    但那个函数只保留方向=看多的名称，这里要的是全部提到的标的，用途不同不复用。
    """
    if not text or _STOCK_TABLE_HEADING not in text:
        return set()
    lines = text.splitlines()
    names: set[str] = set()
    i, n = 0, len(lines)
    while i < n:
        if _STOCK_TABLE_HEADING not in lines[i]:
            i += 1
            continue
        i += 1
        while i < n and not lines[i].strip().startswith("|"):
            if lines[i].strip().startswith("#"):
                break
            i += 1
        if i >= n or not lines[i].strip().startswith("|"):
            continue
        header = _split_row(lines[i])
        i += 1
        if i < n and set(lines[i].strip()) <= set("-:| "):
            i += 1
        name_idx = header.index("名称") if "名称" in header else -1
        while i < n and lines[i].strip().startswith("|"):
            cells = _split_row(lines[i])
            if name_idx >= 0 and len(cells) > name_idx:
                nm = cells[name_idx].strip()
                if nm and nm not in ("无", "-"):
                    names.add(nm)
            i += 1
    return names


_SKIP_ANCESTOR_TAGS = {"table", "code", "pre", "a"}


def _colorize_ticker_names(html: str, names: set[str]) -> str:
    """把正文（表格之外）里出现的标的名称包一层 span.ticker-name，供前端标蓝。

    按名称长度从长到短匹配，避免短名称是长名称子串时抢先命中（如"茅台"是"贵州茅台"的子串）。
    """
    if not names:
        return html
    ordered = sorted(names, key=len, reverse=True)
    pattern = re.compile("(" + "|".join(re.escape(n) for n in ordered) + ")")
    soup = BeautifulSoup(html, "html.parser")
    for node in list(soup.find_all(string=True)):
        if not isinstance(node, NavigableString):
            continue
        if any(p.name in _SKIP_ANCESTOR_TAGS for p in node.parents):
            continue
        parts = pattern.split(str(node))
        if len(parts) == 1:
            continue
        new_nodes: list = []
        for idx, part in enumerate(parts):
            if not part:
                continue
            if idx % 2 == 1:
                span = soup.new_tag("span")
                span["class"] = "ticker-name"
                span.string = part
                new_nodes.append(span)
            else:
                new_nodes.append(part)
        node.replace_with(*new_nodes)
    return str(soup)


def render_md(text: str) -> str:
    html = md.markdown(text or "", extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
    return _colorize_ticker_names(html, _extract_mentioned_names(text or ""))
