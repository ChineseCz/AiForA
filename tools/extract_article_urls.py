#!/usr/bin/env python3
"""Extract and optionally paginate WeChat article URLs from API responses."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def article_urls(value: Any) -> list[dict[str, Any]]:
    """Collect article records while preserving first-seen order."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(node: Any, context: dict[str, Any] | None = None) -> None:
        if isinstance(node, dict):
            url = node.get("ContentUrl")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                if url not in seen:
                    seen.add(url)
                    data = dict(context or {})
                    data.update({
                        "title": node.get("Title", ""),
                        "url": url,
                        "digest": node.get("Digest", ""),
                        "item_index": node.get("ItemIndex", ""),
                        "is_original": node.get("IsOriginal", ""),
                        "read": node.get("Read", ""),
                        "zan": node.get("Zan", ""),
                        "sn": node.get("Sn", ""),
                        "send_time": node.get("send_time", data.get("send_time", "")),
                    })
                    found.append(data)
            next_context = dict(context or {})
            if isinstance(node.get("BaseInfo"), dict):
                base = node["BaseInfo"]
                next_context.update({
                    "msg_id": base.get("MsgId", next_context.get("msg_id", "")),
                    "app_msg_id": base.get("AppMsgId", next_context.get("app_msg_id", "")),
                    "create_time": base.get("CreateTime", next_context.get("create_time", "")),
                    "update_time": base.get("UpdateTime", next_context.get("update_time", "")),
                })
            if "send_time" in node:
                next_context["send_time"] = node["send_time"]
            for child in node.values():
                walk(child, next_context)
        elif isinstance(node, list):
            for child in node:
                walk(child, context)

    root_context: dict[str, Any] = {}
    if isinstance(value, dict) and isinstance(value.get("AccountInfo"), dict):
        account = value["AccountInfo"]
        root_context.update({
            "account_username": account.get("UserName", ""),
            "account_nickname": account.get("NickName", ""),
        })
    walk(value, root_context)
    return found


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def fetch(url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if isinstance(result, dict) and result.get("code") not in (None, 0, "0"):
        raise RuntimeError(f"API code={result.get('code')}: {result.get('msg', 'request failed')}")
    return result


def env_file_value(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def get_offset(response: Any) -> str:
    if not isinstance(response, dict):
        return ""
    paging = response.get("PagingInfo")
    if not isinstance(paging, dict):
        # Some responses nest the same object under MsgList.
        msg_list = response.get("MsgList")
        paging = msg_list.get("PagingInfo") if isinstance(msg_list, dict) else {}
    return str(paging.get("Offset", "")) if isinstance(paging, dict) else ""


def is_end(response: Any) -> bool:
    if not isinstance(response, dict):
        return True
    paging = response.get("PagingInfo")
    if not isinstance(paging, dict):
        msg_list = response.get("MsgList")
        paging = msg_list.get("PagingInfo") if isinstance(msg_list, dict) else {}
    value = paging.get("IsEnd") if isinstance(paging, dict) else 1
    return value in (1, True, "1", "true", "True")


def write_output(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            fields = [
                "account_username", "account_nickname", "title", "url", "digest",
                "msg_id", "app_msg_id", "item_index",
                "send_time", "create_time", "update_time", "is_original", "read", "zan", "sn",
            ]
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
    else:
        path.write_text("\n".join(record["url"] for record in records) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract WeChat article ContentUrl values.")
    parser.add_argument("inputs", nargs="*", type=Path, help="Saved API JSON files")
    parser.add_argument("-o", "--output", type=Path, default=Path("article_urls.txt"))
    parser.add_argument("--api-url", help="API URL; enables automatic pagination")
    parser.add_argument("--payload", type=Path, help="Initial POST JSON payload (optional)")
    parser.add_argument("--ghid", help="公众号原始 ID、微信号 alias/wxid 或公众号文章链接")
    parser.add_argument("--nickname", help="公众号名称")
    parser.add_argument("--verifycode", default="", help="接口附加码")
    parser.add_argument("--env-file", type=Path, default=Path("backend/.env"))
    parser.add_argument("--header", action="append", default=[], metavar="NAME=VALUE")
    args = parser.parse_args()

    records: list[dict[str, str]] = []
    known: set[str] = set()

    def add(response: Any) -> None:
        for record in article_urls(response):
            if record["url"] not in known:
                known.add(record["url"])
                records.append(record)

    for path in args.inputs:
        add(read_json(path))

    if args.api_url or args.ghid or args.nickname:
        api_url = args.api_url or "https://www.dajiala.com/fbmain/monitor/v3/history_by_ghid"
        if args.payload:
            payload = read_json(args.payload)
            if not isinstance(payload, dict):
                parser.error("--payload must contain a JSON object")
        else:
            payload = {
                "ghid": args.ghid or "",
                "url": "",
                "nickname": args.nickname or "",
                "offset": "",
                "key": env_file_value(args.env_file, "CRAW_API_KEY") or os.getenv("CRAW_API_KEY", ""),
                "verifycode": args.verifycode,
            }
        if not payload.get("key"):
            parser.error("CRAW_API_KEY not found in --env-file or environment")
        headers = {}
        for item in args.header:
            if "=" not in item:
                parser.error(f"Invalid --header: {item}")
            name, value = item.split("=", 1)
            headers[name] = value
        payload["offset"] = ""
        page = 0
        while True:
            page += 1
            response = fetch(api_url, payload, headers)
            add(response)
            if records:
                write_output(records, args.output)
            print(f"page {page}: total {len(records)}", file=sys.stderr)
            if is_end(response):
                break
            offset = get_offset(response)
            if not offset:
                break
            if offset == payload.get("offset"):
                print("paging stopped: API returned a repeated offset", file=sys.stderr)
                break
            payload["offset"] = offset

    if not records:
        parser.error("No ContentUrl found")
    write_output(records, args.output)
    print(f"saved {len(records)} URLs to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
