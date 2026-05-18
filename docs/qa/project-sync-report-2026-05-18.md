# 知曜项目同步与前端对齐报告

日期：2026-05-18  
前端版本：v0.6  
后端版本：v0.14  
后端地址：`http://localhost:8000/v1`  
前端地址：`http://localhost:3000`

## 1. 当前进度结论

当前后端 OpenAPI 已同步到：

- Path count：60
- Operation count：73
- 新增核心接口：`POST /v1/agent/chat`

前端已完成 v0.14 对齐：

- 全局 AI 浮标已从旧的 `/checkin` 单点签到模式升级为 `/agent/chat` SSE 流式 Agent。
- onboarding、checkin、profile、tasks 等上一轮 P0/P1 阻塞保持可用。
- `SPEC.md` 已同步为前端 v0.6。

## 2. 本轮前端对齐内容

### 2.1 新增 Agent SSE 客户端

文件：

- `lib/api.ts`

新增：

```ts
streamAgentChat(message, session_id, handlers)
```

支持事件：

- `thinking`
- `delta`
- `done`

行为：

- 自动携带 `Authorization: Bearer <access_token>`
- 使用 `fetch + ReadableStream` 解析 `text/event-stream`
- 保存服务端返回的 `session_id`，用于多轮上下文
- Demo 模式提供本地模拟回复

### 2.2 全局 AI 浮标接入新 Agent

文件：

- `components/agent/agent-layer.tsx`

调整：

- 用户输入后调用 `/v1/agent/chat`
- 流式追加 AI 回复
- 支持服务端 thinking 状态
- 接收 `done.session_id` 后保存会话 id
- 成功后刷新：
  - 今日签到
  - 今日任务
  - 知识点列表
  - 知识点统计
  - 进度概览
  - 个人中心概览

### 2.3 保留 checkin 数据链路

说明：

- `/v1/checkin/*` 仍作为“每日管家签到记录”数据源。
- 新 Agent 可以通过后端工具创建任务/知识点；前端在 Agent 完成后刷新相关缓存。

### 2.4 修复前端类型问题

文件：

- `app/(app)/flashcards/page.tsx`
- `components/dashboard/mastery-ring.tsx`

处理：

- 修复闪卡页 `useQuery` 类型写法。
- 修复 Recharts tooltip formatter 参数类型。

结果：

- `npx tsc --noEmit` 已通过。

## 3. 后端接口验证

真实测试账号验证通过：

- `GET /v1/auth/me`
- `GET /v1/onboarding/status`
- `GET /v1/checkin/today`
- `GET /v1/profile/insights`
- `GET /v1/profile/achievements`
- `GET /v1/tasks`
- `POST /v1/agent/chat`

`POST /v1/agent/chat` 实测返回：

```text
Content-Type: text/event-stream; charset=utf-8
data: {"delta": "..."}
data: {"done": true, "session_id": "...", "tools_called": []}
```

## 4. 前端验证

已执行：

```bash
npm run lint
npx tsc --noEmit
```

结果：全部通过。

浏览器冒烟：

- `http://localhost:3000/dashboard` 可加载。
- Dashboard 首屏正常。
- 全局 AI 浮标存在。

## 5. 需求覆盖状态

已覆盖：

- 新用户注册后进入 onboarding
- onboarding 可调用真实后端状态机
- 用户可通过全局 AI 浮标与 AI 管家交互
- AI 管家支持流式输出和多轮会话 id
- AI 完成后可刷新任务/知识点/进度相关缓存
- profile 空用户 0 值状态可用
- checkin 历史/今日记录接口可用

仍建议继续验证：

- 真实用户完整走完 8 步 onboarding 后，是否自动生成符合预期的知识库/时间线/计划
- Agent 调用工具创建任务、知识点、考试时，前端各页面是否全部实时同步
- Agent SSE 的错误事件/超时事件是否需要后端约定更细的事件类型
- SPEC 后半部分旧 API 表仍建议全量刷新，避免未来 Agent 交接误读

## 6. 当前判断

前端已经完成 v0.14 基础对齐，可以进入下一轮真实用户 E2E 和体验细化。

