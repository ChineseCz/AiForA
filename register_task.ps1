# 把每日采集脚本注册进 Windows 任务计划程序。
# 用法（无需管理员，普通 PowerShell 即可）：
#   powershell -ExecutionPolicy Bypass -File register_task.ps1
#   powershell -ExecutionPolicy Bypass -File register_task.ps1 -At 21:07     # 自定义时间
#
# 任务设为“仅在当前用户登录时运行”，这样有头 Edge 才能弹出窗口。
# 如果那个时间点电脑关机/睡眠，开机登录后会自动补跑（StartWhenAvailable）。

param(
    [string]$At = "22:37",
    [string]$TaskName = "XueqiuDailyCrawl"
)

$proj = $PSScriptRoot
$script = Join-Path $proj "scheduled_crawl.ps1"

if (-not (Test-Path $script)) {
    Write-Error "找不到 $script"
    exit 1
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""

$trigger = New-ScheduledTaskTrigger -Daily -At $At

# Interactive = 仅在用户登录时运行（GUI 才能显示），无需保存密码
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force `
    -Description "雪球大V每日自动采集 + 日总结" | Out-Null

Write-Host ""
Write-Host "✅ 已注册任务 '$TaskName'，每天 $At 运行（仅在你登录时）。"
Write-Host ""
Write-Host "常用命令："
Write-Host "  立即试跑：Start-ScheduledTask -TaskName $TaskName"
Write-Host "  查看状态：Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host "  改时间  ：重新运行本脚本并加 -At 09:30"
Write-Host "  删除任务：Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host "  运行日志：data\schedule.log"
