# 知曜前后端对齐报告

日期：2026-05-18  
前端仓库：`zhiyao-frontend`  
后端地址：`http://localhost:8000/v1`  
前端地址：`http://localhost:3000`

## 1. 结论

后端本轮修复后，前端核心阻塞已解除。

已确认运行时 OpenAPI 包含：

- `GET /v1/onboarding/status`
- `POST /v1/onboarding/chat`
- `POST /v1/onboarding/restart`
- `POST /v1/checkin`
- `GET /v1/checkin/today`
- `GET /v1/checkin/history`
- `GET /v1/profile/insights`
- `GET /v1/profile/achievements`

真实测试账号完成了以下 API 验证：

- 注册成功
- `/auth/me` 正常返回真实用户
- `/onboarding/status` 正常返回建档步骤
- `/onboarding/chat` 正常推进到下一步
- `/checkin/today` 空用户返回 `null`
- `/checkin` 可以创建知识点和任务
- `/checkin/history` 可以读取历史签到
- `/profile/insights` 空用户返回 0 值面板，不再 500
- `/profile/achievements` 空用户返回 20 个成就，不再 500
- `/tasks` 创建、完成、再查询均正常

## 2. 本轮前端已对齐

### 2.1 Dashboard 任务状态更新

问题：

- Dashboard 的今日任务组件仍使用旧字段 `{ is_done: boolean }` 更新任务。
- 后端当前稳定契约是 `status: "pending" | "done"`，响应中额外提供 `is_done` 派生字段。

处理：

- `components/dashboard/today-tasks.tsx`
- 更新任务时改为：

```ts
updateTask(id, { status: isDone ? "done" : "pending" })
```

- 乐观更新同步写入 `status` 和 `is_done`。

### 2.2 全局 AI 签到后的缓存刷新

问题：

- 全局 AI 浮标提交 `/checkin` 后，后端会真实创建知识点和任务，但前端当前页面缓存不会立刻刷新。

处理：

- `components/agent/agent-layer.tsx`
- 签到成功后刷新：
  - `agent-today-checkin`
  - `today-tasks`
  - `kps`
  - `kp-stats`
  - `progress-overview`

效果：

- 用户说“今天学了什么”后，Dashboard 任务、知识点页和进度概览可以自动进入下一轮同步。

### 2.3 SPEC 状态同步

处理：

- 更新 `C:\Users\18208\Desktop\知曜创业项目\SPEC.md`
- 将前端版本标记为 `v0.5`
- 将 `/path`、`/profile`、`/onboarding`、全局签到标记为已接真实 API
- 修正注册 `grade` 枚举为：

```ts
"junior_high" | "senior_high" | "college"
```

## 3. 后端验证结果

### 3.1 Onboarding

`GET /v1/onboarding/status` 返回：

```json
{
  "current_step": "grade",
  "step_index": 0,
  "total_steps": 8,
  "completed": false,
  "question": "...",
  "profile_draft": {}
}
```

`POST /v1/onboarding/chat` 返回：

```json
{
  "reply": "...",
  "step": "subjects",
  "step_index": 1,
  "total_steps": 8,
  "completed": false,
  "profile_draft": {
    "grade": "高二",
    "grade_type": "senior"
  }
}
```

前端当前已兼容：chat 返回 `step` 后映射为页面状态里的 `current_step`。

### 3.2 CheckIn

`POST /v1/checkin` 返回：

```json
{
  "raw_content": "...",
  "ai_summary": "...",
  "parsed_updates": {
    "kp_updates": [],
    "kps_created": [],
    "tasks_created": []
  },
  "created_at": "..."
}
```

实测：

- 会创建知识点。
- 会创建任务。
- `/checkin/history` 可读取。

### 3.3 Profile

空用户 `GET /v1/profile/insights` 已返回稳定 0 值。

空用户 `GET /v1/profile/achievements` 已返回 20 个成就对象。

前端个人中心可继续使用当前实现。

### 3.4 Tasks

任务对象当前同时包含：

```ts
status: "pending" | "done"
is_done: boolean
estimated_minutes: number
duration: number
```

前端策略：

- 写入使用 `status`
- 展示兼容 `is_done`

## 4. 仍建议后端/规格确认

### 4.1 Onboarding `grade_type` 命名

注册接口使用：

```ts
"junior_high" | "senior_high" | "college"
```

onboarding draft 返回：

```ts
"junior" | "senior"
```

这不是当前阻塞，但建议统一命名，避免后续画像系统出现双枚举。

### 4.2 SPEC 仍有旧章节需要后续整体刷新

本轮只更新了顶部状态和注册枚举。

SPEC 后面部分仍可能保留旧接口描述，例如：

- 旧任务接口 `/tasks/today`
- 旧训练接口 `/training/generate`
- 旧 guidance 描述

建议后端下一轮用 OpenAPI 重新生成或手动刷新全量 API 表。

### 4.3 成就 icon 仍是 emoji

后端返回成就图标为 emoji，前端目前照常展示。

如果后续视觉继续走极简科技风，建议后端只返回成就类型，由前端映射 lucide/icon asset。

## 5. 验证

前端静态检查：

```bash
npm run lint
```

结果：通过。

浏览器冒烟：

- `http://localhost:3000/dashboard` 可正常加载。
- 页面标题、Dashboard 内容、全局 AI 浮标均存在。

## 6. 下一步建议

1. 用真实账号完整走完 8 步 onboarding。
2. 完成 onboarding 后检查是否自动生成路径、目标和任务。
3. 用全局 AI 签到后检查 Dashboard、知识点、任务、进度是否同步刷新。
4. 对新用户空状态做一轮文案和 CTA 精修。

