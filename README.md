# 雪球大V帖子抓取 + AI 总结

抓取雪球指定大V的帖子，用 AI（中转站 OpenAI 兼容接口）做 **日 / 周 / 月 / 年** 总结，
并提炼 **精华帖**，客观整理作者提到的标的和观点。

> ⚠️ 本工具只整理"作者说了什么"，输出是对公开帖子的客观摘要，**不构成投资建议**。
> 任何买卖决策请你自己判断，并回看原帖核实，别只依赖单一信息源或 AI 摘要。

## 目录结构

```
config.py       读取 .env 配置
db.py           SQLite：帖子去重入库 + 总结缓存
scraper.py      雪球爬虫（Playwright 驱动本机 Edge）
summarizer.py   AI 总结（日总结 / 周月年归并 / 精华提取）
web.py          本地网页看板（Flask + ECharts）
templates/      看板页面
static/         看板样式与脚本
main.py         命令行入口
.env            你的密钥与配置（不要提交到公开仓库）
data/posts.db   抓到的帖子（自动生成）
reports/        生成的 Markdown 报告（自动生成）
```

## 安装

```powershell
pip install -r requirements.txt
```

> 抓取用 Playwright 驱动你本机的 **Edge**，不会额外下载浏览器。

## 配置（.env）

1. **API**：已填好中转站的 `RELAY_API_KEY` / `RELAY_API_URL` / `RELAY_MODEL`。
2. **目标大V**：把主页链接填到 `XUEQIU_USERS`，多个用英文逗号分隔。
   推荐用 `https://xueqiu.com/u/数字` 形式（最稳）。
3. 不再需要手动复制 cookie —— 改用下面的"登录一次"流程。

## 使用

雪球用阿里云 WAF 反爬，所以抓取走"真实 Edge + 你的登录态"。**首次先登录一次：**

```powershell
# 0. 首次：打开 Edge 登录雪球（若弹滑块，手动拖一下），登录后回终端按回车
python main.py login

# 1. 抓帖子（会打开 Edge，逐个大V主页滚动加载）
python main.py crawl

# 2. 看抓到了什么
python main.py stats

# 3. 各级总结（不带 --date 默认今天/本周/本月/今年）
python main.py summary daily
python main.py summary daily   --date 2026-06-29
python main.py summary weekly
python main.py summary monthly --date 2026-06-15
python main.py summary yearly  --date 2026-01-01

# 只处理某个人（id 或昵称片段）
python main.py summary weekly --user 大V昵称

# 重新生成（忽略缓存）
python main.py summary daily --regen

# 4. 精华帖（按互动量取 top N）
python main.py highlights --period month --topn 10

# 5. 网页看板（暗色金融仪表盘，浏览器查看）
python main.py serve          # 然后打开 http://127.0.0.1:5000
```

登录态保存在 `data/edge_profile`，之后基本不用再登。`HEADLESS=false`（默认）会显示浏览器窗口，
不容易被反爬识别；想试无人值守可改成 `true`，但可能更容易触发滑块。

## 定时自动采集（Windows 任务计划程序）

每天自动跑「采集 + 日总结」：

```powershell
# 注册每日任务（默认 22:37，可用 -At 改时间；无需管理员）
powershell -ExecutionPolicy Bypass -File register_task.ps1
powershell -ExecutionPolicy Bypass -File register_task.ps1 -At 21:07

# 立即试跑一次 / 查看 / 删除
Start-ScheduledTask -TaskName XueqiuDailyCrawl
Get-ScheduledTask   -TaskName XueqiuDailyCrawl | Get-ScheduledTaskInfo
Unregister-ScheduledTask -TaskName XueqiuDailyCrawl -Confirm:$false
```

要点与限制：

- 任务设为**仅在你登录 Windows 时运行**——因为采集要弹有头 Edge，需要桌面。若设定时间电脑没开机，
  下次登录会自动补跑。
- 采集时会弹出 Edge 窗口自动翻页（正常现象）。若弹滑块且无人处理，这次可能采集不到，
  运行日志会记录被拦截次数。
- 每次运行的输出写在 `data/schedule.log`。
- 想连周/月总结也自动，可再注册一个每周任务，动作换成 `python main.py summary weekly`。

## 工作原理

- 总结**分层归并**省 token：日总结由原帖生成并缓存；周/月总结复用已有日总结再归并；
  年度归纳复用月总结。所以建议先 `crawl`，再从日总结往上做。
- 帖子按 `id` 去重，重复 `crawl` 只新增没见过的帖子。

## 后续可加（已预留接口）
- **多人合并总结**：当前是每人一份；如需"把多个大V观点横向对比"再扩展 summarizer。
- **股票提醒**：在入库时匹配关键词/标的，命中就推送。

## 注意

- 雪球接口和反爬策略会变。如果 `crawl` 报错或拿不到数据，多半是 cookie 过期，重新复制一遍。
- 请控制抓取频率（`REQUEST_DELAY`），只抓公开内容，自用即可，遵守雪球的使用条款。
