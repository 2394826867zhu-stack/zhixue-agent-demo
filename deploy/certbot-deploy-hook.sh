#!/usr/bin/env bash
# 知曜 · certbot --deploy-hook（P1-9 证书自动续期）
# ----------------------------------------------------------------------------
# certbot 续期成功后自动执行：校验并重载 nginx，让新证书即时生效（否则旧证书
# 续了但进程仍持旧文件，到期照样断 HTTPS）。
# 安装位置（执行者在 ECS 上）：/etc/letsencrypt/renewal-hooks/deploy/zhiyao-reload.sh
# 由 setup-cert-renewal.sh 自动放置；certbot.timer 每次成功续期后自动调用本钩子。
# ----------------------------------------------------------------------------
set -euo pipefail

LOG=/var/log/zhiyao-cert-renew.log

if nginx -t 2>>"$LOG"; then
    systemctl reload nginx
    echo "$(date -Is) [deploy-hook] 证书已续期，nginx 已重载" >>"$LOG"
else
    echo "$(date -Is) [deploy-hook] ❌ nginx 配置校验失败，未重载（证书已更新但需人工介入）" >>"$LOG"
    exit 1
fi
