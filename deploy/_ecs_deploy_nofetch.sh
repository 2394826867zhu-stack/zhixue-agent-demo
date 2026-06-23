#!/bin/bash
# 一次性部署脚本（绕开 github fetch，代码已 git pull 到 b6b33a1）
# 安全序列：备份 → 构建 → 迁移(一次性容器) → 启动 → 健康闸 → 失败回滚到旧 commit
set -euo pipefail
cd /opt/zhiyao-backend
COMPOSE="docker compose -f docker-compose.prod.yml"
BACKUP_DIR=/opt/backup
PREV=0cd1041                                   # 运行中旧容器对应 commit（回滚点）
HEALTH_URL="http://127.0.0.1:8000/health/ready"

echo "==> HEAD=$(git rev-parse --short HEAD) PREV=$PREV  $(date)"

echo "==> [1/5] 备份数据库"
mkdir -p "$BACKUP_DIR"; TS=$(date +%F-%H%M%S)
if $COMPOSE ps postgres | grep -q healthy; then
  $COMPOSE exec -T postgres pg_dump -U zhiyao zhiyao | gzip > "$BACKUP_DIR/zhiyao_$TS.sql.gz"
  echo "    备份: $BACKUP_DIR/zhiyao_$TS.sql.gz ($(du -h "$BACKUP_DIR/zhiyao_$TS.sql.gz"|cut -f1))"
fi

echo "==> [2/5] 构建镜像（含新依赖 prometheus/json-logger + 新 compose 服务 celery_beat）"
$COMPOSE build

echo "==> [3/5] 迁移（一次性容器，失败即止，旧容器仍在跑）"
$COMPOSE run --rm backend alembic upgrade head

echo "==> [4/5] 启动新容器（--remove-orphans，带起 celery_beat）"
$COMPOSE up -d --remove-orphans

echo "==> [5/5] 健康闸（最多 120s 探 /health/ready）"
ok=0
for i in $(seq 1 24); do
  if curl -sf -m3 "$HEALTH_URL" 2>/dev/null | grep -q '"status":"ready"'; then ok=1; break; fi
  sleep 5
done

if [ "$ok" = 1 ]; then
  echo "✅ 部署成功 health=ready"
  $COMPOSE ps
else
  echo "❌ 健康闸 120s 未过 → 回滚到 $PREV"
  git reset --hard "$PREV"
  $COMPOSE up -d --build --remove-orphans
  echo "已回滚到旧版。后端日志:"; $COMPOSE logs --tail=50 backend
  exit 1
fi
echo "==> DONE $(date)"
