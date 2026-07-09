"""对拍验证：旧 Flask（SQLite）vs 新 FastAPI（Postgres），逐读接口 diff JSON。

用法：
    # 终端1：起旧 Flask（在项目根，用其自带 venv）
    python main.py serve --port 5000
    # 终端2：起新 FastAPI
    uvicorn app.main:app --port 8010
    # 终端3：
    python -m scripts.parity_check --old http://127.0.0.1:5000 --new http://127.0.0.1:8010

比较策略：浮点按相对误差容差；顺序无保证的列表（无 ORDER BY 的）退化为「集合/排序后」比较，
标注 order-differs 但不算失败。任何结构/取值不一致则 FAIL。
"""
import argparse
import json
import sys

import requests

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FLOAT_TOL = 1e-6


def norm(x):
    """递归归一化：float 四舍五入到容差量级，便于比较。"""
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return x


def _sort_key(d):
    if isinstance(d, dict):
        for k in ("id", "code", "ym", "date", "period_key", "field", "board_code", "name"):
            if k in d:
                return json.dumps({k: d[k]}, sort_keys=True, ensure_ascii=False)
        return json.dumps(d, sort_keys=True, ensure_ascii=False)
    return json.dumps(d, sort_keys=True, ensure_ascii=False)


def order_insensitive_equal(a, b) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return norm(sorted(a, key=_sort_key)) == norm(sorted(b, key=_sort_key))
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(order_insensitive_equal(a[k], b[k]) for k in a)
    return norm(a) == norm(b)


def fetch(base, method, path, body=None):
    url = base + path
    r = requests.request(method, url, json=body, timeout=60)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def compare(name, old, new) -> bool:
    os_, ob = old
    ns_, nb = new
    if os_ != ns_:
        print(f"  ❌ {name}: 状态码 old={os_} new={ns_}")
        return False
    if norm(ob) == norm(nb):
        print(f"  ✅ {name}")
        return True
    if order_insensitive_equal(ob, nb):
        print(f"  ✅ {name}  (顺序不同但内容一致)")
        return True
    print(f"  ❌ {name}: 内容不一致")
    _show_diff(ob, nb)
    return False


def _show_diff(ob, nb):
    so = json.dumps(norm(ob), sort_keys=True, ensure_ascii=False)[:600]
    sn = json.dumps(norm(nb), sort_keys=True, ensure_ascii=False)[:600]
    print(f"     old: {so}")
    print(f"     new: {sn}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default="http://127.0.0.1:5000")
    ap.add_argument("--new", default="http://127.0.0.1:8010")
    args = ap.parse_args()
    O, N = args.old, args.new

    # 自发现测试参数
    users = fetch(N, "GET", "/api/users")[1]
    uid = users[0]["id"] if users else ""
    keys = fetch(N, "GET", f"/api/summary_keys?user={uid}&type=daily")[1]
    skey = keys[0] if keys else ""
    # 取一只有历史的股票代码
    preset = fetch(N, "POST", "/api/screen/preset", {"strategies": ["ma_cross2"], "limit": 5})[1]
    code = ""
    if isinstance(preset, dict) and preset.get("items"):
        code = preset["items"][0].get("code", "")
    if not code:
        code = "600519"

    print(f"测试参数: uid={uid} summary_key={skey} code={code}\n")

    cases = [
        ("GET /api/users", "GET", "/api/users", None),
        ("GET /api/overview", "GET", "/api/overview", None),
        (f"GET /api/overview?user={uid}", "GET", f"/api/overview?user={uid}", None),
        ("GET /api/posts p1", "GET", "/api/posts?page=1&size=30", None),
        ("GET /api/posts p2", "GET", "/api/posts?page=2&size=30", None),
        ("GET /api/posts q", "GET", "/api/posts?q=半导体&page=1&size=20", None),
        (f"GET /api/summary_keys {uid}", "GET", f"/api/summary_keys?user={uid}&type=daily", None),
        (f"GET /api/summary {skey}", "GET", f"/api/summary?user={uid}&type=daily&key={skey}", None),
        ("GET /api/screen/fields", "GET", "/api/screen/fields", None),
        ("GET /api/screen/sectors", "GET", "/api/screen/sectors", None),
        ("POST /api/screen preset", "POST", "/api/screen", {"strategies": ["ma_cross2"], "limit": 50}),
        ("POST /api/screen cond", "POST", "/api/screen",
         {"conditions": [{"field": "change_pct", "op": ">", "value": 5}], "limit": 50}),
        ("POST /api/screen/preset", "POST", "/api/screen/preset", {"strategies": ["golden_cross"], "limit": 50}),
        (f"GET /api/stock/kline {code}", "GET", f"/api/stock/kline?code={code}", None),
        (f"GET /api/stock/fundamentals {code}", "GET", f"/api/stock/fundamentals?code={code}", None),
        ("GET /api/groups", "GET", "/api/groups", None),
    ]

    ok = True
    for name, method, path, body in cases:
        try:
            res = compare(name, fetch(O, method, path, body), fetch(N, method, path, body))
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ {name}: 异常 {e}")
            res = False
        ok = ok and res

    print("\n" + ("🎉 全部对拍通过" if ok else "❌ 存在不一致"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
