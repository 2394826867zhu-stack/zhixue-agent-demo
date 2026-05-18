# 知曜前端 UI/UX V2 归档方案

归档时间：2026-05-17
适用仓库：`zhiyao-frontend`
当前基础：Next.js 16 / Tailwind v4 / shadcn/ui / TypeScript
设计目标：在现有 9 个功能页面基础上，重构为“学习友好 + AI 协作 + 低压力成长”的高质量 App 体验。

## 1. 整体设计方向

### 产品气质

知曜不是传统学习工具，也不是儿童化激励产品。它应该像一个“可靠的学习搭子 + 轻量 AI 执行助理”：

- 清晰：用户一进入页面就知道今天该做什么。
- 可靠：结构、反馈、状态稳定，不让用户觉得 AI 黑箱或不可控。
- 轻松：减少压迫性 KPI，更多使用“建议、陪伴、阶段进步”表达。
- 有陪伴感：AI 以“提醒、拆解、复盘、鼓励”的方式出现，而不是只作为聊天框。
- 可扩展：页面结构支持学习、任务、项目管理、AI 对话、个人成长看板长期扩展。

### 设计关键词

大厂质感 / 学习友好 / 轻量科技 / 清晰高效 / 温暖陪伴 / 低压力成长 / AI 协作 / 模块化 / 年轻化 / 长期留存

### 方向判断

当前版本功能完整，但视觉层更像 MVP 原型：卡片和列表已具备，缺少强首页结构、AI 工作台概念、成长路径叙事、统一状态反馈和情绪层。V2 应优先做“信息架构 + 组件系统 + 核心页面重排”，而不是只换颜色。

## 2. 品牌色和辅助色建议

### 推荐主方案：Aurora Mint

适合“清晰、可靠、轻松、有陪伴感”，比荧光紫更适合长期学习产品。

```css
--primary: oklch(0.70 0.16 170);              /* 柔亮薄荷青 */
--primary-foreground: oklch(0.12 0.025 180);
--background: oklch(0.985 0.006 170);
--foreground: oklch(0.16 0.018 245);
--sidebar: oklch(0.12 0.028 245);             /* 深海蓝黑 */
--sidebar-primary: oklch(0.74 0.16 170);
--accent: oklch(0.94 0.030 170);
--ring: oklch(0.70 0.16 170);
```

### 备选主方案：Soft Aurora Purple

适合更强 AI 科技感，但要避免刺眼和夜店感。

```css
--primary: oklch(0.68 0.20 295);              /* 柔和极光紫 */
--primary-foreground: oklch(0.99 0.006 295);
--background: oklch(0.986 0.006 295);
--foreground: oklch(0.15 0.018 270);
--sidebar: oklch(0.10 0.028 275);
--sidebar-primary: oklch(0.75 0.22 295);
--accent: oklch(0.94 0.030 295);
--ring: oklch(0.68 0.20 295);
```

### 辅助色

- Success：`oklch(0.70 0.16 145)`，用于完成、掌握、连续打卡。
- Warning：`oklch(0.78 0.16 78)`，用于待复习、即将过期、建议关注。
- Info：`oklch(0.70 0.14 225)`，用于 AI 解释、系统信息、知识链接。
- Growth Purple：`oklch(0.68 0.18 295)`，用于成就、路径阶段、AI 能力点。
- Error：保留 shadcn destructive，但降低面积，只用于错误和危险操作。

### 色彩原则

- 主色只用于关键行动、当前状态、AI 强提示、进度主轨。
- 页面大面积背景使用浅灰白，不使用重黑科技风。
- 学科色可保留多色，但全部降饱和，避免和品牌主色抢层级。
- 不用纯渐变堆叠制造“科技感”，只在关键反馈卡片或 AI 状态中轻量使用。

## 3. 字体、圆角、阴影、间距规范

### 字体

- 中文：优先系统字体 `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif`
- 数字：使用 `font-variant-numeric: tabular-nums`
- 标题：600-700，避免过粗。
- 正文：14-16px，行高 1.55。
- 辅助说明：12-13px，必须保持可读，不低于 12px。

### 字号层级

- Page Title：24px / 32px，font-weight 700
- Section Title：18px / 26px，font-weight 650
- Card Title：15-16px / 22px，font-weight 650
- Body：14px / 22px
- Meta：12px / 18px
- Label：13px / 18px，font-weight 500

### 圆角

- Page container / large panel：16px
- Card：14px
- Button / input / filter：10-12px
- Badge / pill：999px
- Icon tile：12px

### 阴影

使用轻阴影，避免浮夸：

```css
--shadow-card: 0 1px 2px oklch(0 0 0 / 4%), 0 8px 24px oklch(0 0 0 / 4%);
--shadow-popover: 0 8px 32px oklch(0 0 0 / 10%);
--shadow-focus: 0 0 0 4px color-mix(in oklch, var(--primary) 16%, transparent);
```

### 间距

- 页面外边距：mobile 16px，desktop 32px。
- 卡片内边距：mobile 16px，desktop 20-24px。
- Section 间距：24px。
- 卡片 grid gap：16px / 20px。
- 表单项间距：12px。
- 图标和文字间距：8px。

## 4. 首页 Dashboard 完整 UI 结构

目标：打开首页后，用户马上知道“今天该做什么、AI 帮我做了什么、我的成长在哪里”。

### 页面布局

```txt
DashboardPage
  AppShell
    PageHeader
      GreetingBlock
        title: 早上好，Demo
        subtitle: 今天建议完成 3 个轻任务，预计 42 分钟
      PrimaryAction
        Button: 让 AI 安排今天
    TodayFocusPanel
      CurrentGoalCard
        goal: 本周目标
        progress: 64%
        nextMilestone: 再完成 2 次复习可达成
      NextBestActionCard
        icon: Sparkles
        title: AI 建议先复习“牛顿三定律”
        reason: 昨天错题关联 3 个知识点，遗忘风险较高
        actions: 开始复习 / 稍后
    MainGrid
      LeftColumn
        TodayTasksCard
          progressHeader
          taskList
          completionFeedback
        LearningPathPreview
          currentStage
          nextNodes
      RightColumn
        CompanionCard
          AI avatar
          dailyMessage
          quickPrompts
        StatsMiniCards
          streak
          mastery
          focusMinutes
    InsightBand
      WeeklySummary
      HeatmapLite
```

### 核心交互

- “让 AI 安排今天”：进入轻量 loading，显示 3 阶段文案：分析复习记录 / 匹配薄弱点 / 生成今日计划。
- 完成任务：卡片局部动效，出现“已完成，下一步建议...”。
- 今日任务为空：显示低压力空状态：“今天可以轻一点”，给出复习、整理、自由问答三个入口。
- AI 建议卡片必须解释原因，避免用户觉得 AI 随机推荐。

## 5. AI Agent 页面结构

目标：从“聊天窗口”升级为“AI 协作工作台”。

### 页面定位

当前 `/guidance` 是苏格拉底式问答。V2 建议改名为 `/agent` 或在导航显示“AI 助手”，并将引导问答作为 Agent 的一种模式。

### 页面布局

```txt
AgentWorkspacePage
  WorkspaceHeader
    title: AI 学习助手
    modeTabs: 引导问答 / 生成计划 / 拆解任务 / 复盘总结
    statusChip: 已连接学习记录
  ThreePanelLayout
    LeftContextPanel
      SubjectSelector
      RecentSessions
      KnowledgeContext
      PinnedGoals
    CenterConversationPanel
      AssistantIntroCard
      MessageTimeline
        AssistantMessage
        UserMessage
        ToolExecutionMessage
      Composer
        input
        attachment
        promptSuggestions
        sendButton
    RightActionPanel
      AISuggestionCards
        建议复习
        建议生成闪卡
        建议拆解任务
      ExecutionStatus
        queued/running/done/error
      OutputArtifacts
        note
        task plan
        flashcards
```

### 移动端结构

- 默认只显示中间对话区。
- 顶部提供 Context 抽屉按钮。
- AI 建议以底部卡片横滑展示。

### 关键交互

- 输入区支持 prompt chips：解释概念 / 帮我出题 / 拆成任务 / 复盘今天。
- AI 生成时不只显示 spinner，而显示“正在整理你的上下文...”的自然状态。
- 工具执行要有状态条：准备中 / 执行中 / 已完成 / 需要确认。
- 生成结果可以“保存为笔记 / 加入今日任务 / 生成闪卡”。

## 6. 学习路径页面结构

目标：参考多邻国路径感，但更成熟，不幼稚。

### 页面布局

```txt
LearningPathPage
  PageHeader
    title: 成长路径
    subtitle: 按阶段推进，不用一次学完所有内容
    subjectFilter
  PathOverview
    CurrentStageCard
      stageName
      progress
      nextUnlock
    StreakAndBadges
  PathTimeline
    StageSection
      StageHeader
        stageTitle
        stageDescription
        stageProgress
      PathNodeList
        NodeCard
          type: lesson/review/training/project
          status: locked/current/done/review
          title
          estimateTime
          reward
          CTA
  RightPanelDesktop
    AIPathCoach
      当前卡点
      推荐下一步
      调整难度
```

### 节点状态

- Done：柔和绿色 + check。
- Current：主色描边 + 轻微发光。
- Review：浅橙色，提示“建议回看”。
- Locked：低对比灰色，说明解锁条件。

### 交互

- 点击节点打开 LessonPreviewDrawer。
- 完成节点后出现轻量成就反馈，不全屏打断。
- AI 可以重排路径，但必须显示“为什么这样安排”。

## 7. 任务管理页面结构

目标：比项目管理软件轻，比普通 todo 更智能。

### 页面布局

```txt
TasksPage
  PageHeader
    title: 今日任务
    subtitle: AI 已按精力和优先级排好顺序
    actions: AI 重排 / 新建任务
  DailyPlanCard
    progress
    estimatedTotalTime
    energyLevelSelector
  TaskBoard
    FocusNowColumn
      NextTaskCard
    QueueColumn
      TaskList
    DoneColumn
      CompletedList
  PomodoroPanel
    currentTaskBinding
    timer
    sessionCount
  AIAssistPanel
    autoSplitSuggestion
    blockedTaskHint
```

### 任务卡片规范

```txt
TaskCard
  LeadingStatusButton
  Content
    title
    meta: subject / estimate / source
    aiReason(optional)
  Actions
    start
    defer
    more
```

### 交互

- 完成任务：卡片收起进入 Done，进度条平滑更新。
- AI 重排：先显示对比摘要，不直接打乱用户列表。
- 任务拆解：大任务显示“可拆成 3 步”，点击展开。
- 番茄钟可绑定当前任务，完成一个番茄后建议下一步。

## 8. 个人中心 / 数据看板结构

目标：激励持续使用，不制造焦虑。

### 页面布局

```txt
ProfileInsightsPage
  ProfileHeader
    avatar
    name
    currentGoal
    editGoal
  GrowthStats
    streakDays
    weeklyCompletion
    focusMinutes
    aiAssists
  AchievementShelf
    badges
    recentMilestones
  PersonalTrends
    learningHeatmap
    masteryTrend
    subjectBalance
  AIUsageReview
    savedNotes
    generatedTasks
    guidanceSessions
    mostHelpfulAgentMode
  ReflectionCard
    weeklyReflectionPrompt
    saveReflection
```

### 交互

- 数据文案以鼓励为主：“你已经连续 5 天回到学习节奏”，避免“落后”“失败”等压迫词。
- 周报默认折叠详细数据，先展示结论和建议。
- 徽章不使用过度卡通，采用简洁图标 + 柔和底色。

## 9. 组件规范

### Button

Variants：

- Primary：关键行动，如生成计划、开始复习。
- Secondary：普通行动，如查看详情。
- Soft：低压力建议，如稍后、换一个建议。
- Ghost：导航和轻操作。
- Danger：删除、退出、清空。

尺寸：

- sm：32px，高密度区域。
- md：40px，默认。
- lg：48px，移动端关键 CTA。

交互：

- hover：背景加深 4-8%，不改变尺寸。
- active：scale 0.98，duration 120ms。
- loading：保留按钮宽度，显示自然文案。

### Card

类型：

- MetricCard：顶部指标，少量文字 + 大数字。
- ActionCard：带 CTA 的任务/建议卡。
- ContentCard：笔记、知识点、任务详情。
- CoachCard：AI 建议和解释。
- EmptyStateCard：空状态引导。

规范：

- 默认 `rounded-[14px]`
- border 使用 `border-border/80`
- hover 只用于可点击卡片：`hover:border-primary/30 hover:shadow-card`
- 不嵌套卡片，复杂内容改用 section 或 panel。

### Input / Textarea

- 高度：input 44px，textarea min 96px。
- focus：`ring-4 ring-primary/15 border-primary/40`
- placeholder 要具体，例如“粘贴一段课本内容，AI 会提炼知识点”。
- 错误提示在字段下方，不只放 toast。

### Tag / Badge

用途：

- 学科标签：低饱和多色。
- 状态标签：Done / Review / New / AI Generated。
- 能力标签：AI 拆解 / 可复习 / 已同步闪卡。

规范：

- `rounded-full`
- 高度 24-28px
- 文字 12px / 500

### Progress

类型：

- Linear progress：任务完成、阶段进度。
- Ring progress：掌握率、今日目标。
- Path progress：成长路线。

原则：

- 进度条旁边必须有解释性文案。
- 不用红色表达学习进度落后。
- 满进度触发轻量完成反馈。

### Modal / Drawer

- 移动端优先用 Bottom Sheet。
- 桌面端用右侧 Drawer 查看详情，减少离开当前上下文。
- 需要确认的 AI 执行动作用 Dialog，例如“AI 将新增 5 个任务”。

### Navigation

桌面：

- 左侧 sidebar 保留，但分组：
  - 今日：首页、每日任务
  - 学习：笔记、知识点、闪卡、训练、错题
  - AI：AI 助手、成长路径、进度

移动端：

- 底部导航最多 5 个：首页、任务、学习、AI、我的。
- 其余页面放入“学习”聚合页或更多菜单。

## 10. 可直接交给前端开发的页面布局说明

### AppShell 改造

目标：统一桌面和移动端导航。

建议文件：

- `components/layout/app-shell.tsx`
- `components/layout/sidebar.tsx`
- `components/layout/mobile-nav.tsx`
- `components/layout/page-header.tsx`

结构：

```tsx
<AppShell>
  <Sidebar />
  <MobileHeader />
  <main className="min-h-dvh bg-background md:pl-64">
    <PageContent />
  </main>
  <MobileBottomNav />
</AppShell>
```

### Dashboard 开发拆分

建议组件：

- `components/dashboard/today-focus-panel.tsx`
- `components/dashboard/ai-coach-card.tsx`
- `components/dashboard/next-action-card.tsx`
- `components/dashboard/growth-path-preview.tsx`
- `components/dashboard/metric-card.tsx`

优先级：

1. 重排 Header + TodayFocusPanel。
2. 重做 TodayTasks 为“下一步行动”。
3. 将 WeeklySummary 改为 AI Coach Card。
4. 保留 Heatmap 和 MasteryRing，但降低首屏权重。

### AI Agent 页面开发拆分

建议组件：

- `components/agent/agent-mode-tabs.tsx`
- `components/agent/context-panel.tsx`
- `components/agent/conversation.tsx`
- `components/agent/composer.tsx`
- `components/agent/execution-status.tsx`
- `components/agent/suggestion-card.tsx`

优先级：

1. 保留现有消息逻辑。
2. 将左侧学科过滤升级为上下文面板。
3. 增加右侧 AI 建议和执行状态。
4. 移动端用 Drawer 收纳左右面板。

### Learning Path 新页面

建议路由：`app/(app)/path/page.tsx`

建议组件：

- `components/path/path-stage.tsx`
- `components/path/path-node.tsx`
- `components/path/stage-progress.tsx`
- `components/path/achievement-badge.tsx`
- `components/path/path-coach-card.tsx`

数据结构：

```ts
type PathNodeStatus = "locked" | "current" | "done" | "review";
type PathNodeType = "lesson" | "review" | "training" | "project";

interface PathNode {
  id: string;
  title: string;
  type: PathNodeType;
  status: PathNodeStatus;
  estimateMinutes: number;
  reward?: string;
}
```

### Tasks 页面开发拆分

建议组件：

- `components/tasks/daily-plan-card.tsx`
- `components/tasks/task-card.tsx`
- `components/tasks/task-board.tsx`
- `components/tasks/pomodoro-panel.tsx`
- `components/tasks/ai-reorder-preview.tsx`

优先级：

1. 去掉 emoji 类型图标，改用 lucide。
2. 增加 Focus Now 卡片。
3. AI 重排先显示 preview。
4. 番茄钟绑定当前任务。

### Profile / Insights 新页面

建议路由：`app/(app)/profile/page.tsx`

建议组件：

- `components/profile/profile-header.tsx`
- `components/profile/growth-stats.tsx`
- `components/profile/achievement-shelf.tsx`
- `components/profile/personal-trends.tsx`
- `components/profile/ai-usage-review.tsx`
- `components/profile/reflection-card.tsx`

### 设计实施分期

Phase 1：设计系统落地

- 更新 `app/globals.css` 主题 token。
- 统一 `Button/Card/Badge/Progress/Input` 组件。
- 重构 Sidebar 分组和 Mobile Bottom Nav。

Phase 2：首页和 AI 页面

- Dashboard 改为 Today Focus 架构。
- Guidance 改为 AI Agent Workspace。
- 增加自然 loading、生成完成反馈、AI 建议卡。

Phase 3：成长和留存

- 新增 Learning Path。
- 新增 Profile / Insights。
- 重做 Tasks 为轻量任务板。

Phase 4：细节打磨

- 空状态插画。
- 完成任务反馈动效。
- 移动端 Bottom Sheet。
- 可访问性检查：键盘、焦点、对比度、屏幕阅读器标签。

## 验收标准

- 首屏 5 秒内用户能理解今天要做什么。
- 每个 AI 输出都能被保存、转任务或继续追问。
- 移动端无横向滚动，核心 CTA 在拇指可触范围。
- 关键操作有明确 loading、success、error 状态。
- 卡片不互相嵌套，信息层级清晰。
- 主题色不刺眼，连续使用 20 分钟不疲劳。
- 页面结构支持后续学习、项目、任务、AI 多模块扩展。
