"""Markdown 渲染：与旧 web.py _render_md 完全一致的扩展集，保证输出逐字节相同。"""
import markdown as md


def render_md(text: str) -> str:
    return md.markdown(text or "", extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
