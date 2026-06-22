#!/bin/bash
# 知曜后端 · 每日数据库异地备份（推阿里云 OSS） — 上线审计 P0-9
# ---------------------------------------------------------------------------
# 解决：生产此前唯一备份是 deploy.sh 部署时的本机 pg_dump（同盘 /opt/backup、非定时、
# 无异地、无 PITR），ECS 实例释放/磁盘损坏即全量用户数据不可恢复。
# 本脚本由 cron 每日触发：pg_dump → gzip → ossutil 推 OSS 异地，并按保留期清理。
#
# 前置（在 ECS 上一次性配置）：
#   1. 装 ossutil 并 `ossutil config`（AccessKey 用仅授 OSS 读写的子账号，最小权限）
#   2. 建 OSS bucket，控制台开「版本控制」+「跨区域复制」+「生命周期规则」自动过期
#   3. crontab -e 加：
#        5 3 * * *  OSS_BUCKET=oss://zhiyao-backup /opt/zhiyao-backend/deploy/backup-to-oss.sh \
#                     >> /var/log/zhiyao-backup.log 2>&1
#
# 恢复演练（至少每季度一次，验证备份真能 restore）：
#   ossutil cp oss://zhiyao-backup/pg/zhiyao_<TS>.sql.gz ./restore.sql.gz
#   gunzip -c restore.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres \
#     psql -U zhiyao -d zhiyao_restore_check     # 先恢复到临时库核验，绝不直接覆盖生产
# ---------------------------------------------------------------------------
set -euo pipefail

COMPOSE="docker compose -f $(cd "$(dirname "$0")/.." && pwd)/docker-compose.prod.yml"
OSS_BUCKET="${OSS_BUCKET:?需设置 OSS_BUCKET，如 oss://zhiyao-backup}"
OSS_PREFIX="${OSS_PREFIX:-pg}"
RETAIN_LOCAL="${RETAIN_LOCAL:-3}"          # 本机临时副本保留份数（异地真副本在 OSS）
PG_USER="${POSTGRES_USER:-zhiyao}"
PG_DB="${POSTGRES_DB:-zhiyao}"
TMP_DIR="${TMP_DIR:-/opt/backup}"

mkdir -p "$TMP_DIR"
TS="$(date +%F-%H%M%S)"
FILE="$TMP_DIR/zhiyao_${TS}.sql.gz"

echo "[$(date -Is)] dump $PG_DB ..."
$COMPOSE exec -T postgres pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$FILE"

# 失败保护：dump 异常小（pg_dump 静默失败/空库）时不上传、不清历史，显式报错
SIZE=$(stat -c%s "$FILE" 2>/dev/null || echo 0)
if [ "$SIZE" -lt 1024 ]; then
  echo "ERROR: dump 仅 $SIZE 字节，疑似失败 → 不上传、不清历史" >&2
  exit 1
fi

echo "[$(date -Is)] upload → $OSS_BUCKET/$OSS_PREFIX/ ($SIZE bytes)"
ossutil cp "$FILE" "$OSS_BUCKET/$OSS_PREFIX/" --force

# 本机临时文件只留最近 N 份
ls -1t "$TMP_DIR"/zhiyao_*.sql.gz 2>/dev/null | tail -n +"$((RETAIN_LOCAL + 1))" | xargs -r rm -f

echo "[$(date -Is)] done. OSS 端保留策略请用 bucket 生命周期规则（按天自动过期 + 版本控制）。"
