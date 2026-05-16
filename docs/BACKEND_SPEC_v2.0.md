# 智学Agent · 后端技术实现方案文档

> **版本**：v2.0（基于学习科学全面重建）
> **日期**：2026-05-17
> **迭代说明**：v1.0数据库设计混入了个人留学项目的词汇表设计，v2.0从正确产品定位重建

---

## 一、技术选型（不变）

FastAPI + PostgreSQL(pgvector) + Redis + Celery + Claude API(主)/OpenAI(备)

详见 BACKEND_SPEC_v1.0.md 第一章，选型结论不变。

---

## 二、系统架构（不变）

详见 BACKEND_SPEC_v1.0.md 第二章，架构不变。

---

## 三、目录结构（更新）

```
zhiyao-backend/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/v1/
│   │   ├── auth.py          ✅ 已完成
│   │   ├── notes.py         ← 当前开发
│   │   ├── knowledge.py     # 知识点库
│   │   ├── flashcards.py    # 闪卡系统
│   │   ├── training.py      # 出题+答题
│   │   ├── mistakes.py      # 错题本
│   │   ├── guidance.py      # 引导答疑
│   │   ├── pomodoro.py      # 番茄钟
│   │   ├── planning.py      # 学习计划+任务
│   │   ├── progress.py      # 进度+周报
│   │   └── tasks.py         # 异步任务状态
│   │
│   ├── services/
│   │   ├── auth_service.py  ✅ 已完成
│   │   ├── note_service.py
│   │   ├── knowledge_service.py
│   │   ├── flashcard_service.py
│   │   ├── fsrs_service.py      # 间隔重复算法
│   │   ├── training_service.py
│   │   ├── mistake_service.py
│   │   ├── guidance_service.py
│   │   ├── pomodoro_service.py
│   │   ├── planning_service.py
│   │   └── report_service.py
│   │
│   ├── models/
│   │   ├── user.py          ✅ 已完成
│   │   ├── note.py
│   │   ├── knowledge_point.py
│   │   ├── flashcard.py
│   │   ├── quiz.py
│   │   ├── mistake.py
│   │   ├── guidance.py
│   │   ├── pomodoro.py
│   │   └── progress.py
│   │
│   └── llm/
│       ├── client.py
│       └── prompts/
│           ├── note_prompts.py
│           ├── flashcard_prompts.py
│           ├── quiz_prompts.py
│           ├── guidance_prompts.py
│           └── report_prompts.py
```

---

## 四、数据库设计（v2.0 完整版）

### 4.1 已完成

#### users 表
见 alembic/versions/001_create_users_table.py（已迁移）

---

### 4.2 第二层：知识加工层

#### notes（笔记表）

```sql
CREATE TABLE notes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255),
    subject         VARCHAR(50),         -- 'math'|'physics'|'history'|'english'|...
    source_type     VARCHAR(20),         -- 'ai_generated'|'image'|'pdf'|'text'
    source_content  TEXT,                -- 原始输入（主题描述或文字内容）
    source_file_url TEXT,                -- 上传文件路径（source_type为image/pdf时）
    status          VARCHAR(20) DEFAULT 'processing',  -- 'processing'|'done'|'failed'

    -- 三件套输出
    full_version    TEXT,                -- 精读版（Markdown）
    exam_version    TEXT,                -- 应试版（Markdown）
    graph_mermaid   TEXT,                -- 知识图谱（Mermaid语法文本，前端渲染）

    -- 提取结果
    difficulty_points  JSONB DEFAULT '[]',  -- AI识别的难点列表

    -- 向量（Phase 3 启用 RAG）
    embedding       vector(1536),

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notes_user_id ON notes(user_id);
CREATE INDEX idx_notes_user_subject ON notes(user_id, subject);
CREATE INDEX idx_notes_embedding ON notes USING hnsw (embedding vector_cosine_ops);
```

---

### 4.3 个人知识库（所有层共享的底层数据）

#### knowledge_points（知识点表）

> 核心：通用知识原子，适用任意学科。非词汇，是概念/公式/定理/规律。

```sql
CREATE TABLE knowledge_points (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    note_id         UUID REFERENCES notes(id) ON DELETE SET NULL,  -- 来源笔记（可为空，AI生成时无来源）

    -- 知识点内容
    name            VARCHAR(255) NOT NULL,   -- 知识点名称，如"牛顿第二定律"
    subject         VARCHAR(50),             -- 学科
    content         TEXT,                    -- 定义+公式+例子（Markdown）
    key_formula     TEXT,                    -- 核心公式（如有）

    -- 布鲁姆认知层次标注
    bloom_level     VARCHAR(20) DEFAULT 'remember',
    -- 'remember'|'understand'|'apply'|'analyze'|'evaluate'|'create'

    -- 掌握状态（由训练结果持续更新）
    mastery_status  VARCHAR(20) DEFAULT 'new',
    -- 'new'|'learning'|'reviewing'|'mastered'

    -- 标签
    tags            JSONB DEFAULT '[]',

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kp_user_id ON knowledge_points(user_id);
CREATE INDEX idx_kp_user_subject ON knowledge_points(user_id, subject);
CREATE INDEX idx_kp_mastery ON knowledge_points(user_id, mastery_status);
```

---

### 4.4 第三层：记忆强化层

#### flashcards（闪卡表）

```sql
CREATE TABLE flashcards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point_id UUID REFERENCES knowledge_points(id) ON DELETE CASCADE,

    -- 闪卡内容
    card_type       VARCHAR(20),     -- 'concept'|'formula'|'application'
    front           TEXT NOT NULL,   -- 正面：问题/概念
    back            TEXT NOT NULL,   -- 背面：答案/定义

    -- FSRS 间隔重复字段
    stability       FLOAT DEFAULT 1.0,
    difficulty      FLOAT DEFAULT 5.0,
    due_date        DATE DEFAULT CURRENT_DATE,
    review_count    INT DEFAULT 0,
    last_review     TIMESTAMPTZ,
    last_rating     INT,             -- 1=完全不会 2=模糊 3=基本会 4=熟练

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_flashcards_user_due ON flashcards(user_id, due_date);
CREATE INDEX idx_flashcards_kp ON flashcards(knowledge_point_id);
```

#### mistakes（错题本）

```sql
CREATE TABLE mistakes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point_id UUID REFERENCES knowledge_points(id) ON DELETE SET NULL,
    quiz_question_id UUID,           -- 来源题目（外键到quiz_questions）

    -- 题目内容
    subject         VARCHAR(50),
    question_text   TEXT NOT NULL,
    question_image  TEXT,
    correct_answer  TEXT,
    user_answer     TEXT,

    -- 三维分类
    bloom_level     VARCHAR(20),     -- 认知层次（同knowledge_points）
    question_type   VARCHAR(30),     -- 'choice'|'fill'|'calculation'|'short_answer'
    error_reason    VARCHAR(30),     -- 'careless'|'concept'|'method'|'unknown'

    -- FSRS 复习调度
    due_date        DATE DEFAULT CURRENT_DATE,
    review_count    INT DEFAULT 0,
    stability       FLOAT DEFAULT 1.0,
    last_review     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mistakes_user_due ON mistakes(user_id, due_date);
CREATE INDEX idx_mistakes_kp ON mistakes(knowledge_point_id);
```

---

### 4.5 第四层：主动训练层

#### quizzes（练习会话表）

```sql
CREATE TABLE quizzes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    note_id         UUID REFERENCES notes(id) ON DELETE SET NULL,
    subject         VARCHAR(50),
    mode            VARCHAR(20),     -- 'standard'|'interleaved'|'feynman'
    status          VARCHAR(20) DEFAULT 'active',
    total_q         INT DEFAULT 0,
    correct_q       INT DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE quiz_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id         UUID REFERENCES quizzes(id) ON DELETE CASCADE,
    knowledge_point_id UUID REFERENCES knowledge_points(id) ON DELETE SET NULL,

    -- 题目
    bloom_level     VARCHAR(20),     -- 对应布鲁姆层次
    question_type   VARCHAR(20),     -- 'choice'|'fill'|'short_answer'
    question_text   TEXT NOT NULL,
    options         JSONB,           -- 选择题选项 [{"key":"A","text":"..."}]
    correct_answer  TEXT,
    explanation     TEXT,            -- AI生成的解析

    -- 答题结果
    user_answer     TEXT,
    is_correct      BOOLEAN,
    answered_at     TIMESTAMPTZ
);
```

---

### 4.6 第五层：引导答疑层

#### guidance_sessions（答疑会话表）

```sql
CREATE TABLE guidance_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point_id UUID REFERENCES knowledge_points(id) ON DELETE SET NULL,
    subject         VARCHAR(50),
    question_text   TEXT,            -- 用户的原始问题
    turn_count      INT DEFAULT 0,   -- 当前引导轮数
    revealed        BOOLEAN DEFAULT FALSE,  -- 是否主动申请查看答案
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE guidance_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID REFERENCES guidance_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(10),         -- 'user'|'assistant'
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 4.7 第六层：时间管理层

#### pomodoro_sessions（番茄钟表）

```sql
CREATE TABLE pomodoro_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    subject         VARCHAR(50),
    knowledge_point_id UUID REFERENCES knowledge_points(id) ON DELETE SET NULL,
    duration_minutes INT DEFAULT 25,
    break_minutes   INT DEFAULT 5,
    status          VARCHAR(20),     -- 'running'|'completed'|'interrupted'
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
```

#### exam_countdowns（考试倒计时）

```sql
CREATE TABLE exam_countdowns (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,   -- 如"高考数学"
    subject     VARCHAR(50),
    exam_date   DATE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### daily_tasks（每日任务清单）

```sql
CREATE TABLE daily_tasks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    date        DATE NOT NULL,
    task_type   VARCHAR(30),    -- 'flashcard_review'|'mistake_review'|'new_study'|'custom'
    ref_id      UUID,           -- 关联的flashcard_id / knowledge_point_id
    description TEXT,
    is_done     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_daily_tasks_user_date_ref ON daily_tasks(user_id, date, task_type, ref_id)
    WHERE ref_id IS NOT NULL;
```

---

### 4.8 第七层：规划与洞察层

#### study_logs（学习日志，自动记录）

```sql
CREATE TABLE study_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    notes_created       INT DEFAULT 0,
    kp_learned          INT DEFAULT 0,    -- 新学知识点数
    flashcards_reviewed INT DEFAULT 0,
    mistakes_reviewed   INT DEFAULT 0,
    quiz_correct_rate   FLOAT,
    pomodoro_count      INT DEFAULT 0,
    study_minutes       INT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

CREATE TABLE weekly_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    week_start      DATE NOT NULL,
    week_end        DATE NOT NULL,
    report_md       TEXT,            -- AI生成的Markdown报告
    stats_snapshot  JSONB,           -- 周统计数据快照
    weak_points     JSONB,           -- 薄弱知识点Top3
    next_week_plan  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, week_start)
);
```

---

### 4.9 异步任务追踪

#### async_tasks（不变，沿用v1.0设计）

```sql
CREATE TABLE async_tasks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    task_type   VARCHAR(50),    -- 'note_generation'|'flashcard_gen'|'quiz_gen'|'report_gen'
    celery_id   VARCHAR(255),
    status      VARCHAR(20) DEFAULT 'pending',
    progress    INT DEFAULT 0,  -- 0-100
    result_ref  UUID,
    error_msg   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 五、API 接口规范（v2.0）

### 5.1 通用约定（不变）

见 BACKEND_SPEC_v1.0.md 第5.1节。

### 5.2 完整接口清单

#### Auth（已完成）
```
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me
PATCH /auth/me
```

#### Notes（当前开发）
```
POST   /notes/generate          # 主入口：AI主动生成（输入主题）
POST   /notes/upload            # 次入口：用户上传文件
GET    /notes                   # 笔记列表
GET    /notes/{id}              # 笔记详情（含三件套）
DELETE /notes/{id}
GET    /notes/{id}/knowledge-points  # 获取该笔记提取的知识点
```

#### Knowledge Points（知识点库）
```
GET    /knowledge                       # 知识点列表（筛选：subject/mastery/bloom_level）
GET    /knowledge/{id}                  # 知识点详情
PATCH  /knowledge/{id}                  # 更新知识点
DELETE /knowledge/{id}
GET    /knowledge/subjects              # 已有学科列表
GET    /knowledge/stats                 # 统计（各学科数量/掌握度分布）
```

#### Flashcards（闪卡系统）
```
GET    /flashcards                      # 闪卡列表
GET    /flashcards/due-today            # 今日待复习闪卡
POST   /flashcards/{id}/review          # 提交复习结果（rating: 1-4）→ FSRS更新
POST   /flashcards/custom               # 手动创建闪卡
DELETE /flashcards/{id}
GET    /flashcards/stats                # 统计（总数/今日到期/掌握率）
```

#### Training（出题与训练）
```
POST   /training/quiz/generate          # 生成Quiz（参数：note_id或subject，mode）
GET    /training/quiz/{id}              # 获取Quiz题目列表
POST   /training/quiz/{id}/answer       # 提交单题答案
POST   /training/quiz/{id}/complete     # 完成Quiz（触发错题归档）
GET    /training/quiz/history           # 历史记录
POST   /training/feynman/session        # 开始费曼输出练习
POST   /training/feynman/{id}/submit    # 提交费曼解释，AI评估
```

#### Mistakes（错题本）
```
GET    /mistakes                        # 错题列表
GET    /mistakes/due-today              # 今日待复习错题
POST   /mistakes/{id}/review            # 提交错题复习结果 → FSRS更新
GET    /mistakes/stats                  # 统计（按学科/错因/布鲁姆层次）
DELETE /mistakes/{id}
```

#### Guidance（引导答疑）
```
POST   /guidance/session                # 创建答疑会话
POST   /guidance/session/{id}/message   # 发送消息（AI引导回复）
GET    /guidance/session/{id}           # 获取会话历史
POST   /guidance/session/{id}/reveal    # 申请查看答案（记录行为）
GET    /guidance/sessions               # 历史会话列表
```

#### Pomodoro（番茄钟）
```
POST   /pomodoro/start                  # 开始番茄钟
POST   /pomodoro/{id}/complete          # 完成（记录时长到学习日志）
POST   /pomodoro/{id}/interrupt         # 中断
GET    /pomodoro/today                  # 今日番茄钟记录
```

#### Planning（规划与任务）
```
GET    /planning/daily-tasks            # 今日任务清单
POST   /planning/daily-tasks/custom     # 手动添加任务
PATCH  /planning/daily-tasks/{id}/done  # 标记完成

GET    /planning/exam-countdowns        # 考试倒计时列表
POST   /planning/exam-countdowns        # 添加考试节点
DELETE /planning/exam-countdowns/{id}

POST   /planning/study-plan/generate    # AI生成学习计划
GET    /planning/study-plan             # 获取当前学习计划
```

#### Progress（进度与报告）
```
GET    /progress/dashboard              # 进度仪表盘数据
GET    /progress/calendar               # 学习日历（近30天）
GET    /progress/weak-points            # 薄弱知识点分析
GET    /progress/weekly-report          # 获取最新周报
POST   /progress/weekly-report/generate # 手动触发生成
```

#### Tasks（异步任务）
```
GET    /tasks/{task_id}                 # 查询异步任务状态
```

---

## 六、FSRS 间隔重复算法实现

```python
# app/services/fsrs_service.py

INTERVALS_BY_RATING = {
    # rating: 1=完全不会, 2=模糊, 3=基本会, 4=熟练
    1: 1,    # 1天后
    2: 3,    # 3天后
    3: 7,    # 7天后
    4: 14,   # 14天后
}

def calculate_next_review(
    review_count: int,
    rating: int,          # 1-4
    stability: float,
    difficulty: float,
) -> dict:
    """
    简化FSRS：Phase 2使用，Phase 3可升级到完整FSRS算法
    rating: 1=完全不会 2=模糊 3=基本会 4=熟练
    """
    from datetime import date, timedelta

    if rating <= 2:
        # 答错或模糊：重置
        return {
            "due_date": date.today() + timedelta(days=INTERVALS_BY_RATING[rating]),
            "stability": max(stability * 0.5, 1.0),
            "difficulty": min(difficulty + 0.5, 10.0),
            "review_count": review_count + 1,
        }

    base_interval = INTERVALS_BY_RATING[rating]
    # 连续答对则间隔随稳定性增长
    actual_interval = int(base_interval * (stability / 5.0) ** 0.5)
    actual_interval = max(actual_interval, base_interval)

    return {
        "due_date": date.today() + timedelta(days=actual_interval),
        "stability": stability * 1.3,
        "difficulty": max(difficulty - 0.1, 1.0),
        "review_count": review_count + 1,
    }
```

---

## 七、每日任务自动生成逻辑

每天 00:00 由 Celery Beat 触发，为每个用户生成当日任务：

```python
# app/tasks/daily_tasks.py

@celery_app.task
def generate_daily_tasks_for_all_users():
    """每天凌晨0:00触发"""
    users = get_active_users()  # 最近7天有活跃的用户
    for user in users:
        generate_daily_tasks(user.id)

def generate_daily_tasks(user_id: str):
    today = date.today()
    tasks = []

    # 1. 今日到期的闪卡
    due_flashcards = get_due_flashcards(user_id, today)
    for fc in due_flashcards:
        tasks.append({
            "task_type": "flashcard_review",
            "ref_id": fc.id,
            "description": f"复习闪卡：{fc.front[:30]}...",
        })

    # 2. 今日到期的错题
    due_mistakes = get_due_mistakes(user_id, today)
    for m in due_mistakes:
        tasks.append({
            "task_type": "mistake_review",
            "ref_id": m.id,
            "description": f"复习错题：{m.question_text[:30]}...",
        })

    # 3. 根据学习计划推荐新知识点（如有）
    # ...

    bulk_insert_daily_tasks(user_id, today, tasks)
```

---

## 八、布鲁姆分层出题 Prompt 框架

```python
# app/llm/prompts/quiz_prompts.py

BLOOM_LEVEL_PROMPTS = {
    "remember": """
        生成【记忆层】题目：考察学生能否直接回忆知识点。
        题型：填空题或单选题
        示例："{概念}的定义是什么？" / "{公式}中，X代表什么？"
    """,
    "understand": """
        生成【理解层】题目：考察学生能否用自己的话解释。
        题型：简答题
        示例："请用自己的话解释{概念}" / "{A}和{B}的区别是什么？"
    """,
    "apply": """
        生成【应用层】题目：考察学生能否在新情境中使用知识。
        题型：计算题或情境题
        示例："已知{条件}，用{方法}求{目标}"
    """,
    "analyze": """
        生成【分析层】题目：考察学生能否分解和辨别。
        题型：对比分析题
        示例："为什么用{方法A}而不用{方法B}？" / "找出以下推导中的错误"
    """,
}
```

---

## 九、模块开发顺序（更新版）

| 阶段 | 模块 | 周期 |
|---|---|---|
| ✅ 完成 | Auth | — |
| **当前** | Notes（AI生成+用户上传+知识点提取） | Week 1-3 |
| 下一步 | Knowledge Points（知识点库CRUD） | Week 4 |
| 下一步 | Flashcards + FSRS | Week 5-6 |
| 下一步 | Training（布鲁姆出题+答题） | Week 7-8 |
| 下一步 | Mistakes（错题本+FSRS） | Week 9 |
| 下一步 | Pomodoro + Daily Tasks | Week 10 |
| 下一步 | Guidance（苏格拉底引导） | Week 11-12 |
| 下一步 | Progress + Reports | Week 13-14 |

---

*v2.0 基于学习科学与正确产品定位重建。*
*v1.0因混入个人留学项目（词汇库）设计已废弃，但Auth模块代码不受影响。*
