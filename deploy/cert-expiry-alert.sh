#!/usr/bin/env bash
# 知曜 · 证书到期告警（P1-9 · 自动续期的兜底监控）
# ----------------------------------------------------------------------------
# certbot.timer 会自动续期，但续期可能静默失败（DNS/防火墙/Let's Encrypt 限流/钩子报错）。
# 本脚本每日检查剩余有效天数，低于阈值即告警——续期机制失守时仍有人能在断网前介入。
#
# 用法（systemd timer 每日触发，见 zhiyao-cert-alert.{service,timer}）：
#   DOMAIN=api.zhiyao.app THRESHOLD_DAYS=14 ALERT_WEBHOOK=https://... ./cert-expiry-alert.sh
#   - DOMAIN（必填）：证书域名（对应 /etc/letsencrypt/live/<DOMAIN>/）
#   - THRESHOLD_DAYS（默认 14）：剩余天数低于此值告警
#   - ALERT_WEBHOOK（可选）：POST JSON 告警（钉钉/飞书/Slack 机器人 webhook）；未设则仅写日志
# 退出码：0=证书健康；2=临近到期（已告警）；1=证书缺失/解析失败
# ----------------------------------------------------------------------------
set -euo pipefail

DOMAIN="${DOMAIN:?需设 DOMAIN（证书域名）}"
THRESHOLD_DAYS="${THRESHOLD_DAYS:-14}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
LOG=/var/log/zhiyao-cert-renew.log

log() { echo "$(date -Is) [expiry-alert] $*" >>"$LOG"; }

alert() {
    local msg="$1"
    log "⚠️ $msg"
    if [[ -n "$ALERT_WEBHOOK" ]]; then
        # 通用文本字段，钉钉/飞书/Slack 多数自定义机器人都吃 {"text": "..."}；
        # 不同平台字段名略有差异，按你的机器人改 -d 内容即可。
        curl -fsS -m 10 -X POST -H 'Content-Type: application/json' \
            -d "{\"text\": \"[知曜证书告警] ${msg}\"}" "$ALERT_WEBHOOK" >/dev/null 2>>"$LOG" \
            || log "❌ webhook 告警发送失败"
    fi
}

if [[ ! -f "$CERT" ]]; then
    alert "证书文件不存在：$CERT（域名 $DOMAIN 未签发或路径不符）"
    exit 1
fi

# 到期时间戳 → 剩余天数
end_date=$(openssl x509 -enddate -noout -in "$CERT" 2>/dev/null | cut -d= -f2) || {
    alert "无法解析证书有效期：$CERT"
    exit 1
}
end_epoch=$(date -d "$end_date" +%s)
now_epoch=$(date +%s)
days_left=$(( (end_epoch - now_epoch) / 86400 ))

if (( days_left < THRESHOLD_DAYS )); then
    alert "证书 $DOMAIN 仅剩 ${days_left} 天到期（阈值 ${THRESHOLD_DAYS}）→ 检查 certbot.timer / 手动续期：certbot renew"
    exit 2
fi

log "✓ 证书 $DOMAIN 健康，剩余 ${days_left} 天"
exit 0
