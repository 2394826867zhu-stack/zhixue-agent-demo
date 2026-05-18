# 前端用户层视觉巡检归档

日期：2026-05-18  
环境：`http://127.0.0.1:3000`，Codex in-app browser 侧栏可视化巡检  
视口：移动侧栏视口（约 700x700）  
原始记录：`docs/qa/frontend-user-visual-audit-2026-05-18.json`  
截图目录：`docs/visual-audit-2026-05-18/`

## 结论摘要

本轮从注册页开始，随后通过 demo 登录进入核心功能页，逐页进行视觉级点击巡检。注册、训练、图表容器和移动端首屏加载体验是优先修复对象。

## 已确认可用

- 登录：`demo / zhiyao2025` 可进入 `/dashboard`。
- Onboarding：年级按钮可点击，移动端布局可读。
- 笔记页：`AI 生成` tab 可切换。
- 训练页：学科按钮和 `开始训练` 按钮可点击。
- 进度页：移动端学习热力图可见，底部导航可见。

## 问题清单

### P1 - 注册失败且错误不可自救

现象：注册页填写用户名、年级、密码后，`注册并开始学习` 按钮可点击，但停留在 `/register` 并显示「注册失败，请稍后重试」。

初判：前端注册表单使用“用户名”作为主输入，但后端注册协议可能需要 `email` / `username` / `grade` 的特定组合；当前错误文案没有透出后端 detail，用户无法知道是字段格式、账号冲突还是服务错误。

截图：`docs/visual-audit-2026-05-18/05-onboarding.png` 前序注册失败后改用 demo 登录继续。

### P1 - 训练核心链路无法进入答题

现象：进入 `/training` 后点击 `开始训练`，页面显示「还没有可训练题目。先在笔记页生成笔记或知识点，再回来开始训练。」没有进入答题流。

初判：demo/真实数据分支可能没有把已有知识点传给训练生成；也可能是 `startTraining` 请求体与后端期望不一致。该问题会阻断“学习 → 训练 → 错题沉淀”的核心闭环。

截图：`docs/visual-audit-2026-05-18/17-training-started.png`

### P2 - 受保护页面首屏容易出现长时间 spinner

现象：Dashboard、Notes 等页面在巡检截图中多次出现整屏加载 spinner，等待后才进入具体内容。

初判：AuthGuard / onboarding gate / React Query 初始状态在移动视口下给用户的反馈过少。若接口或 rehydrate 慢，用户会以为页面卡死。

截图：`docs/visual-audit-2026-05-18/01-dashboard.png`

### P2 - 图表容器 Recharts 尺寸警告

现象：浏览器 console 出现 `The width(-1) and height(-1) of chart should be greater than 0`。

初判：ResponsiveContainer 父容器初次布局没有稳定尺寸，可能导致图表首屏空白、抖动或 dev overlay。

截图：`docs/visual-audit-2026-05-18/29-progress-visible.png`

### P2 - 移动端 Next dev issue badge 影响视觉判断

现象：进度页右上角显示红色 `1 Issue` dev overlay。

初判：由 console warning 触发，不是生产 UI，但会干扰开发态视觉巡检；根因仍是图表尺寸 warning。

### P3 - 全局 Agent 快捷动作语义不完整

现象：`上传资料` 和 `语音` 有明确反馈；`生成 quiz` / `成绩分析` 视觉上是按钮，但没有明显动作反馈。

初判：QUICK_ACTIONS 中仍有部分按钮缺 handler。建议点击后自动填入 prompt 或跳转到训练/进度页。

### P3 - 任务页番茄钟入口移动端不够靠前

现象：移动视口下高频的番茄钟操作不在首屏明显区域。

初判：任务页信息密度和操作优先级需要按移动端重排，建议把今日专注入口作为固定小模块或首屏 CTA。

## 建议归档

1. 注册页：显示后端错误 detail；若需要 email，UI 文案改为「邮箱/用户名」或拆成两个字段。
2. 训练页：在开始训练前检查可用知识点数量，并说明“当前学科暂无可训练知识点”；若 demo 模式应保证至少一条可答题路径。
3. 全局图表：给 Recharts 父容器统一 `min-height` / `min-width: 0` / skeleton，消除 dev overlay。
4. Agent 快捷动作：`生成 quiz` 自动填入「根据我的薄弱知识点生成 5 道 quiz」并发送或跳训练；`成绩分析` 跳转 `/progress` 或发起分析 prompt。
5. QA：把本轮脚本沉淀为每日冒烟清单：注册、登录、onboarding、dashboard CTA、笔记生成、训练开始、错题重练、任务/番茄钟、路径重排、AI 浮标。

