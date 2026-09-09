"""国家队持仓同步与查询业务。"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.external.eastmoney import fetch_national_team_holdings


def _team_name(institution: str) -> str:
    if "汇金" in institution:
        return "汇金系"
    if "证金" in institution or "中证金融" in institution:
        return "证金系"
    if "社保" in institution:
        return "社保系"
    if "养老金" in institution:
        return "养老金系"
    if "外汇" in institution or "外管" in institution:
        return "外管局系"
    if "大基金" in institution:
        return "国家大基金系"
    return "其他"


def infer_exit_rows(rows: list[dict]) -> list[dict]:
    """Add report-period rows for holdings that leave the disclosed range."""
    grouped: dict[str, dict[str, dict[str, dict]]] = {}
    for row in rows:
        grouped.setdefault(row["institution"], {}).setdefault(row["report_date"], {})[row["code"]] = row

    for institution, periods in grouped.items():
        dates = sorted(periods)
        for previous, current in zip(dates, dates[1:]):
            for code, old in periods[previous].items():
                if code not in periods[current]:
                    periods[current][code] = {
                        "report_date": current,
                        "institution": institution,
                        "code": code,
                        "name": old.get("name"),
                        "shares": 0,
                        "holding_ratio": 0,
                        "change_shares": -old.get("shares") if old.get("shares") is not None else None,
                        "change_type": "退出披露范围",
                        "market_value": None,
                        "source": "eastmoney",
                    }
    return [
        row
        for periods in grouped.values()
        for rows_by_code in periods.values()
        for row in rows_by_code.values()
    ]


def sync_national_team_holdings() -> int:
    """同步公开披露记录，并补充相邻报告期中消失的“退出”记录。"""
    from app.core.sync_db import sync_session

    rows = fetch_national_team_holdings()
    all_rows = infer_exit_rows(rows)
    now = int(time.time())
    with sync_session() as session:
        for row in all_rows:
            session.execute(text("""
                INSERT INTO national_team_holdings
                    (report_date, institution, code, name, shares, holding_ratio,
                     change_shares, change_type, market_value, source, updated_at)
                VALUES (:report_date, :institution, :code, :name, :shares, :holding_ratio,
                        :change_shares, :change_type, :market_value, :source, :updated_at)
                ON CONFLICT (report_date, institution, code) DO UPDATE SET
                    name=EXCLUDED.name, shares=EXCLUDED.shares, holding_ratio=EXCLUDED.holding_ratio,
                    change_shares=EXCLUDED.change_shares, change_type=EXCLUDED.change_type,
                    market_value=EXCLUDED.market_value, source=EXCLUDED.source, updated_at=EXCLUDED.updated_at
            """), {**row, "updated_at": now})
        session.commit()
    return len(all_rows)


async def get_national_team_holdings(session: AsyncSession, report_date: str | None = None,
                                     institution: str | None = None, change_type: str | None = None) -> dict:
    filters = []
    params: dict[str, str] = {}
    dates = (await session.execute(text(
        "SELECT DISTINCT report_date FROM national_team_holdings ORDER BY report_date DESC"
    ))).scalars().all()
    # The table stores a long disclosure history. Default to the latest period so
    # the public page never attempts to serialize the entire dataset.
    selected_report_date = report_date or (dates[0] if dates else None)
    if selected_report_date:
        filters.append("report_date = :report_date"); params["report_date"] = selected_report_date
    if institution:
        filters.append("institution = :institution"); params["institution"] = institution
    base_filters = list(filters)
    base_params = dict(params)
    if change_type:
        filters.append("change_type = :change_type"); params["change_type"] = change_type
    where = " WHERE " + " AND ".join(filters) if filters else ""
    base_where = " WHERE " + " AND ".join(base_filters) if base_filters else ""
    institutions = (await session.execute(text("SELECT DISTINCT institution FROM national_team_holdings ORDER BY institution"))).scalars().all()
    rows = (await session.execute(text(f"""
        SELECT report_date, institution, code, name, shares, holding_ratio,
               change_shares, change_type, market_value, source
        FROM national_team_holdings{where}
        ORDER BY report_date DESC, change_type, institution, code
    """), params)).mappings().all()
    base_rows = (await session.execute(text(f"""
        SELECT report_date, institution, code, name, shares, holding_ratio,
               change_shares, change_type, market_value, source
        FROM national_team_holdings{base_where}
        ORDER BY change_shares DESC NULLS LAST, institution, code
    """), base_params)).mappings().all()
    base_items = [dict(row) for row in base_rows]
    type_counts: dict[str, int] = {}
    team_counts: dict[str, int] = {}
    stock_changes: list[dict] = []
    for item in base_items:
        kind = item.get("change_type") or "未知"
        type_counts[kind] = type_counts.get(kind, 0) + 1
        team = _team_name(item["institution"])
        team_counts[team] = team_counts.get(team, 0) + 1
        if item.get("change_shares") is not None and kind in {"增持", "减持", "新进", "退出披露范围"}:
            stock_changes.append({"code": item["code"], "name": item.get("name"), "institution": item["institution"], "change_type": kind, "change_shares": item["change_shares"]})
    stock_changes.sort(key=lambda x: abs(x["change_shares"] or 0), reverse=True)
    summary = {
        "total_rows": len(base_items),
        "stock_count": len({item["code"] for item in base_items}),
        "institution_count": len({item["institution"] for item in base_items}),
        "type_counts": type_counts,
        "team_counts": [{"name": k, "count": v} for k, v in sorted(team_counts.items(), key=lambda x: -x[1])],
        "top_changes": stock_changes[:10],
    }
    updated = (await session.execute(text(
        "SELECT MAX(updated_at) FROM national_team_holdings"
    ))).scalar_one_or_none()
    return {
        "report_dates": list(dates),
        "selected_report_date": selected_report_date,
        "institutions": list(institutions),
        "items": [dict(row) for row in rows],
        "summary": summary,
        "last_updated_at": updated,
        "coverage_note": "报告期末公开披露数据；变化类型依据相邻报告期推断，不代表实时成交。",
    }
