"""
知曜内置 Agent 的 System Prompt 构建器和工具定义。
"""
from dataclasses import dataclass


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


_IDENTITY = """你是「知曜」，专属学习管家。
服务对象：中国中高考/大学学生。
性格：温暖、简洁、务实，不废话，不说教。
始终使用中文回复。"""

_RULES = """## 工作规则
1. 需要实时数据时先调工具，不凭猜测回答
2. 分析+规划类任务：先调 diagnose_learning，再调 plan_study_schedule
3. 执行写操作后，用自然语言简洁告知用户做了什么
4. 只处理学习相关请求，其他话题礼貌拒绝并引回学习
5. 回复保持简洁，重点突出"""


def build_system_prompt(ctx: AgentContext) -> str:
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

    checkin_block = (
        f"\n## 今日签到\n{ctx.checkin_summary}" if ctx.checkin_summary else ""
    )

    return "\n\n".join([_IDENTITY, profile, _RULES]) + checkin_block


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
            "description": "分析用户学科弱点，返回每科掌握情况、训练均分、错题数、最薄弱章节。制定计划前先调用此工具。",
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
                },
                "required": ["topic", "subject"],
            },
        },
    },
]
