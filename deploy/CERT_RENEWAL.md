# HTTPS 证书自动续期（P1-9）

> 上线审计 P1-9：证书无自动续期 → 90 天后静默过期，全站 HTTPS 断、App 全部请求失败。
> 本方案：certbot 自动续期 + deploy-hook 重载 nginx + 到期告警兜底监控。

## 组成

| 文件 | 作用 |
|---|---|
| `setup-cert-renewal.sh` | 一键配置（ECS root 跑一次）：装 certbot → 签发 → 装 hook → 启 timer → 装告警 |
| `certbot-deploy-hook.sh` | certbot 续期成功后重载 nginx（装到 `/etc/letsencrypt/renewal-hooks/deploy/`） |
| `cert-expiry-alert.sh` | 每日检查剩余天数，低于阈值告警（webhook + 日志），续期失守的兜底 |
| `systemd/zhiyao-cert-alert.{service,timer}` | 每日 08:00 跑告警检查 |

## 续期为什么不只靠 certbot.timer

certbot 装好即自带 `certbot.timer`（每日两次 `certbot renew`，到期前 30 天起续）。但续期会
**静默失败**（DNS 改动 / 80 端口被防火墙挡 / Let's Encrypt 限流 / hook 报错），且续期成功后
**默认不重载 nginx**（进程仍持旧证书文件）。所以两件事必须补：

1. **deploy-hook 重载 nginx** —— 续期后新证书即时生效（否则续了等于没续）。
2. **到期告警** —— 续期失守时在断网前有人能介入（纯靠 timer = 失败无人知，直到用户报障）。

## 部署（执行者在 ECS 上）

```bash
# 本仓库 clone 到 /opt/zhiyao（与生产 compose 同源，禁在服务器手改）
sudo DOMAIN=api.zhixue.click EMAIL=you@example.com REPO_DIR=/opt/zhiyao \
     ALERT_WEBHOOK=https://your-feishu-or-dingtalk-bot \
     /opt/zhiyao/deploy/setup-cert-renewal.sh
```

脚本结尾会跑 `certbot renew --dry-run` 干跑验证整条续期链路（含 deploy-hook）能通。

## 验证

```bash
systemctl list-timers | grep -E 'certbot|zhiyao-cert'   # 两个 timer 都 active
certbot certificates                                     # 证书有效期
/opt/zhiyao/deploy/cert-expiry-alert.sh                  # 手动跑一次告警检查（剩余天数）
tail -f /var/log/zhiyao-cert-renew.log                   # 续期/告警日志
```

## 与 nginx 配置的衔接

`setup-cert-renewal.sh` 用 `certbot --nginx` 签发，会自动改写 `nginx-zhiyao.conf` 对应的
`ssl_certificate` 路径为 `/etc/letsencrypt/live/<domain>/{fullchain,privkey}.pem`（即
nginx-zhiyao.conf 注释里的方案 B）。若用阿里云 DV 证书（方案 A），则不走 certbot，需手动
每年换证 —— **不推荐**，免续期心智负担选 certbot。

## 故障处理

- **告警触发（剩余 < 14 天）**：先 `certbot renew` 手动续；不成看 `/var/log/letsencrypt/`
  定位（最常见：80 端口验证被安全组/防火墙挡，或域名解析漂移）。
- **续期成功但仍报旧证书**：deploy-hook 没装或 nginx 没 reload，手动 `nginx -t && systemctl reload nginx`。
