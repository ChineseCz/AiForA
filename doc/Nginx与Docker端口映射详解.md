# Nginx与Docker端口映射详解

> **Phase**：Phase 14-15（调试阶段技术文档）  
> **日期**：2026-08-18  
> 本文档整理了项目中 Nginx、Docker 端口映射、前后端通信的完整架构，帮助理解网络请求的完整流程。

---

## 一、核心概念

### 1.1 什么是前端？
- **前端（Frontend）**：React/Vue 等框架编写的代码，**编译后生成静态文件**（HTML/CSS/JS）
- 这些文件本身**不会运行**，需要浏览器下载后执行
- 存放位置：Nginx 的某个目录（如 `/usr/share/nginx/html`）

### 1.2 什么是 Nginx？
**Nginx 是 Web 服务器软件**，有两个核心功能：

#### ① 托管静态文件（Web Server）
```
用户请求 http://example.com/index.html
  → Nginx 从磁盘读取 /usr/share/nginx/html/index.html
  → 返回给浏览器
```
- 就像"文件柜管理员"，用户要什么文件就拿给你

#### ② 反向代理（Reverse Proxy）
```
用户请求 http://example.com/api/login
  → Nginx 检测到 /api 前缀
  → 转发到后端服务（如 FastAPI）
  → 后端返回 JSON
  → Nginx 再转给用户
```
- 就像"前台接待员"，把请求转给后面的专业部门处理
- **好处**：前端和后端用同一个域名，避免浏览器跨域问题

### 1.3 什么是 Docker 端口映射？
Docker 容器是**隔离的小系统**，有自己的网络空间。端口映射把**宿主机端口**和**容器端口**连接起来。

```yaml
ports:
  - "8090:80"
    ↑     ↑
  宿主机  容器内
```

**访问流程：**
```
外部访问 宿主机IP:8090
  → Docker 自动转发
  → 容器内的 80 端口
```

---

## 二、本项目的双层 Nginx 架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────┐
│  外部网络（微信服务器/用户浏览器）                        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP 请求
                     ↓
         ┌───────────────────────┐
         │  服务器公网 IP:80      │
         │  (124.222.169.60:80)  │
         └───────────┬───────────┘
                     ↓
    ┌────────────────────────────────────┐
    │  宿主机 Nginx（入口网关）           │
    │  - 监听 80 端口                    │
    │  - 转发所有请求到 8090              │
    └────────────┬───────────────────────┘
                 ↓
    ┌────────────────────────────────────┐
    │  宿主机 8090 端口                   │
    └────────────┬───────────────────────┘
                 │ Docker 端口映射
                 ↓
    ┌────────────────────────────────────┐
    │  Docker frontend 容器               │
    │  - 容器内监听 80 端口               │
    │  - 内部 Nginx 配置：                │
    │    ① 托管前端静态文件               │
    │    ② /api 请求转发到 api 容器       │
    └────────┬─────────────┬─────────────┘
             │             │
    前端文件 │             │ API 请求
             ↓             ↓
      返回给用户    ┌──────────────────┐
                   │ Docker api 容器   │
                   │ FastAPI (8000端口)│
                   │ ↓                 │
                   │ PostgreSQL        │
                   │ Redis             │
                   └──────────────────┘
```

### 2.2 两个 Nginx 的职责

| Nginx | 位置 | 监听端口 | 职责 |
|-------|------|----------|------|
| **宿主机 Nginx** | Ubuntu 系统 `/etc/nginx` | 80 | 入口守门员：统一接收外部请求，转发到 Docker |
| **容器 Nginx** | Docker frontend 容器内 | 80（映射到宿主机 8090） | ① 返回前端文件 ② 转发 /api 到后端 |

**比喻：**
- 宿主机 Nginx = **大楼门卫**（决定进哪个电梯）
- 容器 Nginx = **楼层前台**（决定给你文件还是转给后端部门）

---

## 三、完整请求流程示例

### 3.1 用户访问首页

```
① 用户浏览器访问：http://124.222.169.60/
                    ↓
② 请求到达宿主机 80 端口（宿主机 Nginx）
                    ↓
③ 宿主机 Nginx 配置：proxy_pass http://127.0.0.1:8090;
                    ↓
④ 转发到宿主机 8090 端口
                    ↓
⑤ Docker 端口映射（8090:80）→ 进入 frontend 容器的 80 端口
                    ↓
⑥ 容器内 Nginx 检测请求路径 "/"
                    ↓
⑦ 读取磁盘文件：/usr/share/nginx/html/index.html
                    ↓
⑧ 返回 HTML 文件给浏览器
                    ↓
⑨ 浏览器解析 HTML，加载 CSS/JS
                    ↓
⑩ 前端页面渲染完成
```

### 3.2 用户点击"登录"按钮

```
① 浏览器发起 AJAX 请求：POST http://124.222.169.60/api/user/login
                    ↓
② 请求到达宿主机 80 端口（宿主机 Nginx）
                    ↓
③ 宿主机 Nginx 转发到 8090
                    ↓
④ Docker 映射 → frontend 容器 80 端口
                    ↓
⑤ 容器 Nginx 检测到路径 "/api"
                    ↓
⑥ 容器 Nginx 配置：
   location /api {
       proxy_pass http://api:8000;  # api 是容器名
   }
                    ↓
⑦ 转发到 api 容器的 8000 端口（FastAPI）
                    ↓
⑧ FastAPI 处理登录逻辑（查数据库、生成 JWT）
                    ↓
⑨ 返回 JSON：{"access_token": "eyJ0..."}
                    ↓
⑩ 原路返回到浏览器
                    ↓
⑪ 前端 JS 保存 token，跳转到首页
```

### 3.3 微信服务器验证 Webhook

```
① 微信服务器发送 GET 请求验证签名：
   http://124.222.169.60/api/user/wechat/webhook?signature=xxx&timestamp=xxx&nonce=xxx&echostr=hello
                    ↓
② 宿主机 Nginx (80) → 转发到 8090
                    ↓
③ Docker 映射 → frontend 容器 Nginx (80)
                    ↓
④ 容器 Nginx 检测到 /api → 转发到 api 容器 8000
                    ↓
⑤ FastAPI 路由 /api/user/wechat/webhook
   - 读取环境变量 WECHAT_TOKEN=cz149
   - 校验签名 sha1(token+timestamp+nonce)
   - 签名正确 → 返回 echostr
                    ↓
⑥ 微信服务器收到 echostr → 验证通过 ✓
```

---

## 四、为什么需要双层 Nginx？

### 4.1 为什么不直接用宿主机 Nginx 托管前端？

**可以，但不推荐。**

#### 方案A：只用宿主机 Nginx（不推荐）
```
外部 :80 → 宿主机 Nginx
            ├─ 直接托管前端静态文件
            └─ /api 转发到 Docker api 容器 :8088
```

**缺点：**
- 每次前端更新需要手动复制文件到 `/var/www/html`
- Nginx 配置不在代码仓库，难以版本管理
- 多套环境（dev/test/prod）配置混乱

#### 方案B：双层 Nginx + Docker（推荐，当前架构）
```
外部 :80 → 宿主机 Nginx :80
            ↓ 转发到 8090
          Docker frontend 容器
            ├─ Nginx 托管前端（容器化）
            └─ /api 转发到 api 容器
```

**优点：**
- **容器化部署**：`docker compose up -d` 一键启动
- **配置跟代码走**：Nginx 配置在 `frontend/nginx.conf`，版本管理
- **环境隔离**：多套环境并存，互不干扰
- **易于迁移**：换服务器只需 `docker compose up`

### 4.2 为什么微信 Webhook 必须用 80 端口？

**微信公众平台的限制：**
- Webhook URL 不允许带端口号（`:8090` 会被拒绝）
- 只接受标准端口：
  - HTTP → 80
  - HTTPS → 443

**解决方案：**
- 宿主机 Nginx 监听 80 端口
- 配置转发到 Docker frontend 的 8090
- 微信配置：`http://124.222.169.60/api/user/wechat/webhook`（不带端口号）

---

## 五、配置文件解析

### 5.1 docker-compose.yml（端口映射）

```yaml
services:
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    container_name: frontend
    ports:
      - "8090:80"  # 宿主机 8090 → 容器 80
    depends_on:
      - api
    networks:
      - app-network

  api:
    # ...
    ports:
      - "8088:8000"  # 宿主机 8088 → 容器 8000（仅用于直接调试）
    expose:
      - "8000"  # 容器间通信用此端口
```

**关键点：**
- `ports`：暴露到宿主机，外部可访问
- `expose`：仅容器间可访问，外部不可直接访问

### 5.2 frontend 容器的 Nginx 配置

```nginx
# frontend/nginx.conf
server {
    listen 80;  # 容器内监听 80
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # 前端路由（SPA）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api {
        proxy_pass http://api:8000;  # api 是 docker-compose 里的服务名
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**关键点：**
- `http://api:8000`：Docker 网络内通过**服务名**访问（不用 IP）
- `try_files ... /index.html`：支持前端路由（React Router）

### 5.3 宿主机 Nginx 配置（需添加）

```nginx
# /etc/nginx/sites-available/natapp
server {
    listen 80;
    server_name 124.222.169.60;  # 或你的域名

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**启用配置：**
```bash
sudo ln -s /etc/nginx/sites-available/natapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 六、常见问题

### Q1: 为什么访问 8088 会卡住，8090 正常？
**A:** 检查云服务器安全组规则，可能只开放了 8090 端口。但不用管，直接用 8090（通过 frontend 容器反代）即可。

### Q2: Docker 容器之间如何通信？
**A:** 通过 Docker 网络的**服务名**访问：
```yaml
# docker-compose.yml
services:
  api:  # ← 服务名
    # ...
  frontend:
    # ...
```

在 frontend 容器的 Nginx 里：
```nginx
proxy_pass http://api:8000;  # 直接用服务名 "api"
```

### Q3: 如何查看容器内 Nginx 的配置？
```bash
docker compose -f /data/app/backend/docker-compose.yml exec frontend cat /etc/nginx/conf.d/default.conf
```

### Q4: 前端如何调用后端 API？
**不需要写完整 URL！** 因为 Nginx 反向代理：

```javascript
// 前端代码（错误示范）
fetch('http://124.222.169.60:8088/api/user/login')  // ❌ 跨域！

// 正确写法
fetch('/api/user/login')  // ✓ 同源，Nginx 自动转发
```

### Q5: 本地开发时怎么办？
本地开发有两种方式：

#### 方式1：Docker Compose（和生产一致）
```bash
docker compose up -d
# 访问 http://localhost:8090
```

#### 方式2：前端开发服务器（热更新）
```bash
cd frontend
npm run dev  # 默认 http://localhost:5173

# vite.config.ts 配置代理
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8088',  # 直连后端容器
        changeOrigin: true,
      }
    }
  }
})
```

---

## 七、部署检查清单

部署到新服务器时，按顺序检查：

### 7.1 检查端口占用
```bash
# 检查 80 端口
sudo lsof -i :80

# 检查 8090 端口
sudo lsof -i :8090
```

### 7.2 启动 Docker 服务
```bash
cd /data/app/backend
docker compose up -d

# 查看状态
docker compose ps
```

### 7.3 配置宿主机 Nginx
```bash
# 创建配置
sudo nano /etc/nginx/sites-available/natapp

# 启用并重载
sudo ln -s /etc/nginx/sites-available/natapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7.4 测试各层连通性
```bash
# 测试容器内 Nginx
curl http://localhost:8090/

# 测试宿主机 Nginx
curl http://localhost:80/

# 测试 API
curl http://localhost:80/api/health

# 测试外网访问（从本机）
curl http://124.222.169.60/
```

### 7.5 配置云服务器安全组
- 开放端口：80（HTTP）、443（HTTPS）
- 可选：8090（调试用，生产可关闭）

### 7.6 配置微信开发平台
- URL：`http://124.222.169.60/api/user/wechat/webhook`
- Token：`cz149`（对应环境变量 `WECHAT_TOKEN`）

---

## 八、总结

### 核心理解
1. **Nginx 是服务器软件**，不是前端，职责是托管文件 + 转发请求
2. **Docker 端口映射**：`宿主机端口:容器端口`，外部访问宿主机端口
3. **双层 Nginx**：宿主机做入口网关，容器做应用层代理

### 架构优势
- ✅ 容器化部署，易于迁移
- ✅ 配置版本管理
- ✅ 前后端同源，无跨域问题
- ✅ 支持微信 80 端口要求

### 关键命令速查
```bash
# 查看容器状态
docker compose ps

# 查看容器日志
docker compose logs -f frontend

# 重启服务
docker compose restart frontend

# 测试 Nginx 配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

---

**文档版本**: v1.0  
**最后更新**: 2026-08-18  
**作者**: Claude Code
