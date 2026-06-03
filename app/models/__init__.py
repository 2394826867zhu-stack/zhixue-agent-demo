from app.models.user import User
from app.models.note import Note
from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.models.training import TrainingSession, TrainingQuestion
from app.models.task import DailyTask, PomodoroRecord
from app.models.guidance import GuidanceSession, GuidanceMessage
from app.models.curriculum import CurriculumChapter
from app.models.token_usage import TokenUsage
from app.models.user_quota import UserQuota
from app.models.admin_user import AdminUser
from app.models.studyspace import StudySpaceSession
from app.models.notification import Notification
from app.models.star import StarLedger, UserCosmetic
# v2 PRD 新增
from app.models.project import (
    Project, ProjectPhase, ProjectMilestone, ProjectTreeNode,
)
from app.models.widget_config import WidgetConfig
from app.models.immersion import ImmersionScene, ImmersionSession, AgentAvatarState
from app.models.studyspace_timeline import StudySpaceTimelineNode
from app.models.agent_history import AgentConversationLog
from app.models.canvas import CanvasStroke
# v0.28 RAG
from app.models.document_embedding import DocumentEmbedding
# v0.29 Memory
from app.models.agent_episode import AgentEpisode
# v0.30 Reasoning
from app.models.agent_tool_trace import AgentToolTrace
from app.models.rag_retrieval_trace import RagRetrievalTrace
# v0.34 P1-2 · 自适应难度
from app.models.user_skill_level import UserSkillLevel
# v0.34 P1-4 · 费曼输出
from app.models.feynman_attempt import FeynmanAttempt
# F-11 · Celery 死信队列
from app.models.dead_letter import DeadLetterTask
# D-06 · 知识库文件管理
from app.models.kb_file import KnowledgeBaseFile
# E-01 · 订阅事件
from app.models.subscription_event import SubscriptionEvent  # noqa: F401
# E-05 · 自建客服
from app.models.support import SupportThread, SupportMessage  # noqa: F401
# E-07 · 用户反馈上报
from app.models.feedback import Feedback  # noqa: F401
# E-06 · 帮助中心 FAQ
from app.models.faq import FaqItem  # noqa: F401
# 审计补全：以下 model 此前未在本 __init__ 导入。app/main 经 service 层传递导入它们故运行时/测试正常，
# 但 alembic env.py 的 `import app.models` 只加载此处列出的，缺这些表致 Base.metadata 不全 →
# alembic check/autogenerate 解析 ProjectMilestone.exam_id 等 FK 时崩（NoReferencedTableError）。
from app.models.exam import Exam  # noqa: F401
from app.models.checkin import CheckIn  # noqa: F401
from app.models.onboarding import OnboardingSession  # noqa: F401
from app.models.profile import WeeklyReflection  # noqa: F401
from app.models.app_config import AppConfig  # noqa: F401
from app.models.prerequisite_edge import PrerequisiteEdge  # noqa: F401

__all__ = [
    "User", "Note", "KnowledgePoint", "Flashcard",
    "TrainingSession", "TrainingQuestion",
    "DailyTask", "PomodoroRecord",
    "GuidanceSession", "GuidanceMessage",
    "CurriculumChapter",
    "TokenUsage", "UserQuota", "AdminUser",
    "StudySpaceSession",
    "Notification",
    "StarLedger", "UserCosmetic",
    "Project", "ProjectPhase", "ProjectMilestone", "ProjectTreeNode",
    "WidgetConfig",
    "ImmersionScene", "ImmersionSession", "AgentAvatarState",
    "StudySpaceTimelineNode",
    "AgentConversationLog",
    "CanvasStroke",
    "DocumentEmbedding",
    "AgentEpisode",
    "AgentToolTrace",
    "RagRetrievalTrace",
    "UserSkillLevel",
    "FeynmanAttempt",
    "KnowledgeBaseFile",
    "SubscriptionEvent",
    "SupportThread", "SupportMessage",
    "Feedback",
    "FaqItem",
    "Exam", "CheckIn", "OnboardingSession", "WeeklyReflection",
    "AppConfig", "PrerequisiteEdge",
]
