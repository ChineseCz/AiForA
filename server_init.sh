#!/bin/bash
# 云服务器初始化脚本 - 在服务器上执行（ubuntu 用户）
set -e

echo "====== 云服务器部署初始化 ======"
echo ""

# 1. 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，正在安装..."
    curl -fsSL https://get.docker.com | sh
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ubuntu
    echo "✅ Docker 安装完成，需要重新登录以生效"
    echo "请执行: exit 后重新 ssh 登录，然后再运行本脚本"
    exit 0
else
    echo "✅ Docker 已安装"
fi

# 2. 检查代码目录
if [ ! -d "/data/app" ]; then
    echo "❌ 代码目录 /data/app 不存在"
    echo "请先克隆代码："
    echo "  git clone <你的仓库URL> /data/app"
    exit 1
fi

cd /data/app/backend
echo "✅ 代码目录存在"

# 3. 检查 .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env 不存在，正在创建..."
    cat > .env << 'EOF'
# ===== 数据库 =====
POSTGRES_USER=natapp
POSTGRES_PASSWORD=natappHAODE1
POSTGRES_DB=natapp
DATABASE_URL=postgresql+asyncpg://natapp:natappHAODE1@pgbouncer:5432/natapp

# ===== Redis =====
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# ===== 安全 =====
JWT_SECRET=0ad8a5c5a2904185b3f080aac4bff88d3fe904801e6a0cd90192f91f78da3876

# ===== AI中转站 =====
RELAY_API_KEY=sk-8i6Jg8VH4aV57zOqzTAJRvqowjqdEIEfeOFMdedTealSyqrh
RELAY_API_URL=https://n.tokeness.io/v1
RELAY_MODEL=gpt-5.6-terra
VISION_MODEL=gpt-image-2
RELAY_API_IMAGE_KEY=sk-vV036QQHt0JuQVQbcoykrHeLc4Eqp9iUZ1z8dLD4MRkrkSNb

# ===== 浏览器 Worker（服务器用 Chromium） =====
BROWSER_CHANNEL=
HEADLESS=true
DATA_DIR=/data/app/backend/data

# ===== 管理员引导 =====
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin12345

# ===== 其他 =====
CORS_ORIGINS=["http://124.222.169.60"]
MAX_PAGES=10
FETCH_FULL_TEXT=true
REQUEST_DELAY=1.5
EOF
    echo "✅ .env 创建完成"
else
    echo "✅ .env 已存在"
fi

# 4. 启动 Docker 栈
echo ""
echo "====== 启动 Docker 栈 ======"
docker compose up -d --build

# 等待服务就绪
echo "等待服务启动..."
sleep 10

# 5. 执行 migration
echo ""
echo "====== 执行数据库 migration ======"
docker compose exec -T api alembic upgrade head

# 6. 检查备份文件
if [ ! -f "/data/natapp_backup.sql.gz" ]; then
    echo "⚠️  备份文件 /data/natapp_backup.sql.gz 不存在"
    echo "请先上传备份文件，然后手动导入："
    echo "  gunzip /data/natapp_backup.sql.gz"
    echo "  docker compose exec -T postgres psql -U natapp natapp < /data/natapp_backup.sql"
    exit 0
fi

# 7. 导入数据
echo ""
echo "====== 导入数据库 ======"
if [ -f "/data/natapp_backup.sql" ]; then
    echo "使用已解压的 SQL 文件..."
    docker compose exec -T postgres psql -U natapp natapp < /data/natapp_backup.sql
else
    echo "解压并导入..."
    gunzip /data/natapp_backup.sql.gz
    docker compose exec -T postgres psql -U natapp natapp < /data/natapp_backup.sql
fi

# 8. 验证数据
echo ""
echo "====== 验证数据 ======"
POSTS_COUNT=$(docker compose exec -T postgres psql -U natapp natapp -t -c "SELECT COUNT(*) FROM posts;" | xargs)
STOCK_COUNT=$(docker compose exec -T postgres psql -U natapp natapp -t -c "SELECT COUNT(*) FROM stock_daily;" | xargs)

echo "✅ posts 表: $POSTS_COUNT 条"
echo "✅ stock_daily 表: $STOCK_COUNT 条"

# 9. 查看服务状态
echo ""
echo "====== 服务状态 ======"
docker compose ps

echo ""
echo "====== 部署完成 ======"
echo "访问: http://124.222.169.60:8090"
echo "API: http://124.222.169.60:8088/api/health"
echo ""
echo "下一步："
echo "1. 在本机开启 SSH 隧道:"
echo "   ssh -L 6380:127.0.0.1:6380 root@124.222.169.60"
echo "2. 在本机启动 browser worker:"
echo "   cd backend"
echo "   .\.venv\Scripts\python -m celery -A app.workers.celery_app worker -Q browser --pool=solo"
