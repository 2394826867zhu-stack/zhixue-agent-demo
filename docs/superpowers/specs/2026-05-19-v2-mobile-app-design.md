# 知曜 V2 移动端前端设计方案

日期：2026-05-19
状态：已由用户逐段确认，待实施计划
适用范围：`zhiyao-mobile-app`、`zhiyao-gamification-lab`、现有 `zhiyao-frontend` 作为参考来源

## 1. 产品方向

V2 的主线从现有 Next.js Web 前端切换为 Expo / React Native 移动 App，目标优先适配移动端并支持后续商店上线。现有 `zhiyao-frontend` 不作为 V2 主开发承载，只作为业务逻辑、API 封装、页面经验、视觉审计记录和可复用模式的参考来源。

V2 的核心定位是 Agent-first Learning OS。Agent 是第一服务模块，不是一个普通聊天入口。学习 OS 提供课程、任务、StudySpace、Focus、成长资产和奖励系统；Agent 贯穿这些模块，负责解释、引导、反馈和陪伴。

已锁定原则：

- 主技术路线：Expo / React Native。
- 首页形态：系统中枢型，Agent 首屏第一位，同时露出任务、学习和反馈资产。
- Agent 形象：伪 3D / 低面体卡通小女孩 Avatar。
- 底部导航：首页 / 任务 / 学习 / 我的。
- Focus 模式入口：学习 Tab 内。
- 视觉比例：Apple 80% + Duolingo 20%。
- 第一阶段方案：主 App 与 Gamification Lab 双核心均衡推进。
- 第一阶段验收：能点通主流程，而不是只做静态 UI。

## 2. 工程边界

V2 建议拆成两个并行工程。

```txt
zhiyao-mobile-app/
  app/ 或 src/
  features/home/
  features/learn/
  features/studyspace/
  features/tasks/
  features/profile/
  features/agent/
  shared/api/
  shared/ui/
  shared/motion/
  shared/theme/

zhiyao-gamification-lab/
  apps/demo-expo/
  packages/reward-engine/
  packages/avatar-kit/
  packages/ui-rewards/
```

主 App 第一阶段只跑一条核心闭环：首页 Agent 中枢 -> 学习 Tab -> 课程浏览器 -> StudySpace -> 完成课时 -> 获得知星/奖励反馈 -> 我的页看到余额和装备状态。

Gamification Lab 第一阶段跑一条奖励闭环：模拟学习事件 -> 获得知星/经验/稀有道具进度 -> 商店购买 -> 装备到低面体 Agent -> 动效反馈。Lab 是未来接回主 App 的 reward engine 和 Avatar kit 试验场，不是一次性原型。

后端适配策略：主 App 直接对接现有 v0.20 API，优先使用 `/curriculum`、`/studyspace`、`/agent`、`/stars`、`/cosmetics`、`/tasks`。Lab 中验证出的等级、稀有度、任务链、连续奖励规则先 mock，稳定后再写入 `SPEC.md` Section 3 请求后端支持。

## 3. 信息架构

V2 主 App 保持 4 Tab：首页 / 任务 / 学习 / 我的。Agent 不单独占 Tab，因为它不是一个页面功能，而是贯穿全局的服务角色。

首页是 Agent-first 系统中枢。首屏 35-45% 给低面体 Agent、Agent 今日发言、主行动按钮；下方露出静默数据与下一步入口，例如今日学习时间、连续天数、待复习数量、下一项任务。首页不做传统 dashboard，不堆图表，不让数据抢过 Agent。

任务页负责“今天要做什么”。采用时间轴或轻量任务队列，区分 `system` 和 `user` 任务。系统任务不能被用户随手标记完成，必须通过对应学习行为自动完成。番茄钟可以在任务页作为普通计时能力存在，但 Focus 模式不从这里主推。

学习页是 V2 的核心入口，包含课程浏览器、StudySpace 入口、Focus 模式入口。闪卡、训练、笔记、知识点不作为一级 Tab，而是作为课程/StudySpace 内的工具流出。学习页承担“我现在学哪一课、进入哪个空间”的决策。

我的页负责成长资产和个性化：低面体 Agent 展示、知星余额、等级、连续奖励、成就、装备状态、商店入口。我的页是 Gamification Lab 成果回灌的主要落点，但视觉仍保持 Apple 80%，避免变成游戏大厅。

全局 Agent 在首页是主角，在 StudySpace 是老师/陪伴者，在通知中是唯一说话者，在完成/奖励时负责反馈。系统本身不说话，提示语尽量转成 Agent 口吻。

## 4. 视觉语言与反馈原则

V2 视觉比例为 Apple 80% + Duolingo 20%。日常界面以 iOS 系统感为骨架：干净层级、底部 Tab、原生 Sheet、柔和材质、清晰触控反馈、稳定字体和克制色彩。Duolingo 式反馈只在关键学习成果出现：完成课时、闪卡连续正确、知识卡升级、获得知星、解锁装备、保持连续学习。

主色建议从 v1 的 Aurora Mint 延续，但降低大面积存在感，用作焦点、进度、Agent 状态和主行动。背景以浅色系统 surface 为主，局部使用材质感和轻微景深。避免大面积紫蓝渐变、扁平卡片海和儿童化糖果界面。

所有动效必须表达因果：点击后发生什么、Agent 为什么反应、知识卡为什么升级、奖励从哪里来。页面切换使用 iOS 式空间连续性；按钮按压 80-150ms 内反馈；Sheet、卡片、Tab 切换使用 spring；复杂动效不超过 400ms；支持 reduced motion。

Agent 是伪 3D / 低面体卡通小女孩，状态包括 idle、thinking、speaking、focus、celebrate、remind、sleepy、confused。装备槽位包括 material、accessory、aura、voice。第一阶段允许使用简化低面体模型或 2.5D 占位，但数据结构必须按最终装备槽位设计。

## 5. 核心功能框架

### 首页

首页包含低面体 Agent、今日发言、“开始今日学习”主按钮和三个静默状态指标。首页只展示最少但关键的信息：下一步、待复习、连续/知星。未读通知作为 Agent 气泡出现，不使用系统 Toast 语气。

### 学习页

学习页包含课程浏览器、StudySpace 入口、Focus 模式入口。课程按学科 Tab 展示，课时状态包括 locked、available、in_progress、completed。

Focus 模式放在学习页内，不占一级导航，风格更安静、更沉浸，内部只保留番茄钟和 Agent 陪伴。

### StudySpace

StudySpace 是混合型学习空间：课程课时为主线，Agent 主导节奏，用户可随时上传资料、提问、打开画板、生成闪卡/练习。完成课时后触发知识点提取、闪卡生成、知星奖励、下一课时解锁。它是 V2 的核心服务模块。

### 知识点卡片

知识点卡片颜色由 Agent 综合优先级决定：金卡、紫卡、蓝卡。依据包括难度、重要度、掌握度、遗忘风险、考试关联、错题关联。每张卡必须显示 Agent 解释短句，颜色不能作为唯一信息。卡片升级时触发轻量动效。

### 闪卡

闪卡不作为一级入口，主要从 StudySpace、知识卡、Agent 提醒中流出。流转采用强反馈学习型：翻卡、评分滑动、连击、Agent 反应、轻量结算。目标是让复习有正反馈，但不变成重关卡。

### 番茄钟 / Focus

番茄钟动效为安静专注型。Focus 模式中 Agent 陪伴但少说话，使用呼吸光、柔和倒计时、低干扰背景。完成时才出现知星奖励和 Agent 小庆祝。任务页可有基础番茄钟，但 Focus 主入口在学习页。

### 奖励与商店

主 App 第一阶段接入知星余额、获得动画、装备展示、商店入口。强游戏化完整规则在 Gamification Lab 先跑：等级、稀有度、任务链、连续奖励、Avatar 成长、商店活动。稳定后再回灌主 App。

## 6. 第一阶段开发流程

第一阶段采用双核心均衡：主 App 与 Gamification Lab 并行推进，但范围严格控制。

主 App 第一阶段目标是点通核心闭环：登录/身份准备 -> 首页 Agent 中枢 -> 学习 Tab -> 课程浏览器 -> 创建 StudySpace 会话 -> Agent 对话/课时空间 -> 完成课时 -> 获得知星/奖励反馈 -> 我的页看到余额和装备状态。页面只做首页、任务、学习、StudySpace、我的，不迁移 v1 的全部功能页。

Gamification Lab 第一阶段目标是跑通奖励闭环：模拟学习事件 -> 获得知星/经验 -> 等级/稀有度变化 -> 商店购买 -> 库存展示 -> 装备到低面体 Agent -> 奖励动效反馈。Lab 采用 Expo Demo App + 内部 packages，避免规则散落在页面里。

开发顺序：

1. 建立两个项目骨架和共享设计 token。
2. 建立 API/Mock 层。
3. 主 App 完成 4 Tab、首页、学习页、StudySpace 壳。
4. 主 App 接入完成课时奖励反馈和我的页资产展示。
5. Lab 完成 reward-engine 数据结构。
6. Lab 完成 demo 页面、Avatar 装备展示和奖励动效。
7. 对齐主 App 与 Lab 的奖励数据结构，决定需要写入 `SPEC.md` 的后端需求。

## 7. 验收标准

主 App 必须能在手机视口完成一条学习闭环；关键点击都有即时反馈；StudySpace 完成后有知星/解锁反馈；首页 Agent 一号位明确；Focus 入口在学习页内；知识卡颜色规则可解释；闪卡和番茄钟有明确动效方向。

Gamification Lab 必须能独立运行 demo，且 `reward-engine`、`avatar-kit`、`ui-rewards` 边界清晰，未来能回灌主 App。

第一阶段不追求迁移 v1 全部页面，不追求完整 3D 资产，不追求 Lab 规则直接落后端。第一阶段的成功标准是 Agent、StudySpace、奖励系统三个核心齿轮能一起转起来。

## 8. 风险控制

低面体 Agent 资产复杂度可能拖慢进度，所以第一阶段允许用简化低面体模型或 2.5D 占位实现，但数据结构必须按最终装备槽位设计。

强游戏化不能挤压学习主流程。奖励反馈必须短、清晰、可跳过，不能阻断继续学习。

后端未覆盖的等级、稀有度、任务链、连续奖励先在 Lab mock，不立即污染主 App API。规则稳定后，由前端在 `SPEC.md` Section 3 记录新增需求，再交由后端实现。

现有 `zhiyao-frontend` 中的未提交改动不属于本设计文档范围，不在本次工作中修改或回滚。
