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
# v0.34 P1-2 · 自适应难度
from app.models.user_skill_level import UserSkillLevel
# v0.34 P1-4 · 费曼输出
from app.models.feynman_attempt import FeynmanAttempt
# F-11 · Celery 死信队列
from app.models.dead_letter import DeadLetterTask

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
    "UserSkillLevel",
    "FeynmanAttempt",
]
