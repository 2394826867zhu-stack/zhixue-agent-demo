# 知曜公开 Demo 分享方案（2026-05-17）

## 目标

让外部朋友可以通过一个公网链接查看当前前端 Demo，不要求他们本地启动后端，也不暴露本机后端服务。

## 已实现

- 前端 API 层已加入 Demo 模式：`lib/api.ts`
- 当页面运行在外部域名，但 API 地址仍是默认 `http://localhost:8000/v1` 时，会自动切换到前端内置演示数据。
- 本地 `localhost:3000` 访问时仍默认连接本地后端，方便继续联调。
- 也可以通过环境变量强制打开：

```bash
NEXT_PUBLIC_DEMO_MODE=true
```

## 推荐分享方式 A：Cloudflare Tunnel

适合临时给朋友看，启动快，不需要部署。

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-frontend
npm run dev
cloudflared tunnel --url http://localhost:3000
```

把 Cloudflare 输出的 `https://...trycloudflare.com` 链接发给朋友即可。

## 推荐分享方式 B：ngrok

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-frontend
npm run dev
ngrok http 3000
```

把 ngrok 输出的 `https://...ngrok-free.app` 链接发给朋友。

## 推荐分享方式 C：Vercel 预览部署

适合更稳定地收集反馈。

1. 推送当前分支到 GitHub。
2. 在 Vercel 导入前端项目。
3. 添加环境变量：

```bash
NEXT_PUBLIC_DEMO_MODE=true
```

4. 部署后分享 Vercel Preview URL。

## 体验账号

```text
用户名: demo
密码: zhiyao2025
```

## 本地测试 Demo 模式

在浏览器控制台执行：

```js
localStorage.setItem("zhiyao_demo_mode", "true");
location.reload();
```

关闭本地强制 Demo：

```js
localStorage.removeItem("zhiyao_demo_mode");
location.reload();
```

## 注意事项

- 这是一套用于公开试看和收集反馈的前端演示方案，不等同于正式生产环境。
- 如果要开放真实后端能力，需要把后端部署到公网，并设置 `NEXT_PUBLIC_API_URL=https://your-api-domain/v1`。
- 当前方案不会让外部访客访问你电脑上的 `localhost:8000`。
