# Phase 14-15：管理员系统改进交付报告

**Phase**：14-15  
**分支**：`fix/admin-improvements`  
**日期**：2026-08-05  
**提交范围**：`2e79dca` ~ `b96212f`

---

## 背景

原有管理员鉴权机制存在两个问题：

1. **IP 锁定字段**（`admin_allowed_ip`）：定义在 config 但从未实际使用，是无效的死配置。
2. **邮箱硬编码**（`admin_email`）：管理员身份通过 config 文件中的邮箱字段判断，无法在运行时调整，也无法支持多管理员。

同时，原先管理后台有独立的用户名/密码登录页（`/admin/login`），账号体系与访客账号完全分离，访客账号持有者即使被指定为管理员也无法通过统一入口进入后台。

---

## 变更内容

### 1. 数据库层：新增 `users.is_admin` 字段

**新增 Alembic migration `0016_user_is_admin`**：

```sql
ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT false;
UPDATE users SET is_admin = TRUE WHERE email = '1123093545@qq.com';
```

管理员身份改为数据库行级标记，可随时通过 SQL 授予或撤销，支持多管理员。

### 2. 后端：移除 config 中的死配置

`core/config.py` 删除 `admin_allowed_ip` 和 `admin_email` 两个字段。前者从未被任何路由或中间件读取；后者被 `users.is_admin` 取代。

### 3. 后端：邮箱登录携带 admin_token

`user_auth.py` 的 `email_login` 和 `email_register` 接口，在用户 `is_admin=True` 时额外返回 `admin_token`（`typ=admin`）：

```python
resp: dict = {"access_token": token, ...}
if user.get("is_admin"):
    resp["admin_token"] = create_access_token(email, typ="admin", ...)
return resp
```

### 4. 后端：修复 admin token 触发 401 的问题（关键 bug）

**问题**：`deps.py` 的 `require_visitor` 和 `require_visitor_payload` 只接受 `typ=visitor`，而前端 `client.ts` 的请求拦截器优先使用 admin token（`getToken() || getVisitorToken()`）。管理员登录后，页面初始化时 `VisitorMenu` 调用 `/api/user/me`（使用 `require_visitor_payload`），admin token 被拒绝返回 401，触发前端拦截器清除 admin token，导致管理后台 tab 闪一下就消失。

**修复**：两个 dep 改为接受 `("visitor", "admin")`，admin 用自己的 token 访问访客接口不再被拒：

```python
# before
payload.get("typ") != "visitor"
# after
payload.get("typ") not in ("visitor", "admin")
```

### 5. 前端：统一登录入口

- `types.ts`：`VisitorLoginResp` 新增可选字段 `admin_token?: string`
- `VisitorLogin.tsx`：邮箱登录成功后若响应含 `admin_token`，同时调用 `auth.login(d.admin_token)` 存入 localStorage
- `Admin.tsx`：移除独立的 `LoginForm` 组件和 `login` prop（原来 `/admin/login` 路由渲染的独立登录表单）
- `App.tsx`：移除 `/admin/login` 路由；`RequireAdmin` 守卫的未登录重定向改为 `/login`

---

## 登录流程（改后）

```
用户在 /login 页用邮箱登录
  └─ 后端：验证密码 → 返回 access_token（typ=visitor）
       └─ is_admin=true → 同时返回 admin_token（typ=admin）
前端：
  ├─ login(access_token)  → localStorage natapp_visitor_token
  └─ auth.login(admin_token) → localStorage natapp_admin_token（若有）

页面加载：
  ├─ useAuth().loggedIn = true → 导航栏出现「管理后台」tab
  └─ 所有 API 请求附带 admin_token → require_visitor/require_admin 均通过
```

---

## 影响范围

| 组件 | 变更类型 |
|---|---|
| `alembic/versions/0016_user_is_admin.py` | 新增（需 `alembic upgrade head`） |
| `app/core/config.py` | 删除两个死字段 |
| `app/models/user.py` | 新增 `is_admin` ORM 字段 |
| `app/repositories/users.py` | `get_by_email` SELECT 补全 `is_admin` |
| `app/api/routers/public/user_auth.py` | 登录/注册返回 `admin_token` |
| `app/api/deps.py` | `require_visitor*` 接受 admin token |
| `frontend/src/api/types.ts` | 响应类型补字段 |
| `frontend/src/pages/VisitorLogin.tsx` | 存 admin token |
| `frontend/src/pages/Admin.tsx` | 删除独立登录表单 |
| `frontend/src/App.tsx` | 路由调整 |

**不影响**：访客登录流程、选股、行情、Celery 任务、数据库其他表。

---

## 部署步骤

```bash
# 1. 重建 API 镜像（代码已入镜像）
docker compose build --no-cache api

# 2. 升级数据库
docker compose up -d api
docker compose exec api alembic upgrade head

# 3. 按需重建前端
docker compose build --no-cache frontend
docker compose up -d frontend api
```

---

## 已验证

- [x] migration 0016 成功执行（0015 → 0016）
- [x] `1123093545@qq.com` 的 `is_admin = true` 已写入 DB
- [x] 邮箱登录 API（port 8088）返回 `access_token` + `admin_token`
- [x] 前端登录后管理后台 tab 持续显示，不再闪烁消失
- [x] FeibiWidget 正常显示
