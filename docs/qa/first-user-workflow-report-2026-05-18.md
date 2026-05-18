# 知曜 Demo 第一批用户工作流测试报告

日期：2026-05-18  
测试角色：前端测试员 / 第一批真实用户  
测试环境：Frontend `http://localhost:3000`，Backend `http://localhost:8000`  
后端健康检查：`GET /health` 正常，返回 `status: ok`

## 1. 测试范围

本轮按“新用户从零开始”的路径测试：

- 注册 / 登录 / 新用户引导
- Dashboard、任务、学习路径、笔记、知识点、闪卡、训练、错题、AI 助手、进度、个人中心
- 全局 AI 浮标相关的数据依赖
- 关键 API 连通性、空用户状态、Demo 状态干扰
- 按钮反馈、加载状态、空状态、移动端导航、基础可访问性

## 2. 已由前端自行修复

### 2.1 注册/登录用户名转邮箱问题

问题：前端把无邮箱格式的用户名补成 `@zhiyao.local`，后端 `EmailStr` 会拒绝 `.local` 保留域名，导致真实注册失败。

处理：

- 新增 `lib/auth-identity.ts`
- 将内部补全域名改为 `zhiyao.app`
- 登录和注册统一使用 `normalizeLoginIdentity()`

影响文件：

- `lib/auth-identity.ts`
- `app/register/page.tsx`
- `app/login/page.tsx`

### 2.2 Demo 状态污染真实用户

问题：浏览器里残留 `zhiyao_demo_mode` / `zhiyao-auth` 时，新注册用户可能仍被识别为 Demo 用户，掩盖真实后端错误。

处理：

- 注册和登录走真实 API 前，清理 Demo 相关本地状态。

影响文件：

- `app/register/page.tsx`
- `app/login/page.tsx`

### 2.3 真实登录后用户信息不完整

问题：后端登录/注册返回 token，但不一定返回 user。前端此前会把真实用户写成 `id: ""` 的临时用户，影响侧栏头像、用户状态和后续功能扩展。

处理：

- 登录/注册拿到 token 后，立即调用 `/auth/me` 补全用户信息。
- 如果 `/auth/me` 临时失败，再使用最小 fallback，避免登录流程中断。

影响文件：

- `app/register/page.tsx`
- `app/login/page.tsx`

### 2.4 进度页“新增错题”空值

问题：`weeklyReport.wrong_count` 缺失时，页面出现“新增错题  道”的空值显示。

处理：

- 增加 `?? 0` 兜底。

影响文件：

- `app/(app)/progress/page.tsx`

### 2.5 任务页按钮语义和视觉一致性

问题：

- 任务卡片可点击，但缺少键盘语义。
- 任务类型使用 emoji 图标，与当前极简科技风不一致。

处理：

- 任务卡片增加 `role="button"`、`tabIndex`、Enter/Space 触发。
- 任务类型改为 `lucide-react` 线性图标。
- AI 理由前的 emoji 改为 `Lightbulb` 图标。

影响文件：

- `app/(app)/tasks/page.tsx`

### 2.6 移动端侧栏按钮 aria

问题：移动端菜单、关闭、退出按钮缺少可读标签。

处理：

- 增加 `aria-label`。

影响文件：

- `components/layout/mobile-nav.tsx`

### 2.7 验证

前端已执行：

```bash
npm run lint
```

结果：通过。

## 3. P0 后端阻塞问题

### 3.1 运行中的后端缺少 `/v1/onboarding/*` 和 `/v1/checkin/*`

现象：

- 前端真实新用户引导依赖：
  - `GET /v1/onboarding/status`
  - `POST /v1/onboarding/chat`
  - `POST /v1/onboarding/restart`
- 全局 AI 浮标 / 每日管家依赖：
  - `GET /v1/checkin/today`
  - `POST /v1/checkin`
  - `GET /v1/checkin/history`

实际测试：

- 运行中的 `http://localhost:8000/openapi.json` 没有 onboarding 和 checkin 路由。
- 调用这些接口返回 404。

重要发现：

- 后端源码 `app/api/v1/__init__.py` 已 include：
  - `onboarding.router`
  - `checkin.router`
- 源码文件也存在：
  - `app/api/v1/onboarding.py`
  - `app/api/v1/checkin.py`

判断：

- 更像是当前 8000 端口运行的后端进程不是最新代码，或没有从当前 `zhiyao-backend` 目录重新加载。
- 不像前端路径错误。

建议后端处理：

1. 停止当前 8000 端口进程。
2. 在 `C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend` 目录重新启动。
3. 启动后检查：
   - `GET /openapi.json` 是否包含 `/v1/onboarding/status`
   - `GET /openapi.json` 是否包含 `/v1/checkin/today`
4. 如果重启后仍缺失，检查导入异常是否被吞掉、包路径是否加载了旧版本。

验收标准：

- 新用户注册后进入 `/onboarding`，真实 API 可推进状态机。
- 全局 AI 浮标可以读取今日签到，提交“今天学了什么”后返回整理结果。

### 3.2 `/v1/profile/insights` 和 `/v1/profile/achievements` 对真实新用户返回 500

现象：

- 真实新用户 token 调用：
  - `GET /v1/profile/insights`
  - `GET /v1/profile/achievements`
- 返回：

```json
{"code":5000,"message":"服务器内部错误","data":null}
```

影响：

- 个人中心真实数据不可用。
- Demo 数据会掩盖这个问题。

建议后端排查：

- 优先看新用户空数据下的聚合逻辑。
- 重点检查 `profile_service._collect_metrics()`：
  - `KnowledgePoint.mastery_status` 枚举/字符串兼容
  - `PomodoroRecord.started_at` 的 `func.date()` 在当前数据库上的返回类型
  - Pydantic schema 是否接受所有 metric 类型
  - 成就中的 `icon` emoji 是否在 JSON 序列化 / 数据库编码中有问题

验收标准：

- 空用户也返回完整 0 值面板，而不是 500。
- `/profile` 页面不依赖 Demo fallback 也能正常展示。

## 4. P1 前后端契约/产品体验问题

### 4.1 新用户引导目前被本地状态兜底，真实后端失败时不够明确

现象：

- 当前前端有 Demo onboarding fallback。
- 真实 API 404 时，如果本地 Demo 状态存在，用户可能看到可完成的引导流程，但实际后端没有沉淀知识库/目标/时间线。

建议：

- 后端修复路由后，前端再增加“真实模式接口失败”的明确错误态。
- 对外分享 Demo 时可以保留 Demo fallback，但真实登录态不应悄悄进入 Demo 数据。

### 4.2 训练页空用户启动训练返回业务错误

现象：

- 真实新用户无知识点时 `POST /v1/training/start` 返回业务错误：没有可用知识点。

判断：

- 后端行为合理。

建议前端后续优化：

- 在训练页空状态中引导用户先生成笔记、创建知识点、完成新用户引导，而不是只报错。

### 4.3 任务状态字段需要保持一致

现象：

- 前端任务模型同时存在 `status` 和 `is_done`。
- 当前任务完成操作已使用 `status: "done" / "pending"`，但页面列表仍用 `is_done` 分组。

建议：

- 后端返回任务时继续保留 `is_done` 派生字段，或前端统一改为只读 `status`。
- API 文档里明确任务完成态字段，以免后续模块接入时状态不同步。

### 4.4 SPEC 与运行时接口存在差异

观察到的差异：

- SPEC 中 onboarding/checkin 写为已完成，但运行时 OpenAPI 缺失。
- SPEC 中部分旧接口与运行时不同，例如 training、tasks、guidance 路径。

建议：

- 后端以当前 OpenAPI 为准更新 SPEC。
- 前端以 SPEC 开发前，需要先做一次 OpenAPI 对账。

## 5. 页面级体验记录

### 5.1 注册 / 登录

已测：

- 用户名、密码、昵称、年级注册。
- 登录后 token 可获取 `/auth/me`。

已修：

- 用户名补全邮箱域名。
- Demo 状态污染。

剩余建议：

- 注册成功后如果 onboarding API 不可用，应给出“学习系统初始化失败，可重试”的明确反馈。

### 5.2 Onboarding

Demo 流程可完成：

- 年级
- 科目
- 当前进度
- 成绩水平
- 下一次考试
- 学习目标
- 跳过上传
- 确认建立学习系统

真实阻塞：

- 后端 `/v1/onboarding/*` 404。

### 5.3 Dashboard

整体可用。

建议：

- 首屏数据 loading 期间需要保持骨架屏一致性，避免短时间空白造成“没加载出来”的感觉。

### 5.4 每日任务

已修：

- 图标风格从 emoji 改为 lucide。
- 任务卡片增加键盘触发。

建议：

- AI 生成任务失败时，toast/错误态需要更友好，尤其是新用户知识库为空时。

### 5.5 学习路径

可用。

建议：

- 空路径时 CTA 要更明确：建议显示“先完成引导 / 让 AI 建立路径”。
- AI 重排路径应显示更明确的执行中状态。

### 5.6 笔记 / 知识点 / 闪卡

基础浏览可用。

建议：

- 空状态要更像学习管家：告诉用户可以上传课堂笔记、输入今天学了什么、或让 AI 生成第一组闪卡。

### 5.7 训练

基础页面可用。

问题：

- 空用户启动训练会失败，需要把后端业务错误翻译成学习引导。
- 学科选中态需要更明确，避免默认学科与用户预期不一致。

### 5.8 错题本

基础列表可用。

建议：

- “重新练习”“移出”操作后需要统一 toast 和动效反馈。

### 5.9 AI 助手 / 全局 AI 浮标

页面 AI 助手基础 API 可用：

- `POST /v1/guidance/sessions`
- `POST /v1/guidance/sessions/{id}/chat`

全局 AI 浮标真实模式阻塞：

- 依赖 `/v1/checkin/*`，当前运行时后端 404。

### 5.10 进度

已修：

- 周报“新增错题”缺字段时兜底为 0。

建议：

- 后端 weekly report schema 明确 `wrong_count` 是否必传。

### 5.11 个人中心

Demo 可显示。

真实阻塞：

- `/v1/profile/insights` 500。
- `/v1/profile/achievements` 500。

## 6. 当前可交给后端的最高优先级清单

1. 修复运行时后端缺少 `/v1/onboarding/*` 和 `/v1/checkin/*`。
2. 修复真实新用户 `/v1/profile/insights`、`/v1/profile/achievements` 500。
3. 更新 SPEC，使其与实际 OpenAPI 完全一致。
4. 明确任务状态字段：`status` 与 `is_done` 的长期契约。
5. 为新用户空数据场景返回稳定 0 值，而不是业务异常或 500。

## 7. 前端下一步建议

后端修复 P0 后，建议继续做一轮真实用户 E2E：

1. 清空浏览器 Demo localStorage。
2. 注册新用户。
3. 完成真实 onboarding。
4. 用全局 AI 提交“今天学了什么”。
5. 检查是否生成知识点、任务、时间线、学习路径。
6. 从任务页完成一个任务，再查看 Dashboard / Progress / Profile 是否同步更新。
