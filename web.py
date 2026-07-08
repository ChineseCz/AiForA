"""本地 Web 看板：把抓到的帖子和 AI 总结用网页展示。

启动：
    python main.py serve
然后浏览器打开 http://127.0.0.1:5000

只监听本地回环地址（127.0.0.1），数据不出本机；没有账号鉴权，仅供本机个人查看。
"""
import json
import os
import sys
import threading
import time as _time
from datetime import date, datetime, timedelta

import markdown as md
from flask import Flask, jsonify, render_template, request

import config
import db

app = Flask(__name__, template_folder="templates", static_folder="static")

PERIOD_TYPES = ("daily", "weekly", "monthly", "yearly", "highlights")

# ===== 采集任务：在后台线程里跑，网页轮询进度 =====
_crawl_lock = threading.Lock()
crawl_state = {
    "running": False,
    "log": [],          # 实时输出的行
    "error": "",
    "source": "",       # 手动 / 定时
    "started_at": "",
    "finished_at": "",
}

SCHEDULE_PATH = os.path.join(config.DATA_DIR, "schedule.json")
DEFAULT_SCHEDULE = {"enabled": False, "start": "08:00", "interval": 30, "end": "22:00"}


class _TeeWriter:
    """把子任务的 print 同时写到原终端和内存日志（供网页轮询）。"""

    def __init__(self, orig, sink: list):
        self.orig = orig
        self.sink = sink

    def write(self, s):
        try:
            self.orig.write(s)
        except Exception:
            pass
        for line in s.splitlines():
            if line.strip():
                self.sink.append(line)
        if len(self.sink) > 300:
            del self.sink[: len(self.sink) - 300]
        return len(s)

    def flush(self):
        try:
            self.orig.flush()
        except Exception:
            pass


def _load_schedule() -> dict:
    try:
        with open(SCHEDULE_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    out = dict(DEFAULT_SCHEDULE)
    out["enabled"] = bool(cfg.get("enabled", False))
    # 兼容旧字段：老版本只有单个 time
    out["start"] = str(cfg.get("start", cfg.get("time", "08:00")))
    out["end"] = str(cfg.get("end", "22:00"))
    try:
        out["interval"] = max(5, int(cfg.get("interval", 30)))
    except (ValueError, TypeError):
        out["interval"] = 30
    return out


def _save_schedule(cfg: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(SCHEDULE_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)


def _parse_hhmm(s: str, default: tuple[int, int]) -> tuple[int, int]:
    try:
        h, m = s.split(":")
        return int(h), int(m)
    except Exception:
        return default


def _run_crawl(summarize: bool):
    import scraper  # 延迟导入，避免无谓加载 playwright

    old = sys.stdout
    sys.stdout = _TeeWriter(old, crawl_state["log"])
    try:
        scraper.crawl_all()
        if summarize:
            import main
            today = date.today()
            print("… 生成今日总结 …")
            for uid, uname in db.get_distinct_users():
                content = main.ensure_daily(uid, uname, today)
                if content:
                    main.write_report("daily", today.isoformat(), uname, content)
            print("✅ 今日总结已生成")
        print("🎉 采集完成")
    except Exception as e:  # noqa: BLE001
        crawl_state["error"] = str(e)
        print(f"❌ 采集出错：{e}")
    finally:
        sys.stdout = old
        crawl_state["running"] = False
        crawl_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_crawl(summarize: bool = True, source: str = "手动") -> bool:
    with _crawl_lock:
        if crawl_state["running"]:
            return False
        crawl_state.update(
            running=True, error="", log=[], source=source,
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at="",
        )
    threading.Thread(target=_run_crawl, args=(summarize,), daemon=True).start()
    return True


# ===== AI 总结任务：同样在后台线程里跑 =====
_summ_lock = threading.Lock()
summ_state = {"running": False, "log": [], "error": "", "started_at": "", "finished_at": ""}


def _name_of(user_id: str) -> str:
    for uid, name in db.get_distinct_users():
        if uid == user_id:
            return name
    return user_id


def _gen_highlights_range(uid: str, uname: str, start: date, end: date):
    import summarizer
    import main
    posts = db.get_top_posts(uid, start.isoformat(), end.isoformat(), 12)
    if not posts:
        print(f"  （{uname} 区间无帖子，跳过）")
        return
    label = f"{start.isoformat()} ~ {end.isoformat()}"
    content = summarizer.summarize_highlights(uname, label, posts)
    key = f"{start.isoformat()}_{end.isoformat()}"
    db.save_summary(uid, "highlights", key, content)
    main.write_report("highlights", key, uname, content)
    print(f"  ✅ 精华 {key}")


def _period_anchors(ptype: str, start: date, end: date) -> list[date]:
    """把 [start, end] 拆成该维度下需要生成的各个周期锚点日期。"""
    anchors: list[date] = []
    if ptype == "daily":
        d = start
        while d <= end:
            anchors.append(d)
            d += timedelta(days=1)
    elif ptype == "weekly":
        d = start - timedelta(days=start.weekday())  # 所在周的周一
        while d <= end:
            anchors.append(d)
            d += timedelta(days=7)
    elif ptype == "monthly":
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            anchors.append(date(y, m, 1))
            m += 1
            if m > 12:
                m = 1
                y += 1
    elif ptype == "yearly":
        for y in range(start.year, end.year + 1):
            anchors.append(date(y, 1, 1))
    return anchors


def _run_summarize(ptype: str, start_str: str, end_str: str, user_id: str, regen: bool):
    import main

    old = sys.stdout
    sys.stdout = _TeeWriter(old, summ_state["log"])
    try:
        today = date.today()
        start = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        end = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else start
        if end < start:
            start, end = end, start

        targets = [(user_id, _name_of(user_id))] if user_id else db.get_distinct_users()
        if not targets:
            print("⚠️ 库里还没有帖子，先采集。")
        for uid, uname in targets:
            if ptype == "highlights":
                _gen_highlights_range(uid, uname, start, end)
                continue
            builder, keyfn = main.BUILDERS[ptype]
            anchors = _period_anchors(ptype, start, end)
            print(f"→ {uname} · {ptype} 共 {len(anchors)} 个周期")
            done = 0
            for a in anchors:
                content = builder(uid, uname, a, regen)
                if content:
                    main.write_report(ptype, keyfn(a), uname, content)
                    done += 1
                    print(f"  ✅ {keyfn(a)}")
            print(f"  {uname}：生成 {done} 份")
        print("🎉 总结完成")
    except Exception as e:  # noqa: BLE001
        summ_state["error"] = str(e)
        print(f"❌ 总结出错：{e}")
    finally:
        sys.stdout = old
        summ_state["running"] = False
        summ_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_summarize(ptype: str, start_str: str, end_str: str, user_id: str, regen: bool) -> bool:
    with _summ_lock:
        if summ_state["running"]:
            return False
        summ_state.update(
            running=True, error="", log=[],
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at="",
        )
    threading.Thread(
        target=_run_summarize, args=(ptype, start_str, end_str, user_id, regen), daemon=True
    ).start()
    return True


# ===== 选股行情同步：同样用后台线程 + 轮询 =====
_stock_sync_lock = threading.Lock()
stock_sync_state = {"running": False, "log": [], "error": "", "started_at": "", "finished_at": ""}

STOCK_FIELD_META = [
    {"field": "change_pct", "label": "涨跌幅(%)"},
    {"field": "close", "label": "最新价"},
    {"field": "volume", "label": "成交量"},
    {"field": "amount", "label": "成交额"},
    {"field": "turnover_rate", "label": "换手率(%)"},
    {"field": "pe_ttm", "label": "市盈率(动态)"},
    {"field": "pb", "label": "市净率"},
    {"field": "total_mv", "label": "总市值(万元)"},
    {"field": "circ_mv", "label": "流通市值(万元)"},
]


def _run_stock_sync():
    import stock  # 延迟导入

    old = sys.stdout
    sys.stdout = _TeeWriter(old, stock_sync_state["log"])
    try:
        stock.sync_daily_snapshot()
    except Exception as e:  # noqa: BLE001
        stock_sync_state["error"] = str(e)
        print(f"❌ 同步出错：{e}")
    finally:
        sys.stdout = old
        stock_sync_state["running"] = False
        stock_sync_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_stock_sync() -> bool:
    with _stock_sync_lock:
        if stock_sync_state["running"]:
            return False
        stock_sync_state.update(
            running=True, error="", log=[],
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at="",
        )
    threading.Thread(target=_run_stock_sync, daemon=True).start()
    return True


# ===== 历史K线批量回补：同样用后台线程 + 轮询（独立状态，不复用 stock_sync_state）=====
_stock_backfill_lock = threading.Lock()
stock_backfill_state = {"running": False, "log": [], "error": "", "started_at": "", "finished_at": ""}


def _run_stock_backfill(days: int):
    import stock  # 延迟导入

    old = sys.stdout
    sys.stdout = _TeeWriter(old, stock_backfill_state["log"])
    try:
        stock.backfill_history(days)
    except Exception as e:  # noqa: BLE001
        stock_backfill_state["error"] = str(e)
        print(f"❌ 回补出错：{e}")
    finally:
        sys.stdout = old
        stock_backfill_state["running"] = False
        stock_backfill_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_stock_backfill(days: int = 60) -> bool:
    with _stock_backfill_lock:
        if stock_backfill_state["running"]:
            return False
        stock_backfill_state.update(
            running=True, error="", log=[],
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at="",
        )
    threading.Thread(target=_run_stock_backfill, args=(days,), daemon=True).start()
    return True


# ===== 财务指标同步：同样用后台线程 + 轮询 =====
_stock_finance_lock = threading.Lock()
stock_finance_state = {"running": False, "log": [], "error": "", "started_at": "", "finished_at": ""}


def _run_stock_finance_sync():
    import stock  # 延迟导入

    old = sys.stdout
    sys.stdout = _TeeWriter(old, stock_finance_state["log"])
    try:
        stock.sync_finance_snapshot()
    except Exception as e:  # noqa: BLE001
        stock_finance_state["error"] = str(e)
        print(f"❌ 同步出错：{e}")
    finally:
        sys.stdout = old
        stock_finance_state["running"] = False
        stock_finance_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_stock_finance_sync() -> bool:
    with _stock_finance_lock:
        if stock_finance_state["running"]:
            return False
        stock_finance_state.update(
            running=True, error="", log=[],
        )
    threading.Thread(target=_run_stock_finance_sync, daemon=True).start()
    return True


# ===== 板块名单同步：同样用后台线程 + 轮询 =====
_sector_sync_lock = threading.Lock()
sector_sync_state = {"running": False, "log": [], "error": "", "started_at": "", "finished_at": ""}


def _run_sector_sync():
    import stock  # 延迟导入

    old = sys.stdout
    sys.stdout = _TeeWriter(old, sector_sync_state["log"])
    try:
        stock.sync_sector_catalog()
    except Exception as e:  # noqa: BLE001
        sector_sync_state["error"] = str(e)
        print(f"❌ 同步出错：{e}")
    finally:
        sys.stdout = old
        sector_sync_state["running"] = False
        sector_sync_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_sector_sync() -> bool:
    with _sector_sync_lock:
        if sector_sync_state["running"]:
            return False
        sector_sync_state.update(
            running=True, error="", log=[],
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at="",
        )
    threading.Thread(target=_run_sector_sync, daemon=True).start()
    return True


# ===== 板块成分股全量同步：同样用后台线程 + 轮询 =====
_sector_members_sync_lock = threading.Lock()
sector_members_sync_state = {"running": False, "log": [], "error": "", "started_at": "", "finished_at": ""}


def _run_sector_members_sync():
    import stock  # 延迟导入

    old = sys.stdout
    sys.stdout = _TeeWriter(old, sector_members_sync_state["log"])
    try:
        stock.sync_all_sector_members()
    except Exception as e:  # noqa: BLE001
        sector_members_sync_state["error"] = str(e)
        print(f"❌ 同步出错：{e}")
    finally:
        sys.stdout = old
        sector_members_sync_state["running"] = False
        sector_members_sync_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_sector_members_sync() -> bool:
    with _sector_members_sync_lock:
        if sector_members_sync_state["running"]:
            return False
        sector_members_sync_state.update(
            running=True, error="", log=[],
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at="",
        )
    threading.Thread(target=_run_sector_members_sync, daemon=True).start()
    return True


def _scheduler_loop():
    """服务运行期间的内置定时器：在 [start, end] 窗口内，每隔 interval 分钟触发一次采集。"""
    last_fired = None  # (日期, 槽位序号)，保证同一时间槽只触发一次
    while True:
        try:
            cfg = _load_schedule()
            if cfg["enabled"]:
                now = datetime.now()
                sh, sm = _parse_hhmm(cfg["start"], (8, 0))
                eh, em = _parse_hhmm(cfg["end"], (22, 0))
                interval = max(5, int(cfg["interval"]))
                start_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
                end_dt = now.replace(hour=eh, minute=em, second=0, microsecond=0)
                if end_dt <= start_dt:  # 结束早于开始则按当天最晚处理
                    end_dt = now.replace(hour=23, minute=59, second=0, microsecond=0)

                if start_dt <= now <= end_dt:
                    slot = int((now - start_dt).total_seconds() // 60 // interval)
                    slot_time = start_dt + timedelta(minutes=slot * interval)
                    # 落在某个时间槽起点后的 60 秒内、且该槽还没触发过 → 跑
                    if (now - slot_time).total_seconds() < 60 and last_fired != (now.date(), slot):
                        last_fired = (now.date(), slot)
                        start_crawl(summarize=True, source="定时")
        except Exception:
            pass
        _time.sleep(20)


def _render_md(text: str) -> str:
    return md.markdown(text or "", extensions=["tables", "fenced_code", "nl2br", "sane_lists"])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/users")
def api_users():
    users = [{"id": uid, "name": name} for uid, name in db.get_distinct_users()]
    return jsonify(users)


@app.route("/api/overview")
def api_overview():
    user_id = request.args.get("user") or None
    stats = db.get_stats()
    monthly = db.get_monthly_counts(user_id)
    daily = db.get_daily_counts(user_id)
    latest = db.get_posts(user_id, limit=8, offset=0)["items"]

    total = sum(m["n"] for m in monthly) if user_id else stats["total"]
    span_first = daily[0]["date"] if daily else "-"
    span_last = daily[-1]["date"] if daily else "-"

    return jsonify(
        {
            "total": total,
            "user_count": len(stats["per_user"]),
            "first": span_first,
            "last": span_last,
            "active_days": len(daily),
            "monthly": monthly,
            "daily": daily,
            "latest": latest,
        }
    )


@app.route("/api/posts")
def api_posts():
    user_id = request.args.get("user") or None
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    q = request.args.get("q", "")
    page = max(1, int(request.args.get("page", 1)))
    size = min(100, max(5, int(request.args.get("size", 30))))
    data = db.get_posts(user_id, start, end, q, limit=size, offset=(page - 1) * size)
    data["page"] = page
    data["size"] = size
    return jsonify(data)


@app.route("/api/summary_keys")
def api_summary_keys():
    user_id = request.args.get("user") or ""
    ptype = request.args.get("type", "daily")
    if not user_id or ptype not in PERIOD_TYPES:
        return jsonify([])
    return jsonify(db.get_summary_keys(user_id, ptype))


@app.route("/api/summary")
def api_summary():
    user_id = request.args.get("user") or ""
    ptype = request.args.get("type", "daily")
    key = request.args.get("key", "")
    content = db.get_summary(user_id, ptype, key)
    if content is None:
        return jsonify({"found": False, "html": ""})
    return jsonify({"found": True, "html": _render_md(content), "raw": content})


@app.route("/api/summary/ask", methods=["POST"])
def api_summary_ask():
    import summarizer

    body = request.get_json(silent=True) or {}
    user_id = str(body.get("user") or "")
    ptype = body.get("type", "daily")
    key = str(body.get("key") or "")
    question = str(body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "请输入问题"}), 400
    content = db.get_summary(user_id, ptype, key)
    if content is None:
        return jsonify({"error": "请先选择一份已生成的总结"}), 400
    try:
        answer = summarizer.ask_about_summary(content, question)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return jsonify({"answer": answer, "html": _render_md(answer)})


@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    body = request.get_json(silent=True) or {}
    summarize = bool(body.get("summarize", True))
    ok = start_crawl(summarize=summarize, source="手动")
    return jsonify({"started": ok, "running": crawl_state["running"]})


@app.route("/api/crawl/status")
def api_crawl_status():
    return jsonify(crawl_state)


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    body = request.get_json(silent=True) or {}
    ptype = body.get("type", "daily")
    if ptype not in PERIOD_TYPES:
        return jsonify({"started": False, "error": "未知的总结类型"})
    ok = start_summarize(
        ptype,
        str(body.get("start", "")),
        str(body.get("end", "")),
        str(body.get("user", "")),
        bool(body.get("regen", False)),
    )
    return jsonify({"started": ok, "running": summ_state["running"]})


@app.route("/api/summarize/status")
def api_summarize_status():
    return jsonify(summ_state)


@app.route("/api/schedule", methods=["GET", "POST"])
def api_schedule():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        try:
            interval = max(5, int(body.get("interval", 30) or 30))
        except (ValueError, TypeError):
            interval = 30
        cfg = {
            "enabled": bool(body.get("enabled", False)),
            "start": str(body.get("start", "08:00")),
            "end": str(body.get("end", "22:00")),
            "interval": interval,
        }
        _save_schedule(cfg)
        return jsonify(cfg)
    return jsonify(_load_schedule())


@app.route("/api/stock/sync", methods=["POST"])
def api_stock_sync():
    ok = start_stock_sync()
    return jsonify({"started": ok, "running": stock_sync_state["running"]})


@app.route("/api/stock/sync/status")
def api_stock_sync_status():
    return jsonify(stock_sync_state)


@app.route("/api/stock/backfill", methods=["POST"])
def api_stock_backfill():
    body = request.get_json(silent=True) or {}
    try:
        days = max(20, min(120, int(body.get("days", 60) or 60)))
    except (TypeError, ValueError):
        days = 60
    ok = start_stock_backfill(days)
    return jsonify({"started": ok, "running": stock_backfill_state["running"]})


@app.route("/api/stock/backfill/status")
def api_stock_backfill_status():
    return jsonify(stock_backfill_state)


@app.route("/api/stock/finance_sync", methods=["POST"])
def api_stock_finance_sync():
    ok = start_stock_finance_sync()
    return jsonify({"started": ok, "running": stock_finance_state["running"]})


@app.route("/api/stock/finance_sync/status")
def api_stock_finance_sync_status():
    return jsonify(stock_finance_state)


@app.route("/api/stock/sync-sectors", methods=["POST"])
def api_sync_sectors():
    ok = start_sector_sync()
    return jsonify({"started": ok, "running": sector_sync_state["running"]})


@app.route("/api/stock/sync-sectors/status")
def api_sync_sectors_status():
    return jsonify(sector_sync_state)


@app.route("/api/stock/sync-sector-members", methods=["POST"])
def api_sync_sector_members():
    ok = start_sector_members_sync()
    return jsonify({"started": ok, "running": sector_members_sync_state["running"]})


@app.route("/api/stock/sync-sector-members/status")
def api_sync_sector_members_status():
    return jsonify(sector_members_sync_state)


@app.route("/api/screen/sectors")
def api_screen_sectors():
    import stock

    rows = db.get_sector_catalog()
    for r in rows:
        r["abbr"] = stock.pinyin_abbr(r["name"])
    return jsonify(rows)


@app.route("/api/screen/fields")
def api_screen_fields():
    return jsonify(STOCK_FIELD_META)


@app.route("/api/screen", methods=["POST"])
def api_screen():
    import stock

    body = request.get_json(silent=True) or {}
    trade_date = db.get_latest_trade_date()
    if not trade_date:
        return jsonify({"error": "还没有行情数据，请先同步。", "items": [], "trade_date": None}), 400

    conditions = body.get("conditions") or []
    strategies = [s for s in (body.get("strategies") or []) if s]
    name_query = str(body.get("name_query") or "").strip()

    try:
        limit = min(500, max(1, int(body.get("limit", 200) or 200)))
    except (TypeError, ValueError):
        limit = 200

    try:
        if strategies:
            rows = stock.screen_combined_all(strategies, conditions, limit)
        elif conditions:
            where_sql, params = stock.build_where(conditions)
            rows = db.screen_stocks(trade_date, where_sql, params, limit)
        elif name_query:
            rows = db.get_latest_rows()
        else:
            return jsonify({"error": "请至少选择一个预设策略、填写筛选条件，或输入股票名称/代码搜索。", "items": [], "trade_date": trade_date}), 400
    except (ValueError, stock.InsufficientHistoryError, stock.InsufficientFinanceError) as e:
        return jsonify({"error": str(e), "items": [], "trade_date": trade_date}), 400

    if name_query:
        rows = stock.match_name_query(rows, name_query)[:limit]

    mentioned = body.get("mentioned") or {}
    if mentioned.get("enabled"):
        try:
            days = max(1, int(mentioned.get("days", 7) or 7))
        except (TypeError, ValueError):
            days = 7
        user_id = str(mentioned.get("user_id") or "")
        rows = stock.match_mentions(rows, days, user_id)

    sector = body.get("sector") or {}
    if sector.get("enabled"):
        names = [n for n in (sector.get("names") or []) if n]
        if sector.get("mode") == "bullish":
            try:
                days = max(1, int(sector.get("days", 7) or 7))
            except (TypeError, ValueError):
                days = 7
            user_id = str(sector.get("user_id") or "")
            names = stock.derive_bullish_sectors(days, user_id)
        rows = stock.match_sector(rows, names) if names else []

    return jsonify({"trade_date": trade_date, "items": rows, "error": ""})


@app.route("/api/screen/preset", methods=["POST"])
def api_screen_preset():
    import stock

    body = request.get_json(silent=True) or {}
    strategies = body.get("strategies")
    if not strategies:
        single = body.get("strategy")
        strategies = [single] if single else []

    trade_date = db.get_latest_trade_date()
    if not trade_date:
        return jsonify({"error": "还没有行情数据，请先同步。", "items": [], "trade_date": None}), 400

    try:
        limit = min(500, max(1, int(body.get("limit", 200) or 200)))
    except (TypeError, ValueError):
        limit = 200

    try:
        rows = stock.screen_combined(strategies, limit)
    except (stock.InsufficientHistoryError, stock.InsufficientFinanceError, ValueError) as e:
        return jsonify({"error": str(e), "items": [], "trade_date": trade_date}), 400

    return jsonify({"trade_date": trade_date, "items": rows, "error": ""})


@app.route("/stock/<code>")
def stock_detail(code):
    return render_template("kline.html", code=code)


@app.route("/api/stock/kline")
def api_stock_kline():
    import stock

    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"error": "缺少股票代码", "code": "", "name": "", "bars": []}), 400
    view = stock.get_kline_view(code)
    view["error"] = ""
    return jsonify(view)


@app.route("/api/stock/fundamentals")
def api_stock_fundamentals():
    import stock

    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"error": "缺少股票代码"}), 400
    try:
        days = max(1, min(365, int(request.args.get("days", 90) or 90)))
    except (TypeError, ValueError):
        days = 90
    view = stock.get_fundamentals_view(code, mention_days=days)
    view["error"] = ""
    return jsonify(view)


@app.route("/api/stock/news")
def api_stock_news():
    import stock

    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"error": "缺少股票代码", "items": []}), 400
    try:
        days = max(1, min(60, int(request.args.get("days", 14) or 14)))
    except (TypeError, ValueError):
        days = 14
    items = stock.fetch_stock_news(code, days=days)
    return jsonify({"items": items, "days": days, "error": ""})


@app.route("/api/groups", methods=["GET", "POST"])
def api_groups():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "分组名不能为空"}), 400
        group_id = db.create_group(name)
        if group_id is None:
            return jsonify({"error": "分组名已存在"}), 400
        return jsonify({"id": group_id, "name": name, "error": ""})
    return jsonify({"groups": db.list_groups(), "error": ""})


@app.route("/api/groups/<int:group_id>", methods=["DELETE"])
def api_group_delete(group_id):
    db.delete_group(group_id)
    return jsonify({"error": ""})


@app.route("/api/groups/<int:group_id>/members", methods=["GET", "POST"])
def api_group_members(group_id):
    import stock

    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        stocks = [
            {"code": s.get("code"), "name": s.get("name")}
            for s in (body.get("stocks") or [])
            if s.get("code")
        ]
        if not stocks:
            return jsonify({"error": "没有可添加的股票"}), 400
        n = db.add_group_members(group_id, stocks)
        return jsonify({"added": n, "error": ""})
    return jsonify({"items": stock.group_members_view(group_id), "error": ""})


@app.route("/api/groups/<int:group_id>/members/<code>", methods=["DELETE"])
def api_group_member_delete(group_id, code):
    db.remove_group_member(group_id, code)
    return jsonify({"error": ""})


def run(host: str = "127.0.0.1", port: int = 5000) -> None:
    db.init_db()
    threading.Thread(target=_scheduler_loop, daemon=True).start()
    print(f"看板已启动 → http://{host}:{port}   （Ctrl+C 停止）")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run()
