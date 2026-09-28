from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_visitor
from app.services import strategy_review

router = APIRouter(prefix="/api")


@router.get("/strategy-review")
async def api_strategy_review(start: str | None = Query(None), end: str | None = Query(None),
                              strategy: str | None = Query(None), limit: int = Query(100, ge=1, le=500),
                              session: AsyncSession = Depends(db_session)):
    return await strategy_review.get_review(session, start, end, strategy, limit)


@router.get("/strategy-review/combination")
async def api_strategy_combination(buy_strategy: str | None = Query(None), sell_strategy: str | None = Query(None),
                                   buy_strategies: str | None = Query(None), sell_strategies: str | None = Query(None),
                                   buy_operator: str = Query("OR"), sell_operator: str = Query("OR"),
                                   initial_capital: float = Query(100000, ge=1000, le=100000000),
                                   max_positions: int = Query(10, ge=1, le=100),
                                   ranking: str = Query("change_pct"),
                                   exclude_chinext: bool = Query(False), exclude_star: bool = Query(False),
                                   exclude_st: bool = Query(True),
                                   min_change_pct: float | None = Query(None, ge=-30, le=30),
                                   max_change_pct: float | None = Query(None, ge=-30, le=30),
                                   min_total_mv: float | None = Query(None, ge=0),
                                   max_total_mv: float | None = Query(None, ge=0),
                                   take_profit_1_pct: float = Query(10, ge=0, le=1000), take_profit_1_fraction: float = Query(0.25, ge=0, le=1),
                                   take_profit_2_pct: float = Query(20, ge=0, le=1000), take_profit_2_fraction: float = Query(0.25, ge=0, le=1),
                                   take_profit_3_pct: float = Query(30, ge=0, le=1000), take_profit_3_fraction: float = Query(0.25, ge=0, le=1),
                                   buy_fee_rate: float = Query(0.0003, ge=0, le=0.02),
                                   sell_fee_rate: float = Query(0.0003, ge=0, le=0.02),
                                   stamp_duty_rate: float = Query(0.0005, ge=0, le=0.02),
                                   start: str | None = Query(None), end: str | None = Query(None),
                                   limit: int = Query(500, ge=1, le=1000),
                                   session: AsyncSession = Depends(db_session)):
    buys = [x for x in (buy_strategies or buy_strategy or "").split(",") if x]
    sells = [x for x in (sell_strategies or sell_strategy or "").split(",") if x]
    return await strategy_review.run_expression_combination(
        session, buys, sells, buy_operator, sell_operator, start, end, limit,
        initial_capital, max_positions, ranking, buy_fee_rate, sell_fee_rate, stamp_duty_rate,
        exclude_chinext, exclude_star, exclude_st, min_change_pct, max_change_pct, min_total_mv, max_total_mv,
        take_profit_1_pct, take_profit_1_fraction, take_profit_2_pct, take_profit_2_fraction,
        take_profit_3_pct, take_profit_3_fraction,
    )


@router.post("/strategy-review/combination/run")
async def api_start_strategy_combination(body: dict):
    from app.repositories import jobs
    from app.workers.tasks.strategy_review import task_strategy_combination
    allowed = {"buy_strategies", "sell_strategies", "buy_operator", "sell_operator", "start", "end", "limit",
               "initial_capital", "max_positions", "ranking", "buy_fee_rate", "sell_fee_rate", "stamp_duty_rate"}
    allowed.update({"exclude_chinext", "exclude_star", "exclude_st", "min_change_pct", "max_change_pct", "min_total_mv", "max_total_mv"})
    allowed.update({"take_profit_1_pct", "take_profit_1_fraction", "take_profit_2_pct", "take_profit_2_fraction", "take_profit_3_pct", "take_profit_3_fraction", "allow_second_entry", "second_entry_drawdown_pct"})
    params = {k: body[k] for k in allowed if k in body}
    if not params.get("buy_strategies") or not params.get("sell_strategies"):
        raise HTTPException(400, "请至少选择一个买入策略和一个卖出策略")
    if jobs.is_running("strategy_combination"):
        return {"started": False, "running": True}
    job_id = jobs.create_job("strategy_combination", "手动组合策略回测", params)
    task_strategy_combination.delay(params, job_id=job_id)
    return {"started": True, "running": True, "job_id": job_id}


@router.get("/strategy-review/combination/status")
async def api_strategy_combination_status(session: AsyncSession = Depends(db_session)):
    from app.repositories import jobs
    return await jobs.get_job_status(session, "strategy_combination")


@router.get("/strategy-review/saved")
async def api_saved_combinations(user_id: str = Depends(require_visitor), session: AsyncSession = Depends(db_session)):
    return {"items": await strategy_review.list_saved_combinations(session, user_id)}


class SaveCombinationBody(BaseModel):
    name: str
    buy_expression: dict
    sell_expression: dict
    execution: dict | None = None


@router.post("/strategy-review/saved")
async def api_save_combination(body: SaveCombinationBody, user_id: str = Depends(require_visitor), session: AsyncSession = Depends(db_session)):
    # 兼容旧前端把 execution 放在 buy_expression 内的格式；新格式优先使用顶层字段。
    execution = body.execution or body.buy_expression.get("execution") or {}
    buy_expression = {k: v for k, v in body.buy_expression.items() if k != "execution"}
    return await strategy_review.save_combination(session, user_id, body.name, {**buy_expression, "execution": execution}, body.sell_expression)


@router.delete("/strategy-review/saved/{combination_id}")
async def api_delete_combination(combination_id: int, user_id: str = Depends(require_visitor), session: AsyncSession = Depends(db_session)):
    return {"deleted": await strategy_review.delete_combination(session, user_id, combination_id)}

@router.put("/strategy-review/saved/{combination_id}")
async def api_update_combination(combination_id: int, body: SaveCombinationBody, user_id: str = Depends(require_visitor), session: AsyncSession = Depends(db_session)):
    execution = body.execution or body.buy_expression.get("execution") or {}
    buy_expression = {k: v for k, v in body.buy_expression.items() if k != "execution"}
    return await strategy_review.update_combination(session, user_id, combination_id, body.name, {**buy_expression, "execution": execution}, body.sell_expression)
