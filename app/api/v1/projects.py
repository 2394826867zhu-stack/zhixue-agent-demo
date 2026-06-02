"""项目系统 API — v2 PRD 3.4 + 9.1 + 9.2

端点设计完全对齐 PRD 行 311-426。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectReorderRequest,
    ProjectInitDraft, ProjectPreviewCard, ProjectConfirmRequest,
    ProjectListItem, ProjectListResponse, ProjectDetail,
    ProjectDataSummary,
    TreeNodeOut, TreeNodeBubble,
    PhaseOut, MilestoneOut, PhaseSummaryItem,
)
from app.services.project_service import project_service
from app.services.project_tree_service import project_tree_service
from app.schemas.envelope import Envelope
from pydantic import BaseModel

router = APIRouter(prefix="/projects", tags=["项目系统"])


class ProjectDeleteResult(BaseModel):
    deleted: bool


class ProjectReorderResult(BaseModel):
    reordered: bool


class TreeGenerateResult(BaseModel):
    nodes_added: int


def ok(data):
    return {"code": 200, "message": "success", "data": data}


# ── 列表 / 详情 ─────────────────────────────────────────────────────

@router.get("", summary="项目列表", response_model=Envelope[ProjectListResponse])
async def list_projects(
    status: str | None = Query(default=None, description="active|paused|completed|archived"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects, total = await project_service.list_projects(
        db, str(user.id), status=status, page=page, page_size=page_size
    )
    items = [
        ProjectListItem(
            id=p.id,
            name=p.name,
            summary=p.summary,
            source=p.source,
            subject=p.subject,
            status=p.status,
            completion_pct=p.completion_pct,
            mastery_pct=p.mastery_pct,
            sort_order=p.sort_order,
            target_completion_date=p.target_completion_date,
            started_at=p.started_at,
            updated_at=p.updated_at,
            phases=[
                PhaseSummaryItem(
                    name=ph.name,
                    is_current=ph.is_current,
                    completion_pct=ph.completion_pct,
                )
                for ph in sorted(p.phases, key=lambda x: x.sort_order)
            ],
            milestone_count=len(p.milestones),
        )
        for p in projects
    ]
    return ok(
        ProjectListResponse(
            items=items, total=total, page=page, page_size=page_size
        ).model_dump()
    )


@router.get("/{project_id}", summary="项目详情（含时间线+phase+milestone）", response_model=Envelope[ProjectDetail])
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await project_service.get_project(db, project_id, str(user.id))
    # 项目下树节点统计
    summary = await project_service.get_data_summary(db, project_id, str(user.id))
    current_phase = next((p for p in proj.phases if p.is_current), None)
    detail = ProjectDetail(
        id=proj.id,
        name=proj.name,
        summary=proj.summary,
        source=proj.source,
        subject=proj.subject,
        status=proj.status,
        completion_pct=proj.completion_pct,
        mastery_pct=proj.mastery_pct,
        init_context=proj.init_context,
        target_completion_date=proj.target_completion_date,
        weekly_hours=proj.weekly_hours,
        started_at=proj.started_at,
        completed_at=proj.completed_at,
        created_at=proj.created_at,
        updated_at=proj.updated_at,
        phases=[PhaseOut.model_validate(p) for p in proj.phases],
        milestones=[MilestoneOut.model_validate(m) for m in proj.milestones],
        current_phase_id=current_phase.id if current_phase else None,
        tree_node_count=summary.tree_nodes_total,
        tree_completed_count=summary.tree_nodes_completed,
    )
    return ok(detail.model_dump(mode="json"))


# ── 创建 ────────────────────────────────────────────────────────────

@router.post("", summary="直接创建项目（结构化）", response_model=Envelope[ProjectListItem])
async def create_project(
    data: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await project_service.create_project(db, str(user.id), data)
    return ok(ProjectListItem.model_validate(proj).model_dump(mode="json"))


@router.post("/from-agent-dialog/preview", summary="Agent 对话式创建 · 计算预览卡（结构化输入）", response_model=Envelope[ProjectPreviewCard])
async def preview_from_dialog(
    draft: ProjectInitDraft,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD 行 333：用户确认前必须看到 Agent 理解的项目骨架。"""
    preview = await project_service.create_from_draft(db, str(user.id), draft)
    return ok(preview.model_dump(mode="json"))


@router.post("/from-agent-dialog/llm-preview", summary="Agent 对话式创建 · LLM 整理自然语言", response_model=Envelope[ProjectPreviewCard | None])
async def llm_preview_from_dialog(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户自然语言对话 → LLM 整理 → 结构化预览卡。
    PRD 9.2 行 624：Agent 把用户表达整理为结构化项目描述。
    """
    dialog = (body or {}).get("dialog") or ""
    if not dialog.strip():
        return ok(None)
    preview = await project_service.draft_from_dialog(db, str(user.id), dialog)
    return ok(preview.model_dump(mode="json"))


@router.post("/from-agent-dialog/confirm", summary="Agent 对话式创建 · 确认生成项目", response_model=Envelope[ProjectListItem])
async def confirm_from_dialog(
    req: ProjectConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD 行 334-339：用户确认 preview 后正式生成。"""
    proj = await project_service.confirm_preview(db, str(user.id), req)
    return ok(ProjectListItem.model_validate(proj).model_dump(mode="json"))


# ── 更新 / 删除 / 排序 ──────────────────────────────────────────────

@router.patch("/{project_id}", summary="编辑（仅名+简介，PRD 9.1）", response_model=Envelope[ProjectListItem])
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await project_service.update_project(db, project_id, str(user.id), data)
    return ok(ProjectListItem.model_validate(proj).model_dump(mode="json"))


@router.delete("/{project_id}", summary="删除项目（前端走系统确认弹窗）", response_model=Envelope[ProjectDeleteResult])
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await project_service.delete_project(db, project_id, str(user.id))
    return ok({"deleted": True})


@router.post("/reorder", summary="拖动排序", response_model=Envelope[ProjectReorderResult])
async def reorder(
    req: ProjectReorderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await project_service.reorder(db, str(user.id), req)
    return ok({"reordered": True})


# ── 数据栏 ──────────────────────────────────────────────────────────

@router.get("/{project_id}/data", summary="项目数据栏（环状图）", response_model=Envelope[ProjectDataSummary])
async def get_data(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await project_service.get_data_summary(db, project_id, str(user.id))
    return ok(summary.model_dump())


# ── 树状路径 ────────────────────────────────────────────────────────

@router.post("/{project_id}/tree/generate", summary="LLM 生成树节点（项目创建后由 Agent 调用）", response_model=Envelope[TreeGenerateResult])
async def generate_tree(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD 9.1 行 621：节点由 Agent 自动添加。
    幂等：已有节点则跳过返回 0。
    """
    count = await project_service.generate_tree_nodes(db, project_id, str(user.id))
    return ok({"nodes_added": count})


@router.get("/{project_id}/tree", summary="树状路径节点（扁平列表）", response_model=Envelope[list[TreeNodeOut]])
async def get_tree(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    nodes = await project_tree_service.get_tree(db, project_id, str(user.id))
    return ok([n.model_dump(mode="json") for n in nodes])


@router.get("/{project_id}/tree/nodes/{node_id}", summary="节点点击气泡详情", response_model=Envelope[TreeNodeBubble])
async def get_node_bubble(
    project_id: str,
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bubble = await project_tree_service.get_node_bubble(db, project_id, node_id, str(user.id))
    return ok(bubble.model_dump(mode="json"))
