@AGENTS.md
@../SPEC.md

# 前端开发规范（Codex 专用）

## 身份
我是知曜·智学Agent **前端 Agent**，只负责 `zhiyao-frontend/`（即 `C:\zhiyao`），不修改任何后端文件。

## 新会话启动清单
1. 读根目录 `../SPEC.md` → Section 0 了解冲刺状态，Section 2 了解可用 API
2. 运行 `git log --oneline -5` 确认最新提交
3. 告知用户：当前状态 + 建议下一步

## 技术栈
- Next.js 16 + React 19（App Router）
- Tailwind v4 + shadcn/ui
- Zustand（状态管理）+ TanStack Query（数据请求）
- Recharts（图表）

## 重要约束
- 路径含中文，**Turbopack 会崩溃**，始终用 `npm run dev`（webpack）
- 软链：`C:\zhiyao` → 实际路径 `C:\Users\18208\Desktop\知曜创业项目\zhiyao-frontend`
- Dev mock 登录：用户名 `demo` / 密码 `zhiyao2025`

## API 调用规范
- 所有 API 调用通过 `lib/api.ts` 的封装函数，不直接 fetch
- 认证 token 由 axios 拦截器自动附加，不要在页面手动带 header
- 新端点需要时，先在 SPEC.md Section 3 记录需求，等后端 Agent 开发完毕再对接

## V2 设计方向
参考 `docs/design-archive/zhiyao-uiux-v2-high-quality-app.md`：
- 品牌主色：Aurora Mint（薄荷青）
- 设计气质：清晰、可靠、轻松、有陪伴感
- 实施分期：Phase 1（接 API）→ Phase 2（设计系统 + Dashboard V2）→ Phase 3（新页面）
