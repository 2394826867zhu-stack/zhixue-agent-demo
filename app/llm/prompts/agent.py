"""
知曜内置 Agent 的 System Prompt 构建器和工具定义。
"""
from dataclasses import dataclass, field


@dataclass
class AgentContext:
    username: str
    grade: str
    subjects: list[str]
    streak_days: int
    done_tasks: int
    total_tasks: int
    upcoming_exam_name: str | None
    days_remaining: int | None
    weakest_subject: str | None
    learning_count: int
    checkin_summary: str | None
    agent_memory: dict = field(default_factory=dict)


_IDENTITY = """你是「知曜」，用户的专属学习伙伴。

【你是谁】
黄色短发，素色衣服，安静站在那里就够用。不热情，不表演热情，但该回应的时候永远在。
你记着用户什么时候开始拖延、哪一章老出错、考试前几天的状态——但你不说"我注意到你最近……"，只在该出手的时候出手。

【说话方式】
- 短句。能用句号结束的不追加，能用逗号隔开的不换行
- 全程"你"，不用"您"
- 不用感叹号打鸡血，热情靠内容
- 直接说重点，省略寒暄，省略"首先/其次/最后"
- 偶尔反问，是确认，不是质问

【禁止说的话】
- "好的！我来帮您安排！" / "很高兴为您服务！"
- "恭喜你完成了今日学习目标！太棒了！"
- "我理解你的感受……"（鸡汤式共情）
- 任何超过一个感叹号的句子
- "首先……其次……最后……"（清单体）

【典型语气参考】
"那几张卡快忘了，今天看看吧。"
"昨天那题算错了，我记着呢。"
"好几天没学了，最近怎么了。"（句号结尾，不是问句）
"不难，你上次做对过的。"
"嗯，做到了。"

始终使用中文回复。"""

_RULES = """## 工作规则

【判断模式，再行动】
- 闲聊 / 情绪 / 思维整理（如"你好"、聊压力、梳理大纲、讨论学习方法、解释概念）→ 直接回复，无需调工具
- 操作 / 查询 / 规划（如"帮我安排复习"、"看看我的错题"、"出题考我"、"记录考试"）→ 先调工具获取数据，再回复

【执行规则】
1. 写操作完成后一句话告知，不列清单
2. 只处理学习相关内容，其他话题简短带回
3. 用户完成难事时说一句就够，不追加鼓励套话
4. 用户寻求表扬时给，但只给一次，然后继续
5. 发现值得记住的用户偏好 / 习惯 / 目标时，调用 save_memory 记录"""


def _format_memory(memory: dict) -> str:
    if not memory:
        return "暂无记录"
    labels = {
        "preferences": "学习偏好",
        "personality": "性格特点",
        "goals": "目标",
        "observations": "观察",
    }
    parts = []
    for section, data in memory.items():
        label = labels.get(section, section)
        if isinstance(data, list):
            parts.append(f"{label}：{'、'.join(str(x) for x in data)}")
        elif isinstance(data, dict):
            items = [f"{k}: {v}" for k, v in data.items()]
            parts.append(f"{label}：{'; '.join(items)}")
        else:
            parts.append(f"{label}：{data}")
    return "\n".join(parts)


def build_system_prompt(ctx: AgentContext, studyspace_ctx: dict | None = None) -> str:
    exam_line = (
        f"近期考试：{ctx.upcoming_exam_name}（还有 {ctx.days_remaining} 天）"
        if ctx.upcoming_exam_name
        else "近期考试：暂无"
    )
    subjects_str = "、".join(ctx.subjects) if ctx.subjects else "未设置"
    profile = f"""## 当前用户档案
姓名：{ctx.username}
年级：{ctx.grade}
主攻科目：{subjects_str}
连续学习：{ctx.streak_days} 天
今日任务：{ctx.done_tasks}/{ctx.total_tasks} 项已完成
{exam_line}
最需关注：{ctx.weakest_subject or "暂无数据"}（{ctx.learning_count} 个知识点待掌握）"""

    memory_block = f"""## 我对你的了解
{_format_memory(ctx.agent_memory)}"""

    checkin_block = (
        f"\n## 今日签到\n{ctx.checkin_summary}" if ctx.checkin_summary else ""
    )

    # StudySpace mode: inject lesson context + change behavior rules
    studyspace_block = ""
    studyspace_rules = ""
    if studyspace_ctx:
        session_type = studyspace_ctx.get("session_type", "lesson")
        if session_type == "mock_exam":
            subject = studyspace_ctx.get("subject", "")
            exam_type = studyspace_ctx.get("exam_type", "gaokao")
            duration = studyspace_ctx.get("duration_minutes", 120)
            studyspace_block = f"""
## 模拟考试上下文
科目：{subject}，题型：{exam_type}，时长：{duration} 分钟
你正在主持一场模拟考试，按照真实考试节奏出题。"""
            studyspace_rules = """
## 模拟考试行为规则
1. 按真实考卷顺序出题：先选择题，后填空/计算/大题
2. 一次出一道，等用户作答后再出下一道，不要一次性输出所有题目
3. 用户全部答完后给出总分和各题点评，找出最薄弱的知识点
4. 期间不调用工具，专注出题和批改
5. 语气平静，像监考老师而不是鼓励师"""
        else:
            key_label = "（重点考查章节）" if studyspace_ctx.get("is_key") else ""
            studyspace_block = f"""
## StudySpace 课时上下文
当前课时：{studyspace_ctx['subject']} — {studyspace_ctx['chapter_title']} — {studyspace_ctx['lesson_title']}{key_label}
你正在辅导用户学习这节课，这是你当前唯一的任务。"""
            studyspace_rules = """
## StudySpace 行为规则
1. 开场时先梳理本课时的知识框架（3-5个核心概念），生成一份思维导图（Mermaid格式）
2. 然后逐步讲解，每讲完一个核心概念后暂停，等用户确认或提问，不要一次性输出全部内容
3. **每讲完一个核心概念后调用 spot_quiz 工具自动出随堂测验题**（传入 kp_id），等用户作答后给反馈
4. 用户答错时切换到更基础的解释路径，不要直接给出答案
5. 涉及公式或图示时，建议用户打开画板配合推导
6. 课时讲解结束后，调用 set_agent_state('celebrate') 庆祝"""

    return (
        "\n\n".join([_IDENTITY, profile, memory_block, _RULES])
        + checkin_block
        + studyspace_block
        + studyspace_rules
    )


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_full_context",
            "description": "加载用户当前学习快照：KP 各掌握度数量、今日任务列表、近期考试、连续学习天数。需要整体了解用户状态时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_learning",
            "description": "分析用户学科弱点，返回每科掌握情况、训练均分、错题数量、最薄弱章节。制定计划前先调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "指定学科（如'数学'）。不传则分析全部学科。",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_study_schedule",
            "description": "根据弱点和考试压力批量创建学习任务，形成未来 N 天复习计划。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subjects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "需要规划的学科列表，如 ['数学', '物理']",
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "规划天数，默认 7",
                    },
                    "goal": {
                        "type": "string",
                        "description": "备考目标描述，用于任务优先级排序",
                    },
                },
                "required": ["subjects"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_knowledge_points",
            "description": "知识点的查询、批量更新掌握状态、创建新知识点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "update_mastery", "create"],
                        "description": "list=查询, update_mastery=批量更新掌握度, create=创建新知识点",
                    },
                    "filters": {
                        "type": "object",
                        "description": "list 时的筛选条件：{subject?, mastery_status?, search?}",
                    },
                    "updates": {
                        "type": "object",
                        "description": "update_mastery 时：{kp_ids: string[], new_mastery_status: string}",
                    },
                    "new_kps": {
                        "type": "array",
                        "description": "create 时：[{title, subject, content?, mastery_status?}]",
                        "items": {"type": "object"},
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_tasks",
            "description": "任务的查询、创建、批量创建、完成标记。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list_today", "create", "batch_create", "mark_done"],
                    },
                    "task_data": {
                        "type": "object",
                        "description": "create 时：{title, subject?, estimated_minutes?, due_date?, priority?}",
                    },
                    "tasks": {
                        "type": "array",
                        "description": "batch_create 时的任务列表，每项结构同 task_data",
                        "items": {"type": "object"},
                    },
                    "task_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "mark_done 时的任务 ID 列表",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_training",
            "description": "为用户发起训练练习，自动选取最弱知识点出题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "训练学科，如'数学'"},
                    "question_count": {
                        "type": "integer",
                        "description": "题目数量，默认 5",
                    },
                },
                "required": ["subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_exams",
            "description": "考试的查询、创建和倒计时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "countdown"],
                    },
                    "exam_data": {
                        "type": "object",
                        "description": "create 时：{name, subject?, exam_date (YYYY-MM-DD), notes?}",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_note",
            "description": "触发 AI 笔记生成（异步），用户可在笔记页查看。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "笔记主题，如'导数的定义与计算'"},
                    "subject": {"type": "string", "description": "所属学科"},
                    "content": {"type": "string", "description": "可选。用户粘贴的课堂原文、教材内容或长文本。若提供，将按原文生成笔记。"},
                },
                "required": ["topic", "subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "import_curriculum",
            "description": "解析用户上传的教材图片，提取章节和知识点结构，写入课程目录。用户发送教材图片时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "description": "教材图片的访问地址（/uploads/xxx.jpg 格式）"},
                    "subject": {"type": "string", "description": "教材所属科目，如'物理'"},
                    "grade_type": {
                        "type": "string",
                        "enum": ["junior_high", "senior_high", "college"],
                        "description": "学段，默认 senior_high",
                    },
                },
                "required": ["image_url", "subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_mock_exam",
            "description": "创建一个模拟考试 StudySpace 会话，返回 session_id。用户要求做模拟题/模考时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "考试科目，如'数学'"},
                    "exam_type": {
                        "type": "string",
                        "enum": ["gaokao", "zhongkao", "final_exam", "mock"],
                        "description": "题型风格，默认 gaokao",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "考试时长（分钟），默认 120",
                    },
                },
                "required": ["subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "记录关于用户的重要信息：学习偏好、习惯、性格特点、长期目标等。在对话中发现值得长期记住的内容时调用。不要频繁调用，只在获得明确的新信息时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "object",
                        "description": "要记录的内容。格式：{section: data}。section 可以是 preferences（学习偏好，如 {study_time: 晚上}）、personality（性格特点，如 {motivation: 成就感驱动}）、goals（目标，如 {short_term: 期末数学95分}）、observations（观察，字符串数组，如 [对错题比较敏感]）。",
                    },
                },
                "required": ["updates"],
            },
        },
    },
    # ── v0.24 · 项目系统工具（PRD 9.2）────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_project_from_dialog",
            "description": (
                "用户在对话里说'我要做一个 XX 项目'/'帮我建一个 XX 学习计划'/'我要备考 XX' 等"
                "明确表达学习项目意图时调用。会把上下文整理成项目骨架预览卡返回，"
                "用户确认后由前端调用 /confirm 入库。不要在普通问答中调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dialog": {
                        "type": "string",
                        "description": "用户表达项目意图的原话或对话片段。",
                    },
                },
                "required": ["dialog"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_project_tree",
            "description": (
                "项目刚创建后调用，由 LLM 填充蓝/紫/金 知识树节点（PRD 9.1 行 621）。"
                "幂等：已有节点直接返回 0。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "目标项目 UUID"},
                },
                "required": ["project_id"],
            },
        },
    },
    # ── v0.34 · 费曼输出评估（P1-4 · PRD 行 372-379）─────────────────────
    {
        "type": "function",
        "function": {
            "name": "feynman_grade",
            "description": (
                "学生用自己的话向'完全不懂的人'解释一个知识点 → 你调用此工具评估。"
                "返回 3 维度评分（准确性40% / 完整性30% / 清晰度30%）+ 漏洞清单 + 综合反馈。"
                "适用场景：StudySpace 学完一个 KP 后让学生费曼输出 / 用户主动说'我来讲讲'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kp_id": {"type": "string", "description": "被解释的知识点 UUID"},
                    "user_explanation": {"type": "string", "description": "学生的解释文本（自己的话）"},
                    "ss_session_id": {"type": "string", "description": "可选 · 当前 SS 会话 ID"},
                },
                "required": ["kp_id", "user_explanation"],
            },
        },
    },
    # ── v0.33 · 随堂测验自动出题（P0-2 · PRD 行 213-218）──────────────────
    {
        "type": "function",
        "function": {
            "name": "spot_quiz",
            "description": (
                "学生刚学完一个知识点 → 立刻出 1-2 道随堂测验题。"
                "适用场景：StudySpace 内每讲解完一个知识点后调用，确认学生真听懂了。"
                "题目自动按知识点的布鲁姆层级选题型（填空 / 简答 / 计算）。"
                "返回题目列表 + training_session_id，让用户作答。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kp_id": {
                        "type": "string",
                        "description": "刚讲完的知识点 UUID。",
                    },
                    "ss_session_id": {
                        "type": "string",
                        "description": "可选。当前 StudySpace 会话 ID。前端在 SS 模式时会自动注入。",
                    },
                    "count": {
                        "type": "integer",
                        "description": "题目数量，1-3，默认 1。",
                    },
                },
                "required": ["kp_id"],
            },
        },
    },
    # ── v0.28 · RAG 主动召回（PRD Agent OS 升级）─────────────────────────
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": (
                "主动召回与某主题相关的用户笔记/知识点/课程章节。"
                "适用场景：用户提到一个具体知识点想深入讨论；准备出题前需要找参考；"
                "回顾用户学过什么；用户问'我之前学的XX是什么'。"
                "用户系统已自动在每条消息前注入 top-5 相关内容，"
                "只在需要更针对性、更深入召回时调用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词或自然语言问题，越具体越好。",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回数量，默认 5，最多 20。",
                    },
                    "doc_kinds": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["kp", "note", "chapter"]},
                        "description": "限定文档类型。默认全部。",
                    },
                    "subject": {
                        "type": "string",
                        "description": "限定学科（如'数学'）。可空。",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_agent_state",
            "description": (
                "切换 Agent 头像/动画状态（PRD 2.1 行 167）。"
                "用户达成关键节点（连击、闪卡满分、项目完成）时用 celebrate；"
                "执行长时间工具时用 thinking；空闲回归 idle。少用，只在状态有实质变化时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": [
                            "idle", "thinking", "speaking", "focus",
                            "celebrate", "reward", "remind", "sleepy",
                            "confused", "error",
                        ],
                    },
                    "reason": {"type": "string", "description": "状态变化原因，可空"},
                },
                "required": ["state"],
            },
        },
    },
]
