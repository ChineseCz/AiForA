# 雪球大V看板 & A股选股系统 —— Phase 9 访客账号系统交付报告

| 项 | 内容 |
|---|---|
| 文档类型 | 阶段交付报告 |
| 周期 | 2026-07-12 |
| 状态 | 代码已提交（commit `369e098`，分支 `feature/user-accounts`，未 push、未合并 master） |
| 范围 | 手机号+验证码 / 微信公众号扫码+验证码 / 邮箱注册+账密 三种访客登录方式；管理后台"访客登录"总开关；邮箱验证码真实 SMTP 发送 |
| 关联代码 | `backend/app/{models/user,repositories/users,api/routers/public/user_auth,services/external/{email,sms,wechat},api/deps,core/security}.py`、`frontend/src/{pages/VisitorLogin,visitorAuth,App,api/{client,hooks,types}}.tsx` |

---

## 1. 背景

此前系统的"用户模型"只有匿名只读 + 管理员两级（见 `backend/README.md`）。本阶段目标是加一层**访客账号**：不影响默认的匿名访问体验，但支持后台一键开启"必须登录才能看"的模式，并让访客能用手机号、微信或邮箱三种常见方式登录，登录后可设置昵称、在多端间保持登录态（JWT 30天）。

## 2. 变更概览

| # | 主题 | 说明 | 状态 |
|---|---|---|---|
| 1 | `users` 表 + `auth_settings` 表 | 迁移 0006；`auth_settings` 存"是否要求登录"开关，单行表 | 已提交 |
| 2 | 手机号+验证码登录 | `/api/user/send-code` + `/api/user/login`；验证码走 Redis，短信发送当前是 **Mock**（只打日志，短信资质未办下来） | 已提交 |
| 3 | 微信公众号登录 | 两条路径：①扫码关注（`wechat/qrcode` + webhook `subscribe`/`SCAN` 事件）②已关注用户发文本消息/点菜单拿验证码（`wechat/webhook` 文本事件 + `wechat/code-login`） | 已提交 |
| 4 | 邮箱注册 + 账密登录 | `/api/user/email/{send-code,register,login}`；真实 SMTP 发送，`SMTP_HOST` 未配时退化为 Mock | 已提交 |
| 5 | 昵称设置 | `/api/user/nickname`，微信/邮箱账号可自起昵称（手机号账号本身就是标识，不需要） | 已提交 |
| 6 | 访客登录总开关 | 管理后台 Switch，`require_login_enabled`；关闭时任何人可匿名浏览，开启时只读接口需 visitor 或 admin token | 已提交 |
| 7 | JWT 加 `typ` 字段 | 区分 `admin`/`visitor` token，`require_admin`/`require_visitor`/`require_visitor_or_anonymous` 三个依赖分别校验 | 已提交 |
| 8 | 邮件模板美化 | 从纯文本升级成品牌色 HTML 卡片（含纯文本降级版本） | 已提交 |

---

## 3. 详细变更

### 3.1 数据模型

`users` 表（迁移 0006 建表 + 0007/0008 补列）：

```
id, phone(unique), openid(unique), email(unique), password_hash, nickname, created_at
```

三种登录方式对应三个可空的唯一字段，**互相独立**——同一个人用手机号注册一次、用邮箱注册一次，会产生两条 `users` 记录，彼此不关联（见第 5 节待优化）。

`auth_settings` 表只有一行：`require_login_enabled` + `updated_at`，读接口带 30s 短 TTL Redis 缓存（`api/deps.py::_is_login_required`），不走 dataver（这个开关的更新频率和语义都和数据同步无关）。

### 3.2 鉴权依赖分层

`api/deps.py` 新增三个依赖，各自校验 JWT 的 `typ` 字段：

- `require_admin`：`typ=admin`（兼容早期无 `typ` 字段的旧 token，视为 admin）
- `require_visitor`：`typ=visitor`，访客专用接口（`/me`、`/nickname`）用
- `require_visitor_or_anonymous`：开关关闭直接放行；开关开启则要求 `typ` 是 `admin` 或 `visitor` 之一

`main.py` 把除 `health` 外的全部公开只读路由都挂了 `require_visitor_or_anonymous` 依赖，`user_auth` 路由本身不挂任何鉴权（登录动作必须开放）。

### 3.3 邮箱服务（真实 SMTP）

`services/external/email.py`：`smtp_host` 未配置时走 Mock（只打日志）；配置后用 `smtplib` 同步发送，走 `run_in_threadpool` 包裹不阻塞事件循环（与选股/K线同一模式，见 CLAUDE.md"异步/同步分界"）。已用 QQ邮箱 SMTP 真实验证过（`smtp.qq.com:465`，SSL，授权码登录），HTML 模板含品牌色条 + 大号验证码卡片 + 页脚免责说明。

### 3.4 短信/微信服务

- `services/external/sms.py`：纯 Mock，等短信服务资质办下来后替换函数体即可，调用方无需改动。
- `services/external/wechat.py`：真实接口（access_token/二维码 ticket/菜单创建/签名校验/XML事件解析），`create_wechat_menu` 挂在管理后台一键创建自定义菜单（"获取验证码"按钮）。

### 3.5 前端

- `VisitorLogin.tsx`：三 Tab（微信/邮箱登录/邮箱注册），短信 Tab 因资质未办暂时移除（后端接口保留）。
- `visitorAuth.tsx`：模块级 Context（不是模块级单例，因为不需要跨路由脱离 React 树存活，登录态本身可以放 Context）。
- `App.tsx`：`RequireVisitorOrAnon` 包裹全部只读路由；`VisitorMenu` 在 Header 展示当前账号 + 改昵称 + 退出。
- `client.ts`：管理员 token 和访客 token 分开存 localStorage，请求时管理员优先；401 时只清失效的那一个，不误伤另一个。

---

## 4. 验证记录

- 容器已重建（`docker compose up -d --build api`），api/worker/beat 均正常启动。
- `POST /api/user/email/send-code` 用真实邮箱（QQ邮箱）验证通过，返回 200，日志确认走的是真实 SMTP 分支（无 `[MOCK EMAIL]` 日志）。
- **未验证**：`alembic upgrade head` 是否已在当前数据库执行（0006/0007/0008 三个迁移）；微信扫码/文本验证码登录完整链路（依赖真实公众号后台配置）；前端三个 Tab 的人工浏览器走查；访客登录开关开启后的整站行为。

---

## 5. 待优化方向（未开工，供下次会话参考）

### 5.1 选股接口并发瓶颈

选股逻辑是同步代码 + `run_in_threadpool`（CLAUDE.md"异步/同步分界"），受两个限制：

- 同步 DB 连接池只有 `sync_db_pool_size=4 + sync_db_max_overflow=4`，超过 8 个并发选股请求会排队，超过 `db_statement_timeout_ms`(15s) 会超时。
- 选股内部大量 Python 循环计算（MA/MACD/KDJ），并发线程间有 GIL 竞争。

当前用户规模下（多数访问是只读浏览，同时选股的人很少）不是问题，且已有预计算快路径（`stock_indicator` 表）分担实时计算压力。真出现排队再考虑：调大连接池，或把选股改成"提交任务→轮询结果"的异步模式。

### 5.2 三种登录方式账号不互通

同一个人分别用手机号、邮箱、微信登录会产生三条独立的 `users` 记录，昵称/历史状态不互通。如果产品上需要"一个人只有一个账号"，需要设计账号绑定/合并流程（比如登录后在设置里"绑定手机号/邮箱"，写入同一条 `users` 记录）。

### 5.3 邮箱账号找回密码缺失

`email/register` 时 `email` 唯一约束会挡住重复注册；如果用户忘记密码，目前**没有重置入口**，只能联系管理员手动改库。需要补一个"忘记密码"流程（邮箱验证码校验后允许改 `password_hash`，复用现有的验证码发送逻辑）。

### 5.4 短信服务尚未真实接入

`services/external/sms.py` 是 Mock，等短信服务资质（阿里云/腾讯云）办下来后替换函数体，`VisitorLogin.tsx` 里的手机号 Tab 也需要加回来（代码注释里留了说明，未删除，接口一直保留）。

### 5.5 验证码发送限流粒度

`rate_limit_email_send = "1/minute"` 是按 IP 限流（slowapi），配合 Redis 按邮箱维度限流（`_email_resend_key`）。同一 IP 换不同邮箱刷验证码理论上仍可绕过按邮箱的节流（IP 限流本身会挡住大部分场景，但没有验证码图片/滑块防护批量注册脚本）。当前风险可接受（内部小项目，不是公开互联网服务），如果开放范围扩大需要重新评估。

---

## 6. 部署清单（下次会话开工前）

1. `docker compose up -d --build`（api/worker/beat/frontend 四个都要重建，本次只重建了 api）
2. `alembic upgrade head`（0006/0007/0008 三个迁移未确认执行）
3. `.env` 补齐 `SMTP_*`（已完成，QQ邮箱）与 `WECHAT_*`（已有，需确认公众号后台"服务器配置"里的 URL/Token 与 `.env` 一致）
4. 浏览器人工走查：`/login` 三个 Tab、开启访客登录开关后整站行为、修改昵称、退出登录
