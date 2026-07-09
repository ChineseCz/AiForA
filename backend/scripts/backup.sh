#!/usr/bin/env bash
# Postgres 备份（Phase 5）。对运行中的 compose Postgres 容器做 pg_dump，输出到 backend/backups/。
#
# 用法：  bash scripts/backup.sh
# 定时（Windows 任务计划 / cron）：每日调用本脚本即可。保留最近 14 份。
#
# 恢复：  gunzip -c backups/natapp_YYYYmmdd_HHMMSS.sql.gz | \
#           docker exec -i backend-postgres-1 psql -U natapp -d natapp
set -euo pipefail

CONTAINER="${PG_CONTAINER:-backend-postgres-1}"
DB_USER="${POSTGRES_USER:-natapp}"
DB_NAME="${POSTGRES_DB:-natapp}"
OUT_DIR="$(dirname "$0")/../backups"
KEEP=14

mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/natapp_${STAMP}.sql.gz"

echo "→ 备份 $DB_NAME 到 $OUT"
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" | gzip > "$OUT"
echo "✅ 完成：$(du -h "$OUT" | cut -f1)"

# 仅保留最近 KEEP 份
ls -1t "$OUT_DIR"/natapp_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "→ 现存备份：$(ls -1 "$OUT_DIR"/natapp_*.sql.gz 2>/dev/null | wc -l) 份"
