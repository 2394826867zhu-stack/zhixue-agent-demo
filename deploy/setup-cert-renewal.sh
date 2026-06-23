#!/usr/bin/env bash
# 知曜 · HTTPS 证书签发 + 自动续期一键配置（P1-9）
# ----------------------------------------------------------------------------
# 在 ECS 上以 root 运行一次：装 certbot → 签发证书 → 装 deploy-hook（续期后重载 nginx）
# → 启用 certbot.timer（自动续期）→ 装到期告警 timer（兜底监控）。
#
# 前置：① 域名已解析到本机公网 IP；② nginx 已装且 80 端口可达（webroot/standalone 验证）；
#       ③ 本仓库已 clone 到 /opt/zhiyao（脚本从这里取 hook/alert 文件）。
#
# 用法：
#   sudo DOMAIN=api.zhiyao.app EMAIL=you@example.com REPO_DIR=/opt/zhiyao \
#        ALERT_WEBHOOK=https://your-bot-webhook ./deploy/setup-cert-renewal.sh
#
# 幂等：可重复运行（certbot 已有证书则跳过签发；文件覆盖安装）。
# ----------------------------------------------------------------------------
set -euo pipefail

DOMAIN="${DOMAIN:?需设 DOMAIN}"
EMAIL="${EMAIL:?需设 EMAIL（Let’s Encrypt 到期通知邮箱）}"
REPO_DIR="${REPO_DIR:-/opt/zhiyao}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
THRESHOLD_DAYS="${THRESHOLD_DAYS:-14}"

echo "==> 1/5 安装 certbot"
if ! command -v certbot >/dev/null 2>&1; then
    apt-get update -y && apt-get install -y certbot python3-certbot-nginx
fi

echo "==> 2/5 签发证书（nginx 插件自动改写 server 块 + 验证）"
if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    echo "    已存在 ${DOMAIN} 证书，跳过签发"
else
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect
fi

echo "==> 3/5 安装 deploy-hook（续期成功后重载 nginx）"
install -d /etc/letsencrypt/renewal-hooks/deploy
install -m 0755 "${REPO_DIR}/deploy/certbot-deploy-hook.sh" \
    /etc/letsencrypt/renewal-hooks/deploy/zhiyao-reload.sh

echo "==> 4/5 启用 certbot 自动续期 timer（每日两次尝试，到期前 30 天起续）"
systemctl enable --now certbot.timer
# 干跑校验整条续期链路（含 deploy-hook）能跑通，不真正续期
certbot renew --dry-run

echo "==> 5/5 安装到期告警 timer（续期失守的兜底监控）"
chmod +x "${REPO_DIR}/deploy/cert-expiry-alert.sh"
# 写入 service（注入本机 DOMAIN/阈值/webhook）
sed -e "s|api.zhiyao.app|${DOMAIN}|" \
    -e "s|THRESHOLD_DAYS=14|THRESHOLD_DAYS=${THRESHOLD_DAYS}|" \
    -e "s|ALERT_WEBHOOK=|ALERT_WEBHOOK=${ALERT_WEBHOOK}|" \
    -e "s|/opt/zhiyao|${REPO_DIR}|" \
    "${REPO_DIR}/deploy/systemd/zhiyao-cert-alert.service" \
    >/etc/systemd/system/zhiyao-cert-alert.service
cp "${REPO_DIR}/deploy/systemd/zhiyao-cert-alert.timer" /etc/systemd/system/zhiyao-cert-alert.timer
systemctl daemon-reload
systemctl enable --now zhiyao-cert-alert.timer

echo ""
echo "✅ 完成。验证："
echo "   systemctl list-timers | grep -E 'certbot|zhiyao-cert'"
echo "   certbot certificates"
echo "   ${REPO_DIR}/deploy/cert-expiry-alert.sh   # 手动跑一次告警检查"
