#!/bin/bash
# 知曜后端 · 生产部署 / 更新脚本（阿里云 ECS 单机）
# ---------------------------------------------------------------------------
# 用法：在 ECS 上 `bash /opt/zhiyao-backend/deploy/deploy.sh`
# 对标 RELEASE_AND_DEPLOYMENT_SOP §11.A：
#   记录回滚点 → git 同步 → pg_dump 备份 → 构建启动 → 健康闸 → 失败自动回滚
# 不可变制品（推 ACR）属 M1 后续；当前为现场 --build。
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(cd "$(dirname "$0")/.." && pwd)"   # 仓库根
COMPOSE="docker compose -f docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-/opt/backup}"
HEALTH_URL="http://127.0.0.1:8000/health/ready"   # P1-6 · 探真就绪（DB+Redis），非假 ok
BRANCH="${DEPLOY_BRANCH:-main}"

echo "==> [1/6] 记录当前 commit（回滚点）"
PREV="$(git rev-parse HEAD)"
echo "    prev = $PREV"

echo "==> [2/6] 同步最新代码（origin/$BRANCH）"
git fetch origin
git reset --hard "origin/$BRANCH"
echo "    now  = $(git rev-parse --short HEAD)  $(git log -1 --pretty=%s)"

echo "==> [3/6] 备份数据库（迁移前必做）"
mkdir -p "$BACKUP_DIR"
TS="$(date +%F-%H%M%S)"
if $COMPOSE ps postgres 2>/dev/null | grep -q healthy; then
  $COMPOSE exec -T postgres pg_dump -U zhiyao zhiyao | gzip > "$BACKUP_DIR/zhiyao_$TS.sql.gz"
  echo "    备份: $BACKUP_DIR/zhiyao_$TS.sql.gz"
  # 仅保留最近 14 份
  ls -1t "$BACKUP_DIR"/zhiyao_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
else
  echo "    ⚠️ postgres 未就绪，跳过备份（首次部署正常）"
fi

echo "==> [4/6] 构建镜像"
$COMPOSE build

echo "==> [5/6] 数据库迁移（一次性容器，与应用启动解耦 · P0-11）"
# run --rm 会按 depends_on 先拉起 postgres/redis 至 healthy 再迁移；迁移失败 set -e 直接中止
# （不会进入半启动状态）→ 落到下方回滚逻辑由人工介入（迁移失败不自动 downgrade，需排查）。
$COMPOSE run --rm backend alembic upgrade head

echo "==> [6/6] 启动 + 健康闸（最多等 120s）"
$COMPOSE up -d
ok=0
for i in $(seq 1 24); do
  if curl -sf -m 3 "$HEALTH_URL" 2>/dev/null | grep -q '"status":"ready"'; then ok=1; break; fi
  sleep 5
done

if [ "$ok" = 1 ]; then
  echo "✅ 部署成功，health ok"
  $COMPOSE ps
else
  echo "❌ 健康检查失败（120s 未就绪）→ 回滚到 $PREV"
  git reset --hard "$PREV"
  $COMPOSE up -d --build
  echo "已回滚。请查日志：$COMPOSE logs --tail=60 backend"
  exit 1
fi
