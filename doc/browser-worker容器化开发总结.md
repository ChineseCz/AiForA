# browser-worker 容器化开发总结

> **Phase**：Phase 17  
> **日期**：2026-08-19  
> **分支**：`feature/browser-worker-storage-state` → 合并到 `dev`

---

## 一、背景与问题

项目原有设计中，`browser` 队列（雪球抓取、K 线回补、雪球板块同步）依赖真实 Edge 浏览器的登录态，**只能在本机 Windows 上跑**，无法容器化部署到服务器。

原始设计的限制：
- `docker-compose.yml` 里没有 `browser-worker` 服务，注释写明"在 Windows 宿主机运行"
- `requirements.txt` 里故意不包含 playwright（注释：抓取任务在 Windows 宿主 worker 跑）
- 服务器部署后，雪球抓取和 K 线回补功能实际上处于"不可用"状态

---

## 二、解决方案选型

调研了四种方案，最终选择**方案 C（Storage State 容器化）**：

| 方案 | 描述 | 结论 |
|------|------|------|
| A：SSH 隧道 + 本机 worker | 本机 Windows 连服务器 Redis | 过渡方案，需本机长期在线 |
| B：服务器装 Chromium + xvfb | 服务器上装图形环境 | 配置复杂，登录态不稳定 |
| C：Storage State 容器化 | 导出登录态 JSON，容器加载 | ✅ **最优**，无额外成本 |
| D：独立 Worker 服务器 | 另租一台服务器跑 browser worker | 需额外费用，维护两台服务器 |

**方案 C 的核心思路**：
- 本机 Edge 登录雪球 → 用 `export_xueqiu_state.py` 导出 `xueqiu-state.json`（126KB）
- 上传到服务器，Docker browser-worker 容器加载该文件
- Playwright 官方镜像内置 Chromium，无需 xvfb 或图形界面

---

## 三、代码改动

### 1. `backend/app/scrapers/xueqiu.py`

`open_context()` 函数按 `BROWSER_CHANNEL` 分支：

```python
if settings.browser_channel:
    # 本机模式：Edge + persistent profile（原有逻辑不变）
    ctx = playwright.chromium.launch_persistent_context(
        user_data_dir=profile,
        channel=settings.browser_channel,  # msedge
        ...
    )
else:
    # 服务器模式：Chromium 无头 + storage state 文件
    state_file = os.path.join(settings.data_dir, "xueqiu-state.json")
    browser = playwright.chromium.launch(headless=True, ...)
    ctx = browser.new_context(storage_state=state_file if os.path.exists(state_file) else None)
```

### 2. `backend/app/scrapers/kline.py`

`backfill_history()` 同样按 `BROWSER_CHANNEL` 分支：

```python
if settings.browser_channel:
    # 本机：Edge persistent context
    ctx = p.chromium.launch_persistent_context(channel=settings.browser_channel, ...)
else:
    # 服务器：Chromium 无头（K 线无需登录态，只需真实浏览器指纹绕反爬）
    browser = p.chromium.launch(headless=True, ...)
    ctx = browser.new_context(locale="zh-CN")
```

### 3. `backend/docker-compose.yml`

新增 `browser-worker` 服务：

```yaml
browser-worker:
  build: .
  command: celery -A app.workers.celery_app worker -Q browser --pool=solo --loglevel=info
  environment:
    BROWSER_CHANNEL: ""     # 留空使用 Chromium
    HEADLESS: "true"
  volumes:
    - ./data:/app/data      # 挂载 xueqiu-state.json 所在目录
```

### 4. `backend/Dockerfile`

换用 Playwright 官方镜像（内置 Chromium + 系统依赖）：

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble
```

### 5. `backend/requirements.txt`

添加 playwright 依赖：

```
playwright>=1.40
```

### 6. 新增 `backend/export_xueqiu_state.py`

本机导出雪球登录态的工具脚本，从 `edge_profile/` 提取 cookies 转为 Playwright Storage State 格式。

---

## 四、部署步骤（首次）

### 本机操作

```powershell
# 1. 导出雪球登录态
cd backend
python export_xueqiu_state.py

# 2. 上传到服务器
scp data/xueqiu-state.json ubuntu@124.222.169.60:/data/app/backend/data/
```

### 服务器操作

```bash
# 1. 拉取代码
cd /data/app
git pull origin dev

# 2. 构建镜像（首次需要拉取 playwright 官方镜像，约 1.5GB）
cd backend
docker compose build

# 3. 启动服务
docker compose up -d

# 4. 验证
docker compose logs -f browser-worker
```

---

## 五、踩过的坑

### 坑 1：playwright 官方镜像名称
- `playwright/python:v1.48.0-jammy` → `denied`（Docker Hub 没有）
- `microsoft/playwright-python:v1.48.0-jammy` → `not found`
- `mcr.microsoft.com/playwright/python:v1.48-jammy` → `not found`（版本号格式错误）
- ✅ `mcr.microsoft.com/playwright/python:v1.62.0-noble` → 成功

### 坑 2：requirements.txt 必须声明 playwright ⚠️ 已更正
`mcr.microsoft.com/playwright/python:v1.62.0-noble` 官方镜像**只内置了 Chromium 二进制和系统依赖**，并不预装 playwright Python 包（`pip list` 输出为空，`pip show playwright` 返回 not found）。必须在 `requirements.txt` 里显式声明：
```
playwright>=1.40
```
- ~~原始结论"已预装，无需声明"是错的~~ — 当时服务器跑通是因为用的是旧镜像（构建时 requirements.txt 还有这行），rebuild 后立刻复现 `No module named 'playwright'`
- 版本冲突担忧是多余的：pip 安装的版本不超过镜像内 Chromium 对应版本即可

### 坑 3：edge_profile 和 xueqiu-state.json 是两回事
- `edge_profile/`：Edge 浏览器完整的 profile 目录（11MB），供 `launch_persistent_context` 使用
- `xueqiu-state.json`：Playwright Storage State 格式（126KB），供 `new_context(storage_state=...)` 使用
- 两者不能互换，需要先运行 `export_xueqiu_state.py` 从 profile 提取 state 文件

### 坑 4：GitHub 在腾讯云服务器访问不稳定
- 可用镜像：`gitclone.com`（502 偶发）、`ghproxy.net`
- 最终用官方地址配合重试成功

### 坑 5：scp 上传失败（exit code 255）
- 原因：PowerShell 的 scp 不支持密码认证（需要 SSH key 或 PuTTY 的 pscp）
- 解决：手动在终端输入密码执行 scp

---

## 六、验证结果

抓取任务成功执行日志：

```
🚀 启动浏览器，开始采集…
→ 正在抓取 https://xueqiu.com/u/7143769715 …
✅ 冰冰小美（7143769715）：新增 7 条
→ 正在抓取 https://xueqiu.com/u/1314783718 …
✅ 饕餮海（1314783718）：新增 3 条
...
✅ 今日总结任务已派发
✅ Task browser.crawl succeeded in 89s
```

---

## 七、后续维护

### 登录态过期时（约 30 天）

```powershell
# 本机重新导出
cd backend
python export_xueqiu_state.py

# 上传到服务器
scp data/xueqiu-state.json ubuntu@124.222.169.60:/data/app/backend/data/

# 重启 browser-worker
ssh ubuntu@124.222.169.60 "cd /data/app/backend && docker compose restart browser-worker"
```

### 切换方式（本机/服务器）

只需修改 `.env` 的一个配置：

```env
# 本机 Windows 模式（Edge）
BROWSER_CHANNEL=msedge

# 服务器模式（Chromium）
BROWSER_CHANNEL=
```

---

**文档版本**: v1.0
**创建时间**: 2026-08-19
**分支**: feature/browser-worker-storage-state → dev
