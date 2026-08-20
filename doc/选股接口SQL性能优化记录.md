# Phase 2-5：选股接口（/api/screen）SQL 性能优化记录

**Phase**：2-5（服务化重构期间）  
**日期**：2026-07-09  
**提交范围**：`44db4f0` ~ `125f694`

## 背景

用户反馈选股筛选（`/api/screen`）响应很慢。排查前先排除了几个"看起来最可能"但实际无关的嫌疑对象。

## 排查过程

先用 `EXPLAIN ANALYZE` 逐个验证直觉上的重点表，结果全部正常：

- `stock_daily`（522万行）取最新交易日快照：`SELECT * FROM stock_daily WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily)`，命中 `idx_stock_daily_date`，1.289ms。
- `posts` 按用户+日期过滤：命中 `idx_posts_user_date`，0.559ms。

两个大表查询都很快，说明瓶颈不在这里。转而用 `cProfile` 直接在容器内对 `screen_api.screen()` 做函数级耗时统计（而不是继续猜代码）：

```bash
docker cp _tmp_profile.py backend-api-1:/app/_tmp_profile.py
docker compose exec -T api python _tmp_profile.py
```

结果定位到 `sync_data.py::get_distinct_users()`：一次 `/api/screen` 请求里被调用 2~3 次，累计 5.545s，占总耗时 5.879s 的绝大部分。

## 根因

`get_distinct_users()` 用来取"每个大V最新一条帖子对应的昵称"（同一 `user_id` 昵称可能改过名，不能直接 `DISTINCT`），原实现是逐行相关子查询：

```sql
SELECT user_id, user_name
FROM posts p
WHERE created_at = (SELECT MAX(created_at) FROM posts WHERE user_id = p.user_id)
GROUP BY user_id, user_name
```

`EXPLAIN ANALYZE` 显示内层子查询 `loops=4606`——外层 `posts` 表每一行都要重新扫一遍该用户的全部帖子求 `MAX(created_at)`，帖子表几千行时这是 O(n²) 级别的扫描。单条查询耗时 **2727.596ms**。

而这个函数在 `matching.py` 里被 `_recent_combined_text`、`get_bullish_users_map`、`derive_bullish_sectors` 三处分别调用（`user_ids` 为空时的默认路径），一次选股请求触发 2~3 次，直接叠加成几秒到近10秒的响应时间。

## 修复

改写为 `DISTINCT ON`，一次排序即可拿到"每个 `user_id` 最新一行"，语义完全等价：

```sql
SELECT DISTINCT ON (user_id) user_id, user_name
FROM posts
ORDER BY user_id, created_at DESC
```

`EXPLAIN ANALYZE` 验证：**4.702ms**，单条查询提速约 580 倍。返回值类型/顺序保持 `list[tuple[str, str]]` 不变，未改动调用方。

## 验证结果

修复后重启 `api` 容器（`docker cp` 不会让已运行的 uvicorn 进程重新 import 模块，必须重启才生效），清空 Redis dataver 缓存后用真实请求（非缓存命中）对拍：

| 请求场景 | 修复前 | 修复后（cache miss） |
|---|---|---|
| mentioned only | ~3-9s | 0.51s |
| sector 手动指定单个板块 | ~3-9s | 0.22s |
| sector 看多模式 | ~3-9s | 1.17s |
| preset ma_cross | ~3-9s | 0.34s |
| mentioned bullish_only | ~3-9s | 0.28s |

命中 Redis 缓存（同一请求体短期内重复请求）时进一步降到 0.01~0.07s，属于缓存本身的效果，不代表 SQL 优化的真实增益；上表是清缓存后的真实耗时对比。

## 追加优化：个股K线/基本面接口（/api/stock/kline、/api/stock/fundamentals）

`views.py::get_kline_view()`/`get_fundamentals_view()` 只需要"这一只股票"的最新快照，但原来调用的是
`db.get_latest_rows()`——这个函数是 `SELECT * FROM stock_daily WHERE trade_date = 最新交易日`，
不带 `code` 过滤，会把**当天全部5000+只股票**的行情整表拉回来，再在 Python 里 `{r["code"]: r for r in ...}`
建字典、只取其中一行。这是为"选股结果批量补行情"设计的函数（`screening.py`/`screen_api.py` 那几处一次要
判断几百上千只股票，确实需要整表），但个股详情页只查一只股票，被迫多背了一次全表 IO + 反序列化。

新增 `db.get_latest_row_by_code(code)`，直接 `WHERE code = :code AND trade_date = 最新交易日`，命中
`(trade_date, code)` 复合主键，索引扫描单行返回。`get_kline_view`/`get_fundamentals_view` 改用它。

清缓存后端到端对拍（`/api/stock/kline`，5只不同股票）：

| | 修复前 | 修复后 |
|---|---|---|
| 平均响应 | ~0.20s | ~0.11s |

`cProfile` 确认单次 `get_kline_view()` 调用中 SQL 部分占比从"整表扫描+反序列化5000+行"降到只反序列化1行，
剩余耗时主要是历史K线（几百到上千行）+ MA/MACD/KDJ/买卖点信号的 Python 计算，这部分是纯计算逻辑，
当前数据量下（单只股票几百至上千个交易日）不构成瓶颈，未做改动。

`group_members_view()`（分组页批量取多只股票行情）仍保留 `get_latest_rows()` 整表读法——分组成员通常有
多只股票，整表读一次比按 code 循环查询更划算，这里不是 N+1 场景。

## 追加优化：全站扫查（/api/users、/api/overview、/api/screen 板块看多模式、分组成员）

前两轮优化完成后，用子代理把 `sync_data.py`/`posts.py`/`matching.py`/`services/*` 里同类模式又扫了一遍，
找到几处同款问题，一并修掉：

### 1. `/api/users` 也有一份未修的相关子查询

`app/repositories/posts.py::get_distinct_users()`（异步版本，供 `/api/users` 用）跟 `sync_data.py` 里
已修的那个是**两份独立实现**，同样的相关子查询 bug，之前只改了同步版本，这份异步版本没跟着改。
`EXPLAIN ANALYZE` 实测：4606行 posts 下单条查询 **4124ms**。同样改成 `DISTINCT ON`，改完 **4.1ms**。

### 2. 选股结果附加板块信息时，为了查几个名字拉全市场整表

`matching.py::derive_bullish_sectors()`（挂在 `attach_sectors()`，每次 `/api/screen`/`preset` 结尾
**都会跑**，不管有没有开板块筛选）为了把"最近被看多"的几个股票名转成代码，调用
`db.get_latest_rows()` 拉全市场当天5500+行快照。`overview.py` 的 `get_bullish_heat`/
`get_board_bullish_heat` 也是同款写法，一次 `/api/overview` 未命中缓存时重复拉两次。

新增 `get_latest_rows_by_names(names)`（`WHERE name = ANY(:names) AND trade_date = ...`），三处调用点
改用它，只查需要的几个名字对应的行。`views.py::group_members_view()`（分组成员页）也有同款问题
（为了查分组里几只股票拉全表），新增 `get_latest_rows_by_codes(codes)` 一并修掉。

### 3. "看多板块"模式下 264 个板块名逐个查缓存，等于 N×2 次数据库往返

这是本轮扫查发现的、影响面比预期更大的一个：`matching.py::match_sector()` 收到
`derive_bullish_sectors()` 算出的板块/概念名列表后，对每个名字单独调用
`get_sector_members()` → `get_sector_members_cached()`，后者每次开一个新 session 跑 2 条 SQL
（先查 `updated_at` 判断新鲜度，再查成分股列表）。真实数据下这个列表有 **264 个板块名**，
等于一次请求打了 528 次数据库往返。

`cProfile` 实测"看多板块"模式的 `/api/screen`：优化前 1.259s（`get_sector_members_cached` 占
1.03s），比对照的"手动指定单个板块"（0.2s量级）慢了几倍，是选股功能里除了已修的两个之外最大的
单项开销。

新增 `get_sector_members_cached_batch(sectors)`，一次 `WHERE sector = ANY(:sectors)` 查询取出所有
板块名的成分股+更新时间，按 sector 分组后在 Python 里按新鲜度过滤；`match_sector()` 改为先批量查
一次，只有极少数缓存缺失/过期的板块名才回退到原来的单个懒加载路径（这些板块名可能需要现拉新浪接口
或雪球板块本来就没有缓存，无法批量处理）。修复后 `/api/screen`（看多板块模式）总耗时降到 0.636s，
`cProfile` 显示批量查询本身仅占 0.39s（vs 优化前的 264 次循环占 1.03s）。

### 4. 顺手补的索引

`job_runs` 表建表时没有任何索引（对照 `posts`/`stock_daily`/`stock_sector` 都有 `create_index`），
但 `jobs.py::get_latest_state()`/`any_running()` 全靠 `WHERE kind = :k ORDER BY id DESC LIMIT 1`，
是管理后台任务状态轮询的必经路径。当前 142 行数据量下走全表扫描也很快（<1ms），不是当前瓶颈，
但随着任务历史累积（`job_runs` 没有清理机制）迟早会退化。新增 migration `0005_job_runs_kind_index.py`
补 `(kind, id DESC)` 复合索引，防患于未然。

## 经验小结

- 排查慢查询别只凭直觉猜"大表就是瓶颈"，`EXPLAIN ANALYZE` + `cProfile` 定位到具体函数比读代码猜测更快更准。
- 相关子查询（correlated subquery）在"取每组最新一行"这类场景下很容易写成隐藏的 O(n²)；`DISTINCT ON (col) ... ORDER BY col, sort_col DESC` 是 Postgres 下更优的等价写法。
- `docker cp` 只改容器文件系统，不会触发已运行进程重新加载模块；验证修复效果前要 `docker compose restart <service>`。
