# 知曜 UI/UX V2 实现归档

归档时间：2026-05-17
分支：`color/version-b`
目标：基于 V2 设计方案，先落地可见的产品级视觉和核心页面体验。

## 已完成

### 1. 主题系统

文件：`app/globals.css`

- 将临时荧光紫调整为更适合长期学习产品的 Aurora Mint。
- 保留 `oklch()` 色彩空间。
- 增加更柔和的浅背景、深海蓝侧栏、主色 focus ring。
- 增加卡片阴影 token：`--shadow-card`、`--shadow-card-hover`。
- 设置 tabular numbers，让数据卡片更稳定。

### 2. 基础组件质感

文件：

- `components/ui/button.tsx`
- `components/ui/card.tsx`
- `components/ui/badge.tsx`

改动：

- Button 调整为 40/48px 更适合触控和现代 App 的高度。
- Primary button 增加柔和品牌色投影。
- 新增 `soft` button variant，用于低压力建议操作。
- Card 改为 2xl 圆角、轻边框、轻阴影。
- Badge 增加更舒适的 24px 高度，并扩展 success/warning 语义。

### 3. 导航结构

文件：

- `components/layout/sidebar.tsx`
- `components/layout/mobile-nav.tsx`
- `app/(app)/layout.tsx`

改动：

- Sidebar 宽度从 224px 调整为 256px。
- 导航分组为：
  - 今日：首页、每日任务
  - 学习：笔记、知识点、闪卡复习、训练、错题本
  - AI 与成长：AI 助手、成长看板
- 增加“今日 AI 建议”侧栏卡片。
- 移动端增加 5 项底部导航：首页、任务、学习、AI、我的。
- 隐藏深色侧栏中的系统滚动条，保留滚动能力。

### 4. Notes 页面二次设计

文件：`app/(app)/notes/page.tsx`

改动：

- 从列表页升级为“AI 学习内容库”。
- 增加大首屏 Hero，明确价值：把零散内容整理成可复习资产。
- 增加三项数据卡：笔记、知识点、AI 建议。
- 增加搜索、学科筛选、AI 生成两种模式。
- 重做 AI 生成面板，包含：
  - 学科选择
  - 原文输入
  - 知识点 / 闪卡 / 复习安排说明
  - 自然 loading 文案
  - 成功 / 错误反馈
- 增加右侧辅助区：
  - 今日整理建议
  - 知识资产流转

### 5. Dashboard 首屏二次设计

文件：`app/(app)/dashboard/page.tsx`

改动：

- 从指标陈列升级为“今日焦点”体验。
- 首屏明确告诉用户今天应该轻量推进 3 件事。
- 增加本周目标进度卡。
- 增加四项关键指标：今日计划、预计投入、连续学习、AI 辅助。
- 增加 AI 建议的下一步，解释每个任务为什么值得做。
- 增加学习路径预览，表达长期成长方向。
- 保留已有 TodayTasks、Heatmap、WeeklySummary、MasteryRing、SubjectProgress，降低改动风险。

### 6. Logo 修复仍保留

文件：`components/ui/turbine-logo.tsx`

- 保留此前从品牌线稿提取的四叶涡轮复合 SVG path。
- 继续使用 `currentColor`，跟随主题色变化。

## 浏览器验证

已在 in-app browser 验证：

- `http://localhost:3000/notes`
- `http://localhost:3000/dashboard`

结果：

- 页面可正常渲染。
- 新主题色、侧栏分组、Notes 工作台、Dashboard 今日焦点均生效。
- 深色侧栏滚动条视觉问题已处理。

## 当前检查状态

`npm run lint` 仍失败，但失败来自既有文件，不是本次新增页面：

- `app/(app)/guidance/page.tsx`：未转义引号、未使用 Card imports。
- `components/auth/auth-guard.tsx`：React hooks set-state-in-effect 规则。
- 多个页面存在既有 unused imports warning。

`npx tsc --noEmit` 仍失败，失败来自既有类型问题：

- `app/(app)/flashcards/page.tsx`
- `components/dashboard/mastery-ring.tsx`

## 后续建议

Phase 2 优先级：

1. 重做 AI Agent 页面，把 `/guidance` 从聊天页升级为 AI 工作台。
2. 重做 Tasks 页面，去掉 emoji 类型图标，增加 Focus Now 和 AI 重排预览。
3. 修复现有 lint/tsc 阻断，让后续每次设计迭代有干净验证基线。
4. 新增 Learning Path 页面，承接 Dashboard 的“学习路径预览”。
