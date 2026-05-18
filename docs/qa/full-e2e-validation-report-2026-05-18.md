# 知曜完整 E2E 验证报告

日期：2026-05-18  
范围：新用户注册后建档、AI Agent、知识库、任务、考试、路径、进度闭环  
前端：`http://localhost:3000`  
后端：`http://localhost:8000/v1`

## 1. 总结

本轮验证结果：核心数据闭环大体成立，但仍有两个需要继续跟进的问题。

已确认成立：

- onboarding 8 步状态机可完整完成。
- onboarding 完成后会生成用户画像草稿。
- onboarding 会沉淀基础知识点。
- onboarding 会创建下一次考试。
- 进度概览和个人中心能读取新用户真实数据。
- `/v1/agent/chat` SSE 可流式返回。
- Agent 在明确任务创建指令下，可以调用 `manage_tasks` 创建任务。
- `/path/ai-generate` 可以基于已有知识点生成学习路径。

待跟进：

- 浏览器中残留 Demo 状态会干扰真实 UI 验证，已做前端修复。
- Agent 对“今天学了什么，请整理知识点并生成明天复习任务”这类综合指令有一次失败，只返回“回复生成时遇到问题，请重试”，需要后端继续查 Agent 工具链/LLM 错误处理。
- onboarding 完成后不会自动生成学习路径；如果产品预期是“建档后自动形成计划/路径”，需要把 `/path/ai-generate` 串进 onboarding 完成流程或前端完成页 CTA 自动触发。

## 2. 前端本轮已修

### 2.1 Demo 状态优先级问题

问题：

- 浏览器残留 `zhiyao_demo_mode` 时，真实 token 也可能继续显示“知曜体验用户”。
- 这会干扰从 Demo 切换到真实账号，也干扰 E2E 验证。

处理：

- `lib/api.ts`
- `isDemoMode()` 中真实 token 优先级高于 Demo 标记。

### 2.2 退出登录清理 Demo 标记

问题：

- `clearAuth()` 只清理 `access_token`，没有清理 Demo/onboarding 标记。

处理：

- `lib/store.ts`
- 退出登录时同时清理：
  - `zhiyao_demo_mode`
  - `zhiyao_needs_onboarding`
  - `zhiyao_onboarding_completed`

## 3. 真实后端 E2E 验证

测试账号：

- `full-e2e-20260518035241@zhiyao.app`

### 3.1 Onboarding

输入序列：

1. `高二`
2. `数学、物理、英语`
3. `数学二次函数，物理浮力`
4. `中等偏上`
5. `期末考试，6月25日`
6. `稳定完成作业和复习`
7. `先跳过`
8. `确认建立学习系统`

结果：

- `completed: true`
- `step_index: 8`
- `current_step: completed`

最终画像草稿包含：

- 年级：高二
- 科目：数学、物理、英语
- 当前学习：数学二次函数、物理浮力
- 目标：稳定完成作业和复习
- 考试：期末考试，2026-06-25

### 3.2 Onboarding 后数据沉淀

验证结果：

- 知识点数量：9
- 考试数量：1
- 进度概览：
  - `total_kps: 9`
  - `kp_delta_week: 9`
  - `today_tasks_total: 0`
- 个人中心：
  - `total_kps: 9`
  - `achievements_earned: 1`

说明：

- onboarding 会生成知识库和考试。
- onboarding 不会自动生成今日任务。
- onboarding 不会自动生成学习路径。

### 3.3 Agent 综合指令测试

输入：

```text
今天我学习了数学导数和物理电磁感应，完成了作业。请帮我整理知识点并生成明天复习任务。
```

返回：

```text
thinking: get_full_context
thinking: diagnose_learning
delta: 抱歉，回复生成时遇到问题，请重试。
done: tools_called = ["get_full_context", "diagnose_learning"]
```

结果：

- 没有创建任务。
- 没有新增知识点。

判断：

- Agent 基础 SSE 链路可用。
- 综合意图下工具链中断或 LLM 生成异常，需要后端排查。

### 3.4 Agent 明确任务创建测试

输入：

```text
请直接为明天创建两个任务：复习数学二次函数20分钟，复习物理浮力20分钟。
```

返回：

- `tools_called: ["get_full_context", "manage_tasks"]`
- SSE 正常流式输出。

结果：

- 成功创建 2 个任务：
  - 复习数学二次函数，20 分钟
  - 复习物理浮力，20 分钟

判断：

- `manage_tasks` 工具可用。
- Agent 对明确任务创建指令可闭环。

### 3.5 学习路径生成

调用：

```http
POST /v1/path/ai-generate
```

结果：

- 成功生成 3 个阶段。
- 第一个阶段包含当前节点。
- `/v1/path/stages` 可读取。

判断：

- 路径模块可用。
- 但 onboarding 完成后未自动触发路径生成。

## 4. 浏览器 UI 验证

已验证：

- `/dashboard` 正常加载。
- 全局 AI 浮标存在。
- onboarding 页面可通过建议按钮推进到 100%。

限制：

- 当前内置浏览器自动填充 input 时被虚拟剪贴板限制拦截，无法稳定模拟注册表单输入。
- 当前浏览器残留 Demo 状态，导致 Dashboard 一度显示“知曜体验用户”。前端已修复真实 token 优先级和退出清理逻辑，后续重开/清理浏览器后需复测。

## 5. 验证命令

前端质量门：

```bash
npm run lint
npx tsc --noEmit
```

结果：全部通过。

## 6. 后端建议

### P1：Agent 综合意图失败

需要后端检查：

- `diagnose_learning` 后为什么没有继续 `manage_knowledge_points` / `manage_tasks`
- LLM 回复生成失败的真实异常日志
- SSE 是否应该返回结构化 `error` 事件，而不是只返回普通 `delta`

建议事件格式：

```text
data: {"error": {"code": "...", "message": "...", "recoverable": true}}
```

### P1：建档完成后是否自动生成路径/计划

产品需求里“自动整理计划”比较明确。

建议二选一：

- 后端 onboarding 完成时自动调用路径/任务生成服务。
- 前端完成页在用户点击“进入我的学习系统”前自动触发 `/path/ai-generate` 和初始任务生成。

### P2：Onboarding `grade_type` 命名统一

当前返回：

```json
"grade_type": "senior"
```

注册枚举是：

```ts
"junior_high" | "senior_high" | "college"
```

建议统一，避免长期画像字段出现双标准。

## 7. 当前判断

可以进入下一阶段体验打磨，但在对外分享前，建议先修 Agent 综合意图失败和建档后自动路径/计划这两个问题。否则用户会觉得“建档完成了，但下一步还要自己点/自己说得很明确”。

