"""Preview or remove daily market rows dated outside recorded exchange sessions.

The Shanghai-Shenzhen 300 index calendar is used as the session reference. Run
without --apply first and review every reported date before deleting anything.
"""
import argparse
from datetime import date

from sqlalchemy import text

from app.core.sync_db import sync_session


def _candidate_dates(session) -> list[str]:
    calendar = session.execute(text(
        "SELECT DISTINCT trade_date FROM index_daily WHERE code='sh000300' ORDER BY trade_date"
    )).scalars().all()
    if not calendar:
        raise RuntimeError("no sh000300 index calendar is available")

    first, last = str(calendar[0]), str(calendar[-1])
    market_dates = {str(day) for day in calendar}
    observed = session.execute(text("""
        SELECT trade_date FROM stock_daily WHERE trade_date BETWEEN :first AND :last
        UNION
        SELECT trade_date FROM bond_daily WHERE trade_date BETWEEN :first AND :last
        UNION
        SELECT trade_date FROM stock_indicator WHERE trade_date BETWEEN :first AND :last
        UNION
        SELECT trade_date::text FROM strategy_daily_runs
        WHERE trade_date BETWEEN CAST(:first AS date) AND CAST(:last AS date)
        ORDER BY trade_date
    """), {"first": first, "last": last}).scalars().all()
    return sorted(str(day) for day in observed if str(day) not in market_dates)


def _counts(session, trade_date: str) -> dict[str, int]:
    counts = {}
    for table in ("stock_daily", "bond_daily", "stock_indicator", "strategy_daily_runs"):
        day = date.fromisoformat(trade_date) if table == "strategy_daily_runs" else trade_date
        counts[table] = session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE trade_date=:day"), {"day": day}
        ).scalar_one()
    return counts


def _delete_date(session, trade_date: str) -> dict[str, int]:
    strategy_day = date.fromisoformat(trade_date)
    session.execute(text("""
        DELETE FROM strategy_daily_picks
        WHERE run_id IN (SELECT id FROM strategy_daily_runs WHERE trade_date=:day)
    """), {"day": strategy_day})
    counts = {}
    for table in ("stock_indicator", "strategy_daily_runs", "stock_daily", "bond_daily"):
        day = strategy_day if table == "strategy_daily_runs" else trade_date
        result = session.execute(text(f"DELETE FROM {table} WHERE trade_date=:day"), {"day": day})
        counts[table] = result.rowcount
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, help="limit cleanup to one date, for example 2026-09-25")
    parser.add_argument("--apply", action="store_true", help="delete the previewed rows")
    args = parser.parse_args()

    with sync_session() as session:
        dates = _candidate_dates(session)
        if args.date:
            target = args.date.isoformat()
            dates = [day for day in dates if day == target]
        if not dates:
            if args.date:
                print(f"No non-session market data found for {args.date.isoformat()}.")
            else:
                print("No non-session market dates found in the available index calendar range.")
            return 0

        print(f"Non-session dates within the index calendar range: {len(dates)}")
        for day in dates:
            counts = _counts(session, day)
            print(f"{day}: " + ", ".join(f"{table}={count}" for table, count in counts.items()))

        if not args.apply:
            print("Preview only. Add --apply after reviewing the dates and row counts.")
            return 0

        for day in dates:
            deleted = _delete_date(session, day)
            print(f"deleted {day}: " + ", ".join(f"{table}={count}" for table, count in deleted.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
