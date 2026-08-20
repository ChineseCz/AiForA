# Bug修复记录：邮箱登录管理员显示「微信用户」异常

**Phase**：Phase 14-15  
**日期**：2026-08-18  
**分支**：`fix/admin-token-sty` → `dev`  
**提交**：`e244f21`

---

## 一、问题现象

用户使用邮箱 `1123093545@qq.com` 登录后，前端右上角显示兜底文本「微信用户」，而非用户昵称「QQ橙子🍊」。

---

## 二、调试过程回顾

### 2.1 初期方向错误：在云服务器调试

**错误假设**：以为是云服务器部署配置问题（Nginx 反向代理、Docker 端口映射、防火墙规则等）。

**浪费的时间**：
- 检查宿主机 Nginx 80 端口转发到 Docker frontend 8090
- 检查 frontend 容器内 Nginx `/api` 反向代理到 api 容器 8000
- 分析《Nginx与Docker端口映射详解.md》文档，验证双层 Nginx 架构
- 测试云服务器 `/api/user/me` 返回 404

**问题**：
1. 云服务器调试反馈周期长（改代码 → 上传 → 重启容器 → 测试）
2. 网络层复杂（公网IP → 宿主机Nginx → Docker网络 → 容器Nginx → FastAPI），干扰问题定位
3. **实际根因是代码逻辑 bug，与部署环境无关**

---

### 2.2 转向本地 Docker 环境

切换到本地笔记本 `localhost:8090` 调试后，问题复现：
- 邮箱登录成功，返回 `access_token` 和 `admin_token`
- 前端调用 `/api/user/me` 返回 **404 Not Found**
- 右上角显示兜底文本「微信用户」

**关键发现**：
- 容器日志显示：`GET /api/user/me HTTP/1.1" 404 Not Found`
- 但源码 `user_auth.py` 明确定义了 `@router.get("/me")` 端点

---

### 2.3 Docker 镜像缓存问题

**假设**：容器运行的是旧代码镜像，未包含 `/me` 端点。

**验证**：
```bash
# 重建 API 容器
docker compose up -d --build api
```

重建后再次测试，`/me` 端点存在但返回：
```json
{"error": "用户不存在"}
```

**进展**：从 404（路由不存在）变成了 200 + 业务错误（用户查询失败）。

---

### 2.4 Token 解码与根因定位

**分析工具**：创建 `decode_token.py` 脚本解码 JWT payload。

**发现问题**：
```json
// 前端使用的 admin_token payload
{
  "sub": "1123093545@qq.com",
  "typ": "admin",
  "iat": 1787040958,
  "exp": 1787084158
  // ❌ 缺少 sty 字段
}
```

**对比正常 access_token**：
```json
{
  "sub": "1123093545@qq.com",
  "typ": "visitor",
  "sty": "email",  // ✅ 有 sty 字段
  "iat": ...,
  "exp": ...
}
```

**追踪 `/me` 端点逻辑**（`user_auth.py:112-139`）：
```python
@router.get("/me")
async def me(payload: dict = Depends(require_visitor_payload), session: AsyncSession = Depends(db_session)):
    sub = payload["sub"]
    sty = payload.get("sty", "phone")  # ⚠️ 无 sty 时降级为 "phone"

    if sty == "wechat":
        user = await users_repo.get_by_openid(session, sub)
    elif sty == "email":
        user = await users_repo.get_by_email(session, sub)  # ✅ 应该走这里
    else:
        user = await users_repo.get_by_phone(session, sub)  # ❌ 实际走了这里
```

**根因确认**：
- `admin_token` 无 `sty` 字段 → 降级为 `sty="phone"`
- 用邮箱地址 `1123093545@qq.com` 调用 `get_by_phone()` → 查询失败 → 返回 404

---

## 三、修复方案

### 3.1 代码修改

**文件**：`backend/app/api/routers/public/user_auth.py`

**位置1**：`email/register` 端点（第 203 行）
```python
# 修复前
resp["admin_token"] = create_access_token(email, typ="admin", expire_minutes=settings.jwt_expire_minutes)

# 修复后
resp["admin_token"] = create_access_token(email, typ="admin", expire_minutes=settings.jwt_expire_minutes, sty="email")
```

**位置2**：`email/login` 端点（第 223 行）
```python
# 同上修改
```

### 3.2 测试验证

```bash
# 1. 重启容器
docker compose restart api

# 2. 浏览器清除旧 token
localStorage.clear()

# 3. 重新邮箱登录
# 4. 解码新 admin_token 验证 sty 字段存在
# 5. 确认 /api/user/me 返回正确用户信息
# 6. 确认前端右上角显示昵称而非兜底文本
```

---

## 四、深层次问题：双 Token 设计缺陷

### 4.1 当前设计

邮箱登录返回两个 token：
```json
{
  "access_token": "visitor token (sty=email)",
  "admin_token": "admin token (sty=email)",  // 管理员才有
  "email": "1123093545@qq.com"
}
```

**前端逻辑**（`Login.tsx:69-70`）：
```typescript
login(d.access_token);           // 先存 visitor token
if (d.admin_token) auth.login(d.admin_token);  // 管理员用 admin token 覆盖
```

**问题**：
1. **语义混乱**：访客接口（`/api/user/me`、`/nickname`）用 `require_visitor` 守卫，却允许 `typ=admin` 通过（`deps.py:82`）
2. **前端困惑**：不知道该用哪个 token，只能"先存再覆盖"
3. **维护成本**：两套 token 生成逻辑容易漏加参数（本次 bug）

### 4.2 合理设计方向

**建议**：只返回一个 token，用 `typ` 字段区分角色。

**守卫重构**：
- `require_visitor`：只允许 `typ=visitor`
- `require_admin`：只允许 `typ=admin`  
- `require_auth`：两者都行（用于 `/me` 等通用接口）

**工作量**：
- 后端：重构 `deps.py` 守卫函数 + 修改 `email/register` 和 `email/login` 返回值
- 前端：删除双 token 保存逻辑，简化为单 token 存储
- 兼容性：已发放的旧 token 需要过期处理或迁移逻辑

**优先级**：中（非紧急，但影响代码可维护性）

---

## 五、经验教训

### 5.1 调试策略

❌ **错误方向**：
- 在生产/类生产环境（云服务器）调试代码逻辑问题
- 过度关注基础设施层（Nginx、Docker、网络）而忽略业务逻辑

✅ **正确方向**：
1. **先本地复现**：本地 Docker 环境反馈周期短，排除网络干扰
2. **分层排查**：
   - 容器是否运行最新代码？（Docker 镜像缓存）
   - 路由是否注册？（404 vs 业务错误）
   - 数据是否正确？（Token payload 解码）
3. **工具辅助**：写 `decode_token.py` 快速查看 JWT 内容，避免手动 base64 解码

### 5.2 Docker 开发陷阱

**问题**：修改代码后容器仍运行旧逻辑。

**原因**：
- `docker compose up -d` 不会自动重建镜像
- 容器内代码来自镜像构建时的 `COPY`，不是挂载卷

**解决**：
```bash
# 方案1：重建指定服务
docker compose up -d --build api

# 方案2：强制重建所有服务
docker compose up -d --build --force-recreate

# 方案3：开发时使用卷挂载（需修改 docker-compose.yml）
volumes:
  - ./app:/app  # 代码改动实时生效，需配合热重载
```

### 5.3 JWT 调试技巧

**常见错误**：Token 有效但业务逻辑失败，容易误判为鉴权问题。

**调试步骤**：
1. 解码 payload 查看字段完整性（`decode_token.py`）
2. 对比预期字段（如本次缺失 `sty`）
3. 追踪守卫/端点如何使用这些字段

**工具推荐**：
- 在线：jwt.io
- 本地：自写脚本（避免敏感 token 上传）

---

## 六、后续优化建议

1. **单元测试覆盖**：
   - 测试邮箱登录返回的 `admin_token` 包含 `sty` 字段
   - 测试 `/api/user/me` 对三种 `sty`（email/phone/wechat）的路由逻辑

2. **类型安全**：
   - 定义 `TokenPayload` Pydantic 模型，强制 `sty` 必填
   - 避免字典 `.get("sty", "phone")` 这种隐式降级

3. **前端错误提示**：
   - `/me` 返回 404 时不应静默降级为兜底文本
   - 应提示"用户信息获取失败，请重新登录"并清除 token

4. **文档同步**：
   - `doc/Phase9访客账号系统交付报告.md` 需补充双 token 设计缺陷说明
   - `doc/访客账号体系后续需求PRD.md` 增加"单 token 重构"任务项

---

**修复人**：Claude Code  
**审核人**：（待填写）  
**部署状态**：已合并到 dev 分支，待部署验证
