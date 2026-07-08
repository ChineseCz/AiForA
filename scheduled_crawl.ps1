# 雪球每日自动采集 + 日总结
# 由 Windows 任务计划程序调用；也可手动运行：
#   powershell -ExecutionPolicy Bypass -File scheduled_crawl.ps1
#
# 说明：采集用有头 Edge，会弹出浏览器窗口，请在已登录桌面时运行。
#       若中途弹滑块无人处理，本次可能采集不到，日志会记录被拦截次数。

$ErrorActionPreference = "Continue"

# 统一 UTF-8，保证日志里的中文/emoji 不乱码
$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$proj = $PSScriptRoot
Set-Location $proj

# 优先用项目虚拟环境的 python，找不到就用 PATH 里的
$py = Join-Path $proj ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$log = Join-Path $proj "data\schedule.log"
$start = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $log -Value "`n===== $start 开始 =====" -Encoding utf8

# 1) 抓最新帖子（按 .env 的 MAX_PAGES，默认 10 页，适合每日补新）
$out = & $py main.py crawl 2>&1 | Out-String
Add-Content -Path $log -Value $out -Encoding utf8

# 2) 生成今天的日总结
$out = & $py main.py summary daily 2>&1 | Out-String
Add-Content -Path $log -Value $out -Encoding utf8

# 3) 同步一次A股行情快照（供选股功能使用；此时已收盘）
$out = & $py main.py stock-sync 2>&1 | Out-String
Add-Content -Path $log -Value $out -Encoding utf8

$end = Get-Date -Format "HH:mm:ss"
Add-Content -Path $log -Value "===== $end 结束 =====" -Encoding utf8
