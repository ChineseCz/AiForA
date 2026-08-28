# 服务器浏览器 Worker 部署方案

> **Phase**：Phase 16  
> **日期**：2026-08-11  
> **提交范围**：`7fc428b` ~ `0529712`  
> 解决：腾讯云 Ubuntu 服务器上如何处理需要真实浏览器的抓取任务（雪球帖子、K 线回补、雪球板块）

> **当前状态（2026-08-27）**：生产环境已经采用服务器 Docker 内的 Playwright `browser-worker`，Windows Edge Worker 和 SSH 隧道方案已停止使用。本文历史方案仍保留用于排障参考，实际部署以“方案 C”和下方命令为准。

## 当前生产部署

服务器 Compose 栈包含 8 个服务：`postgres`、`pgbouncer`、`redis`、`api`、`worker`、`beat`、`browser-worker`、`frontend`。

```bash
cd /data/app
git pull --ff-only origin dev
cd backend
docker compose config -q
docker compose up -d --build api worker beat browser-worker frontend
docker compose exec -T api alembic upgrade head
docker compose up -d --force-recreate frontend
docker compose ps
```

`browser-worker` 的代码复制在 Docker 镜像中，没有挂载 `./app`。所以 `git pull` 只更新源码，必须使用 `--build` 重建；仅执行 `restart` 不会加载新的浏览器任务代码。

查看任务日志：

```bash
docker compose logs -f browser-worker
```

---

## 一、架构认知：Worker 和 Beat 是什么

### Beat（调度器）

Celery Beat 是一个**定时任务调度器**，只负责"到点发任务"，本身不执行任何业务逻辑。

- 每 60 秒执行一次 `beat.tick`，读 `schedules` 表决定是否派发雪球抓取任务
- 每 600 秒触发全市场行情同步（`stock.auto_sync_tick`）
- 周三/周日 20:00 触发周总结生成（`summarize.weekly_tick`）

### Worker（工人）

Celery Worker 是实际执行任务的进程，按队列分工：

| 队列 | 任务内容 | 运行位置 |
|------|---------|---------|
| `default` | 全市场快照同步、财务同步、指标预计算 | Docker 容器 |
| `llm` | AI 总结生成、菲比问答 | Docker 容器 |
| `browser` | 雪球帖子抓取、历史 K 线回补、雪球板块同步 | **⚠️ 需要真实浏览器** |

---

## 二、为什么 `browser` 队列不能直接容器化

核心原因是两个数据源对浏览器有特殊要求：

**雪球抓取**
- 需要真实 Edge 的登录态（存在 `data/edge_profile/`）
- 雪球板块页面是纯前端渲染，必须在已登录浏览器内用 `page.evaluate` fetch（带 cookie），纯 requests 直接 400

**历史 K 线**
- 新浪 K 线接口（`quotes.sina.cn`）纯 requests 批量查询约 250 只后触发永久 456 拒绝
- 必须在真实浏览器页面内 fetch 来携带正常 UA 和 cookie 绕过限制

Docker 容器内没有 Edge，Chromium 也无法稳定持有雪球登录态。

---

## 三、四种解决方案对比

| 对比项 | 方案 A：SSH 隧道 + 本机 Worker | 方案 B：服务器装 Chromium | 方案 C：Storage State 容器化 | 方案 D：独立 Worker 服务器 |
|-------|-------------------------------|--------------------------|---------------------------|-----------------------------|
| 本机依赖 | 需长期开着 | 不需要 | 仅首次登录导出 | 不需要 |
| 配置难度 | 低 | 高（xvfb+VNC） | 中（改代码+镜像） | 低（另开一台装环境） |
| 稳定性 | 高（Edge稳定） | 中（Chromium易失效） | 中（登录态定期刷新） | 高（可用 Edge） |
| 额外成本 | 无 | 无 | 无 | 约 40-60元/月（轻量服务器） |
| 全自动化 | ❌ 需本机在线 | ✅ | ✅ | ✅ |
| 行业标准 | 否 | 否 | ✅ Playwright 推荐 | 是（微服务拆分） |
| **推荐程度** | 🔵 过渡方案 | ❌ 不推荐 | ✅ **最优技术方案** | 🟡 土豪方案 |

---

## 四、推荐方案：SSH 隧道 + 本机 Windows Worker

### 原理

```
本机 Windows
  ├─ Edge browser worker（消费 browser 队列）
  └─ SSH 隧道（把服务器 Redis 6380 映射到本机 localhost:6380）

腾讯云 Ubuntu
  └─ Docker 栈（7 服务：postgres/pgbouncer/redis/api/worker/beat/frontend）
       └─ Redis 6380（通过隧道被本机 worker 连接，收发 browser 队列任务）
```

本机 worker 和服务器 Docker 栈共用同一个 Redis，但通过 SSH 隧道连接，不暴露端口到公网。

---

## 五、部署步骤

### 5.1 服务器端（当前部署方式）

```bash
# 登录服务器
ssh ubuntu@124.222.169.60

# 部署 Docker 栈
cd /data/app/backend
docker compose config -q
docker compose up -d --build api worker beat browser-worker frontend
docker compose exec -T api alembic upgrade head
docker compose up -d --force-recreate frontend

# 验证
docker compose ps
curl --fail http://localhost:8090/health
```

### 5.2 本机端：修改 .env

在本机 `backend/.env` 中添加或修改以下两行，指向本机 localhost（隧道映射端口）：

```env
CELERY_BROKER_URL=redis://localhost:6380/0
CELERY_RESULT_BACKEND=redis://localhost:6380/0
```

> ⚠️ 注意：`REDIS_URL` 是给 API 缓存用的，不用改；只改 Celery broker 这两项。

### 5.3 本机端：建立 SSH 隧道

单独开一个终端，保持运行：

```bash
ssh -L 6380:127.0.0.1:6380 ubuntu@124.222.169.60 -N
```

- `-L 6380:127.0.0.1:6380`：把本机 6380 映射到服务器的 127.0.0.1:6380
- `-N`：不执行命令，只保持隧道

### 5.4 本机端：启动 Browser Worker

另开一个终端：

```bash
cd backend
pip install -r requirements-host.txt

celery -A app.workers.celery_app worker -Q browser --pool=solo --loglevel=info
```

看到如下输出说明连接成功：

```
[celery@你的机器名] ready.
[queues]
. browser        exchange=browser(direct) key=browser
```

---

## 六、验证抓取是否正常

### 手动触发一次抓取任务

```bash
# 在服务器 API 容器内发送任务
docker compose exec api python -c "
from app.workers.celery_app import celery_app
celery_app.send_task('app.workers.tasks.browser.task_crawl', kwargs={'source': '手动测试', 'summarize': False})
print('任务已发送')
"
```

### 观察本机 worker 日志

本机 worker 终端应出现类似：

```
[2026-08-18 17:00:00,000: INFO/MainProcess] Task app.workers.tasks.browser.task_crawl received
[2026-08-18 17:00:05,000: INFO/MainProcess] 开始抓取雪球帖子...
```

### 查看任务执行记录

```bash
# 服务器上查看 job_runs 表
docker compose exec postgres psql -U natapp natapp -c \
  "SELECT id, job_type, status, created_at FROM job_runs ORDER BY created_at DESC LIMIT 5;"
```

---

## 七、日常维护

### 每次开机需要做的事（本机）

1. 开一个终端，启动 SSH 隧道：
   ```bash
   ssh -L 6380:127.0.0.1:6380 ubuntu@124.222.169.60 -N
   ```

2. 再开一个终端，启动 browser worker：
   ```bash
   cd backend
   celery -A app.workers.celery_app worker -Q browser --pool=solo --loglevel=info
   ```

### 雪球登录态失效时

登录态存在本机 `backend/data/edge_profile/`，一般长期有效。如果抓取报错提示未登录：

1. 关闭 browser worker
2. 手动打开 Edge，用 `data/edge_profile/` 作为用户目录登录一次雪球
3. 重启 browser worker

---

## 八、如果不想本机长期开着（备用方案 B）

服务器上配置 Chromium + xvfb，**仅适合有固定带宽且雪球抓取频率低的情况**：

```bash
# 1. 安装依赖（服务器上）
sudo apt install -y xvfb chromium-browser

cd /data/app/backend
pip install playwright
playwright install chromium
playwright install-deps chromium

# 2. 启动虚拟显示
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# 3. 首次登录雪球（需要 VNC 远程桌面，腾讯云控制台 → VNC 登录）
# 临时改 .env：HEADLESS=false
# 手动跑一次触发登录窗口，完成后改回 HEADLESS=true

# 4. 启动 browser worker
export DISPLAY=:99
celery -A app.workers.celery_app worker -Q browser --pool=solo --loglevel=info
```

> ⚠️ 雪球登录态在无头 Chromium 下稳定性不如 Edge，首次登录需要图形界面，配置成本较高，**不推荐作为主要方案**。

---

## 九、方案 C：Playwright Storage State + Docker 容器化（最优技术方案）

### 核心思路

利用 [Playwright 的 Storage State 机制](https://playwright.dev/docs/auth)把雪球登录态**导出成一个 JSON 文件**（cookies + localStorage），服务器上的 Docker 容器加载该文件，完全在 Chromium 无头模式下运行。无需本机在线，无需 xvfb，是 Playwright 官方推荐的持久化认证方案。

### 架构

```
本机 Windows（仅首次登录时需要）
  └─ 登录雪球 → 导出 xueqiu-state.json → scp 上传到服务器

腾讯云 Ubuntu
  └─ Docker 栈（8 服务，新增 browser-worker）
       └─ browser-worker 容器
            ├─ 官方 Playwright 镜像（内含 Chromium + 所有系统依赖）
            ├─ 加载 /app/data/xueqiu-state.json
            └─ 无头模式消费 browser 队列
```

### 实施步骤

**第一步：本机导出登录态**

```python
# 新建 backend/export_xueqiu_state.py
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir='./data/edge_profile',
        channel='msedge',
        headless=False
    )
    page = context.new_page()
    page.goto('https://xueqiu.com')
    input('请在浏览器中确认已登录雪球，然后按回车...')
    context.storage_state(path='./data/xueqiu-state.json')
    print('已保存到 data/xueqiu-state.json')
    context.close()
```

```bash
python export_xueqiu_state.py
scp backend/data/xueqiu-state.json ubuntu@124.222.169.60:/data/app/backend/data/
```

**第二步：修改 Dockerfile 使用官方 Playwright 镜像**

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.48-focal

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

**第三步：docker-compose.yml 添加 browser-worker**

```yaml
  browser-worker:
    build: .
    restart: unless-stopped
    command: celery -A app.workers.celery_app worker -Q browser --pool=solo --loglevel=info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      BROWSER_CHANNEL: ""   # 留空使用 Chromium
      HEADLESS: "true"
      TZ: Asia/Shanghai
    env_file:
      - .env
    volumes:
      - ./data:/app/data    # 挂载 xueqiu-state.json
```

**第四步：启动**

```bash
cd /data/app/backend
docker compose up -d --build browser-worker
docker compose logs -f browser-worker
```

### 登录态过期处理

雪球 token 一般 30 天左右过期，过期后重新导出上传即可：

```bash
# 本机
python export_xueqiu_state.py
scp backend/data/xueqiu-state.json ubuntu@124.222.169.60:/data/app/backend/data/

# 服务器
docker compose restart browser-worker
```

---

## 十、方案 D：独立 Worker 服务器（土豪方案）

### 核心思路

单独租一台轻量服务器（约 40-60 元/月，2 核 2G 够用），专门跑 browser worker，主服务器只跑 API + 数据库，两台服务器共用同一个 Redis broker。

### 架构

```
主服务器（腾讯云，现有的那台）
  └─ Docker 栈：postgres / pgbouncer / redis / api / worker(default+llm) / beat / frontend
       └─ Redis 对 Worker 服务器暴露（或 SSH 隧道）

Worker 服务器（新租一台，Ubuntu 2核2G，40-60元/月）
  └─ 直接装 Python + Playwright + Chromium（不用 Docker）
  └─ 登录雪球（有图形界面或 VNC，可用 Edge）
  └─ 启动：celery -A app.workers.celery_app worker -Q browser --pool=solo
```

### 优缺点

**优点**
- 不依赖本机，完全云端化
- Worker 服务器可以装 Edge（腾讯云轻量支持 Ubuntu Desktop / VNC）
- 主服务器不受 Chromium 内存影响
- 可以随时关掉 Worker 服务器省钱（不抓取时不用开着）

**缺点**
- 增加 40-60 元/月的费用
- 需要维护两台服务器
- Redis 跨服务器需要处理网络安全（内网互通或 SSH 隧道）

### 腾讯云实施步骤

```bash
# 1. 购买腾讯云轻量应用服务器，选 Ubuntu 22.04，2核2G
#    两台服务器选同一地域（广州/上海），开启内网互通

# 2. Worker 服务器上安装环境
sudo apt update && sudo apt install -y python3-pip git
git clone <repo> /data/app
cd /data/app/backend
pip install -r requirements-host.txt
pip install playwright
playwright install chromium
playwright install-deps chromium

# 3. Worker 服务器 .env，broker 指向主服务器内网 IP
CELERY_BROKER_URL=redis://主服务器内网IP:6380/0
CELERY_RESULT_BACKEND=redis://主服务器内网IP:6380/0
DATABASE_URL=postgresql+asyncpg://natapp:密码@主服务器内网IP:5433/natapp

# 4. 主服务器安全组：开放 6380 端口仅允许 Worker 服务器内网 IP 访问

# 5. 启动 worker
celery -A app.workers.celery_app worker -Q browser --pool=solo --loglevel=info
```

---

## 十一、总结：怎么选

```
你愿意花钱且追求全自动？
  ├─ 是 → 方案 D（独立 Worker 服务器，最省心）
  └─ 否 → 方案 C（Storage State 容器化，最优技术方案，无额外成本）
            如果方案 C 改代码太麻烦先用什么过渡？
              └─ 方案 A（SSH 隧道 + 本机，配置最简单，但需本机在线）
```

**当前建议**：使用方案 C 的服务器容器化 Playwright。方案 A 仅用于历史排障或临时回退，不应作为生产常驻方案。

---

**文档版本**: v2.0
**创建时间**: 2026-08-18
**适用分支**: dev
