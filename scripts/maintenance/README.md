# 维护脚本

本目录包含项目日常维护所需的脚本。

## 脚本列表

### update_xueqiu_login.bat

**用途**：更新雪球登录态（用于服务器浏览器 Worker）

**使用场景**：当雪球采集任务显示成功但实际抓取 0 条帖子时，说明登录态已过期，需要重新生成。

**使用方法**：
1. 双击运行 `scripts/maintenance/update_xueqiu_login.bat`
2. Edge 浏览器会自动打开雪球网站
3. 如果已登录，脚本会自动检测；如果未登录，请手动登录
4. 登录完成后回到命令行窗口按回车
5. 脚本会自动上传新的登录态到服务器并重启 browser-worker

**原理**：
- 读取本地 `backend/data/edge_profile/` 中的 Edge 登录态
- 导出为 Playwright storage state 格式 (`xueqiu-state.json`)
- 上传到服务器 `/data/app/backend/data/`
- 重启 Docker 容器 `browser-worker` 使新登录态生效

**手动执行命令**（如果不想用批处理脚本）：
```bash
# 1. 导出登录态
cd backend
python export_xueqiu_state.py

# 2. 上传到服务器
scp data/xueqiu-state.json ubuntu@124.222.169.60:/data/app/backend/data/

# 3. 重启容器
ssh ubuntu@124.222.169.60 "cd /data/app/backend && docker compose restart browser-worker"
```

**相关文档**：
- `doc/服务器浏览器Worker部署方案.md` - 详细的部署方案说明
- `backend/export_xueqiu_state.py` - 登录态导出脚本

## 添加新脚本

如果需要添加新的维护脚本：
1. 将脚本放在 `scripts/maintenance/` 目录下
2. 在本 README 中添加说明文档
3. 注意脚本路径使用相对路径，方便在不同机器上运行
