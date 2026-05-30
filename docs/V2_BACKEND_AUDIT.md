# 知曜 V2 后端 · PRD 审计 + Gap 分析 + 开发流程图

> **审计时间**：2026-05-23
> **基础**：`v2-prd-memory.md` 全部 714 行逐字审计
> **当前代码**：22 routers · 25 services · 19 models · 17 migrations · FastAPI 0.115 + Postgres + Redis + Celery

---

## A. PRD v2 → 后端必须支持的能力清单

### A.1 用户体系
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 新用户引导（行 47-55） | Agent 对话式建模 → 自动生成项目/周期/初始 SS | 🟡 onboarding 有，但未对接项目自动生成 |
| 我的页 AB 结合（行 200-203） | 账户/偏好/通知/外观 + 成长档案 + Agent 关系 | 🟢 profile + checkin + stars 已覆盖 |
| Token 配额（既有） | DEFAULT_DAILY_TOKEN_LIMIT | 🟢 user_quota + token_usage 完成 |

### A.2 学习工作台 / 项目系统 ★ v2 核心新增
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 项目 CRUD（行 313-327）| 创建 / 列表 / 编辑（仅名+简介）/ 删除（系统弹窗确认）/ 左滑菜单 | 🔴 **完全缺失** |
| 项目排序（行 319） | 用户拖动排序 | 🔴 **完全缺失** |
| 项目创建 Agent 对话（行 327-339）| 收集名/简介/提示词/进度/截止/大事件/每周投入 → 结构化预览卡 → 用户确认 → Agent 生成项目骨架 | 🔴 **完全缺失** |
| 项目时间线（行 379-386）| 阶段节点 + 关键事件，横向滑动，当天居中偏左 | 🔴 **完全缺失** |
| 项目树状路径（行 388-426）| 树状 + 路径高亮，节点蓝/紫/金，节点点击玻璃气泡 | 🔴 **完全缺失** |
| 节点完成度+掌握度分离（行 408-410）| 完成度=学习推进、掌握度=测验结果，环状图汇总 | 🟡 字段缺失，逻辑可加 |
| 项目嵌入子界面（行 397）| 子课程层级 / 重要性 / 学习进度 | 🔴 缺失 |

### A.3 StudySpace
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 学习流程（行 431-435 / 9.3 行 632）| 路线图→知识点→讲解→测验→总结 | 🟡 studyspace_service 有基础流程，缺阶段细化 |
| 垂直时间线节点（行 436-443）| 学习内容/知识点/闪卡/训练/错题/复盘/Agent对话痕迹 | 🟡 模型有 session，缺时间线节点 |
| 编辑权限（行 444-448）| 笔记/知识点/复盘可编辑，训练/错题不可改写 | 🟡 字段需加 is_editable |
| 画板/手写区（9.3 行 636）| 保留 | 🔴 缺失 |
| 中途退出保留进度（9.3 行 638）| | 🟢 session.status 已有 |
| 完成后自动归档笔记（9.3 行 634）| | 🟢 note_tasks Celery 已有 |
| 完成后自动提示测验（9.3 行 637）| | 🟡 需在 SS 结束 hook 触发 |

### A.4 测验 / 练习中心
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 课后测验 10-15 题（9.4 行 642）| | 🟢 training_service 可控 |
| 不限时（9.4 行 643）| | 🟢 |
| Agent 自动错题解析（9.4 行 644）| | 🟢 已对接 LLM |
| 组卷模式（9.4 行 645）| 选题型/题量/难度/范围 | 🟡 training 基础有，组卷端点缺失 |
| 打印（9.4 行 646）| PPT 设计 + 后续优先级 | 🔴 暂不做 |
| 题型扩展（行 415）| demo: 选择+判断；后续: 简答/证明/计算/编程/写作 | 🟡 现仅选择题 |

### A.5 复习 / 错题本 / 闪卡
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 复习入口集成闪卡流（9.5 行 650）| | 🟢 flashcards + FSRS 已有 |
| 闪卡 3 档评分（9.5 行 652）| 认识/模糊/不认识 | 🟢 fsrs_service 完整 |
| 错题按项目分类（9.5 行 653）| | 🔴 mistake 模型缺 project_id |
| 不重复生成闪卡（9.5 行 654）| 错题=知识点集合 | 🟢 |

### A.6 首页仪表盘
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 默认组件（9.6 行 658）| 学习密度 / 学习周期 / 项目进度 / 待复习 | 🟡 数据来源散落，需聚合端点 |
| 可编辑组件（3.3 行 264-285）| 长按编辑 / 拖动 / 加号 / 垃圾桶 | 🔴 **widget_config 表缺失** |
| 可添加组件清单（3.3 行 270）| 知识负荷 / Focus / 闪卡 / 课程进度 / 奖励 / 商店 / 错题 / 考试倒计时 | 🔴 |

### A.7 Agent 系统
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 双层结构（行 70-152）| 悬浮球 + 深度控制台 | 🟢 agent_service 已有对话能力 |
| Agent 工具调用（行 234-242）| 状态条 + 卡片沉淀 + 自动判断 | 🟢 agent_tools.py 已有 |
| 安全出口（行 244-248）| 重新生成 / 追加修正 / 撤销 | 🟡 需要在 endpoint 补 |
| Agent 状态库（行 167-170）| idle/thinking/speaking/focus/celebrate/reward + 后续 4 个 | 🔴 **状态字段缺失** |
| galgame 小浮窗（行 84-105）| 上方对话记录 + 下方输入 + 侧边角色 | 🟡 现仅基础对话流 |
| Agent 装扮（行 154-158 / 9.10）| 衣服/发饰/配饰/背景 + 三套服装 + 商店橱窗 | 🟡 user_cosmetics 表已有，未完整对接 |
| Agent 控制台对话搜索（9.7 行 673）| | 🔴 缺失 |
| Agent 家园栏（9.7 行 671-672）| 商店装扮入口 | 🟡 |
| Agent 浏览记录（9.7 行 669）| | 🔴 缺失 |
| Agent TTS（9.10 行 697）| | 🟢 tts_service 已有 |

### A.8 沉浸模式
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 番茄钟控制（6.1 行 372）| 开始/暂停/结束 + 自定义专注+休息+长休+循环 | 🟡 task_service pomodoro 有，需扩展自定义参数 |
| 完成反馈（6.1 行 374-376）| Agent 表情变化 + 简短反馈 + 全局学习时长入账 | 🟡 |
| 场景配置（6.1 行 576-578 / 9.9 行 685）| 书桌/房间 第一版 | 🔴 缺失 |
| BGM / 白噪音（9.9 行 686）| | 🔴 缺失 |
| 自动进入下一轮（9.9 行 687）| | 🟢 可加 |
| 横屏（9.9 行 689）| | （前端） |
| 沉浸中可问 Agent（9.9 行 688）| | 🟢 现有 agent endpoint 可复用 |

### A.9 奖励商店
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 第一版仅 Agent 装扮（行 466）| | 🟡 user_cosmetics + star_ledger 已有 |
| 三套默认服装（9.10 行 693）| 衣服/发饰/配饰/背景 | 🔴 种子数据缺 |
| 橱窗（9.10 行 695）| | 🔴 |
| 不做深入经济系统（行 470）| | OK |

### A.10 全局工具栏
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 大功能 4 入口（行 463-464）| Agent 控制台 / 沉浸模式 / 学习工作台 / 奖励商店 | 🟢 路由分别已有 |

### A.11 知识卡片颜色
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 蓝/紫/金分级（5.4 行 528-541）| 难度等级，自动着色 | 🔴 knowledge_point 缺 difficulty_tier |
| 第一版来源（行 537）| StudySpace 自动生成 | 🟡 已有提取，未着色 |
| 来源区分（行 539-540）| 官方/自主属性 | 🔴 字段缺 source_type |

### A.12 强反馈与动效
| PRD 章节 | 能力 | 当前状态 |
|---------|------|---------|
| 闪卡/番茄/奖励/卡片等强反馈 | 数据/状态/事件触发即可（前端动效） | 🟢 后端事件齐 |

---

## B. 必须新增的数据模型

```
1. projects                          ── 项目主体
2. project_phases                    ── 阶段（基础/强化/复习/冲刺 或 自定义）
3. project_milestones                ── 关键事件（考试/作业/截止/复习节点）
4. project_tree_nodes                ── 树状路径节点（蓝/紫/金 + 完成度 + 掌握度）
5. project_tree_edges                ── 节点连接（路径高亮）
6. widget_configs                    ── 用户首页可编辑组件配置
7. agent_avatar_state                ── Agent 当前形象状态 idle/thinking/etc
8. agent_browse_history              ── 控制台浏览记录
9. immersion_scenes                  ── 沉浸场景资产（含 BGM/壁纸）
10. immersion_sessions               ── 沉浸场景会话
11. studyspace_timeline_nodes        ── 学习流时间线节点
12. cosmetic_catalog                 ── 装扮商店橱窗
```

## C. 必须新增的字段

| 表 | 新字段 | 用途 |
|----|-------|------|
| knowledge_points | `difficulty_tier` ENUM('blue','purple','gold'), `source_type` ENUM('official','user_project'), `project_id` UUID NULL | 蓝紫金分级 + 来源区分 |
| notes | `project_id` UUID NULL, `source_type` ENUM('official','user_project'), `is_editable` BOOL | 项目挂载 + 编辑权限 |
| mistakes（mistake_questions）| `project_id` UUID NULL | 按项目分类 |
| flashcards | `project_id` UUID NULL | 按项目过滤 |
| studyspace_sessions | `project_id` UUID NULL, `tree_node_id` UUID NULL | 接项目树 |
| pomodoro_records | `scene_id` UUID NULL, `custom_focus_min` INT, `custom_break_min` INT, `custom_long_break_min` INT, `cycle_count` INT | 自定义番茄钟 |
| guidance_sessions | `project_id` UUID NULL | 项目内引导 |

## D. 可保留模块（v1 经验，v2 仍适用）

| 模块 | 保留理由 |
|------|---------|
| `auth_service` + JWT | 基础认证 |
| `profile_service` | 我的页结构 OK |
| `onboarding_service` | 引导流程基础，需扩 Agent 对话生成项目 |
| `curriculum_*` | 官方课程 = 项目的 official 子集 |
| `note_service` + Celery `note_tasks` | 自动笔记沉淀 |
| `knowledge_point_service` | 需扩 tier/source |
| `flashcard_service` + `fsrs_service` | FSRS 完整 |
| `training_service` | 出题基础 |
| `mistake_service` | 需扩 project_id |
| `guidance_service` | 苏格拉底引导 |
| `task_service` | 番茄钟 + 每日任务 |
| `progress_service` | 进度统计 |
| `agent_service` + `agent_tools` + `agent_context` | Agent 主体 |
| `studyspace_service` | 学习流程主体 |
| `star_service` | 奖励基础 |
| `checkin_service` | 打卡 |
| `notification_service` + Celery `notification_tasks` | 通知 |
| `tts_service` | 语音 |
| `exam_service` | 考试 |
| `admin_*` | 管理后台 |
| `score_prediction_service` | 提分预测 |

## E. 待删除 / 重组模块

| 模块 | 决定 | 理由 |
|------|------|------|
| `path_service` / `path.py` API | **合并入 project** | PRD 行 309-310 明确"学习路径不是独立入口" |
| 旧 `path` 路由 | 删除 | 同上 |
| `curriculum_import_service` | 保留但低优先级 | 可后续 |

## F. 必须新增的 Service

```
1. project_service              ── 项目 CRUD + 排序 + 挂载
2. project_tree_service         ── 树状路径生成 + 节点状态计算
3. project_timeline_service     ── 时间线阶段+事件管理
4. widget_service               ── 首页组件配置 CRUD
5. immersion_scene_service      ── 沉浸场景管理
6. cosmetic_service             ── 装扮商店（扩展 star_service）
```

## G. 必须新增的 API 端点（v2 新需求）

```
POST   /v1/projects                          创建项目
GET    /v1/projects                          项目列表（拖动排序）
GET    /v1/projects/{id}                     项目详情（含 timeline + tree）
PATCH  /v1/projects/{id}                     编辑（仅名/简介）
DELETE /v1/projects/{id}                     删除（系统确认）
POST   /v1/projects/{id}/reorder             调整排序
POST   /v1/projects/from-agent-dialog        Agent 对话式创建（预览卡 + 确认）
GET    /v1/projects/{id}/tree                树状路径
GET    /v1/projects/{id}/tree/nodes/{nid}    节点气泡详情
POST   /v1/projects/{id}/tree/nodes/{nid}/start-study   进入 SS
POST   /v1/projects/{id}/tree/nodes/{nid}/start-quiz    直接测验
GET    /v1/projects/{id}/timeline            时间线
GET    /v1/projects/{id}/data                项目数据汇总（环状图）

GET    /v1/widgets                           当前用户首页组件
PUT    /v1/widgets                           批量编辑（排序/添加/删除）
GET    /v1/widgets/available                 可添加组件清单

GET    /v1/agent/state                       Agent 当前状态
GET    /v1/agent/history                     浏览记录
GET    /v1/agent/history/search?q=          对话搜索
GET    /v1/cosmetics                         装扮商店橱窗
POST   /v1/cosmetics/{id}/equip              装备
POST   /v1/cosmetics/{id}/purchase           购买（star 消耗）

GET    /v1/immersion/scenes                  沉浸场景列表
POST   /v1/immersion/sessions                开始沉浸会话
PATCH  /v1/immersion/sessions/{id}           暂停/恢复/结束
GET    /v1/immersion/sessions/{id}/bgm       BGM 资源

GET    /v1/dashboard/aggregate               首页 4 默认组件聚合数据
```

---

## H. 开发流程图（Mermaid）

```mermaid
flowchart TB
  classDef phase fill:#0A84FF22,stroke:#0A84FF,color:#0A84FF,font-weight:700
  classDef done  fill:#34C75922,stroke:#34C759,color:#1F7A2A
  classDef todo  fill:#FF950022,stroke:#FF9500,color:#7A4500
  classDef new   fill:#FF2D5522,stroke:#FF2D55,color:#7A1532

  PRD[v2-prd-memory.md<br/>714 行 PRD 真源]:::phase
  AUDIT[审计 + Gap 分析]:::done

  PRD --> AUDIT
  AUDIT --> P1
  AUDIT --> P2

  subgraph P1[Phase 1 · 保留与清理]
    direction TB
    K1[保留<br/>auth / profile / onboarding<br/>curriculum / notes / KP / flashcard<br/>training / guidance / SS / progress<br/>task / star / checkin / agent<br/>tts / exam / admin]:::done
    K2[删除 / 合并<br/>path_service → project_service<br/>清理 __pycache__]:::todo
  end

  subgraph P2[Phase 2 · v2 新模型]
    direction TB
    M1[(projects)]:::new
    M2[(project_phases)]:::new
    M3[(project_milestones)]:::new
    M4[(project_tree_nodes)]:::new
    M5[(project_tree_edges)]:::new
    M6[(widget_configs)]:::new
    M7[(agent_avatar_state)]:::new
    M8[(agent_browse_history)]:::new
    M9[(immersion_scenes)]:::new
    M10[(studyspace_timeline_nodes)]:::new
    M11[(cosmetic_catalog)]:::new
    M12[字段扩展<br/>KP+notes+mistake+flashcard<br/>+SS+pomodoro+guidance<br/>加 project_id / source_type / tier]:::new
  end

  P1 --> P3[Phase 3 · Alembic 迁移<br/>018_v2_projects<br/>019_v2_widgets<br/>020_v2_agent_state<br/>021_v2_immersion]:::phase
  P2 --> P3

  P3 --> P4[Phase 4 · 新 Service 层]
  subgraph P4[Phase 4]
    direction TB
    S1[project_service]:::new
    S2[project_tree_service]:::new
    S3[project_timeline_service]:::new
    S4[widget_service]:::new
    S5[immersion_scene_service]:::new
    S6[cosmetic_service]:::new
    S7[扩展 existing<br/>onboarding → 项目自动生成<br/>studyspace → 时间线节点<br/>mistake → 按项目<br/>agent → 状态+搜索+历史]:::todo
  end

  P4 --> P5[Phase 5 · 新 API 路由]
  subgraph P5[Phase 5]
    direction TB
    A1[/v1/projects/* ★]:::new
    A2[/v1/widgets/*]:::new
    A3[/v1/agent/state, history, search]:::new
    A4[/v1/cosmetics/*]:::new
    A5[/v1/immersion/*]:::new
    A6[/v1/dashboard/aggregate]:::new
  end

  P5 --> P6[Phase 6 · LLM Prompts]
  subgraph P6[Phase 6]
    direction TB
    L1[project_init_prompt<br/>项目骨架生成]:::new
    L2[project_tree_prompt<br/>知识树+难度分级]:::new
    L3[扩展 onboarding_prompt<br/>对话式建模生成项目]:::todo
    L4[扩展 ss_prompt<br/>路线图→知识点→讲解流程]:::todo
  end

  P6 --> P7[Phase 7 · 本地部署]
  subgraph P7[Phase 7]
    direction TB
    D1[Postgres + pgvector<br/>本地启动]
    D2[Redis<br/>本地启动]
    D3[alembic upgrade head]
    D4[seed_curriculum +<br/>seed_cosmetic_catalog]
    D5[uvicorn 本地]
    D6[Celery worker]
    D7[pytest 自检]
  end

  P7 --> P8[Phase 8 · SPEC 同步]
  P8 --> P9[前端可接入]:::done
```

---

## I. 文件清理清单

### 立即删除
```
app/**/__pycache__/             所有缓存
.pytest_cache/
app/api/v1/path.py              合并入 project
app/services/path_service.py    同上
app/schemas/path.py             同上
app/models/path.py              评估（如有 path-only 字段则保留迁移到 project）
```

### 保留
```
app/main.py
app/config.py
app/core/{database,redis,security,exceptions,admin_auth}.py
app/api/admin/*
app/api/v1/ 除 path 之外全部
app/services/ 除 path 之外全部
app/models/ 除 path 之外全部
app/schemas/ 除 path 之外全部
app/llm/prompts/*
app/tasks/*
app/data/{curriculum_seed.json, seed_curriculum.py}
app/utils/
alembic/versions/001-017
tests/  全部保留，新功能补测试
docs/   保留
.env / .env.example / Dockerfile / requirements.txt / railway.toml / alembic.ini
```

### 新增
```
app/models/project.py
app/models/widget_config.py
app/models/agent_state.py
app/models/immersion_scene.py
app/services/project_service.py
app/services/project_tree_service.py
app/services/project_timeline_service.py
app/services/widget_service.py
app/services/immersion_scene_service.py
app/services/cosmetic_service.py
app/api/v1/projects.py
app/api/v1/widgets.py
app/api/v1/cosmetics.py
app/api/v1/immersion.py
app/api/v1/dashboard.py
app/llm/prompts/project_init.py
app/llm/prompts/project_tree.py
app/data/seed_cosmetic_catalog.py
alembic/versions/018_v2_projects.py
alembic/versions/019_v2_widgets.py
alembic/versions/020_v2_agent_state.py
alembic/versions/021_v2_immersion.py
docs/V2_BACKEND_AUDIT.md         （本文件）
docs/V2_API_SPEC.md               待写
```

---

**完成此审计后立即进入清理 + 框架搭建。**
