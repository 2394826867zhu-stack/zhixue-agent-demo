import uuid
import os
import base64
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.note import Note
from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.schemas.note import NoteGenerateRequest, NoteUploadRequest
from app.core.redis import get_redis
from app.core.exceptions import NotFoundError, PermissionDeniedError, LLMError
from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PDF_TYPE = "application/pdf"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class NoteService:

    async def create_from_ai(self, db: AsyncSession, user_id: str, data: NoteGenerateRequest) -> dict:
        """主入口：AI主动生成"""
        note = Note(
            user_id=uuid.UUID(user_id),
            title=data.topic[:50],
            subject=data.subject,
            source_type="ai_generated",
            source_input=data.topic,
            status="processing",
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        # 触发 Celery 异步任务
        from app.tasks.note_tasks import process_note
        process_note.delay(str(note.id), user_id)

        return {"note_id": str(note.id), "status": "processing"}

    async def create_from_text(self, db: AsyncSession, user_id: str, data: NoteUploadRequest) -> dict:
        """次入口：用户粘贴文字"""
        note = Note(
            user_id=uuid.UUID(user_id),
            title=data.title,
            subject=data.subject,
            source_type="text",
            source_input=data.content,
            status="processing",
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        from app.tasks.note_tasks import process_note
        process_note.delay(str(note.id), user_id)

        return {"note_id": str(note.id), "status": "processing"}

    async def create_from_file(self, db: AsyncSession, user_id: str, file_bytes: bytes, content_type: str, filename: str) -> dict:
        """次入口：用户上传图片或PDF"""
        if len(file_bytes) > MAX_FILE_SIZE:
            from app.core.exceptions import ValidationError
            raise ValidationError("文件大小不能超过20MB")

        source_type = "image" if content_type in ALLOWED_IMAGE_TYPES else "pdf"

        # 保存文件
        upload_dir = settings.LOCAL_UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = f"{uuid.uuid4()}{os.path.splitext(filename)[-1]}"
        file_path = os.path.join(upload_dir, safe_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # PDF：提取前5页文字
        text_content = None
        if source_type == "pdf":
            text_content = _extract_pdf_text(file_path, max_pages=5)
            if not text_content.strip():
                from app.core.exceptions import ValidationError
                raise ValidationError("未能从PDF中提取到文字，请上传可复制文字的PDF或改用图片/文本上传")

        note = Note(
            user_id=uuid.UUID(user_id),
            source_type=source_type,
            source_file_url=file_path,
            source_input=text_content,  # PDF文字内容，image时为空
            status="processing",
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        from app.tasks.note_tasks import process_note
        process_note.delay(str(note.id), user_id)

        return {"note_id": str(note.id), "status": "processing"}

    async def get_task_status(self, note_id: str, user_id: str, db: AsyncSession) -> dict:
        note = await self._get_note(db, note_id, user_id)
        redis = await get_redis()
        cached = await redis.hgetall(f"note_task:{note_id}")

        default_progress = 100 if note.status in ("done", "failed") else 0
        default_message = {
            "done": "完成",
            "failed": "处理失败，请重新上传或稍后重试",
        }.get(note.status, "处理中...")

        return {
            "note_id": note_id,
            "status": note.status,
            "progress": int(cached.get("progress", default_progress)),
            "message": cached.get("message", default_message),
        }

    async def get_note(self, db: AsyncSession, note_id: str, user_id: str) -> Note:
        return await self._get_note(db, note_id, user_id, with_kps=True)

    async def list_notes(self, db: AsyncSession, user_id: str, subject: str | None, page: int, page_size: int) -> dict:
        query = select(Note).where(Note.user_id == uuid.UUID(user_id))
        if subject:
            query = query.where(Note.subject == subject)
        query = query.order_by(Note.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        notes = result.scalars().all()

        # 为每条笔记附加知识点数量
        items = []
        for note in notes:
            count_result = await db.execute(
                select(func.count()).where(
                    KnowledgePoint.user_id == uuid.UUID(user_id),
                    KnowledgePoint.note_id == note.id,
                )
            )
            kp_count = count_result.scalar() or 0
            items.append({"note": note, "kp_count": kp_count})

        return {"items": items, "page": page, "page_size": page_size}

    async def delete_note(self, db: AsyncSession, note_id: str, user_id: str):
        note = await self._get_note(db, note_id, user_id)
        await db.delete(note)
        await db.commit()

    async def generate_flashcards(self, db: AsyncSession, note_id: str, user_id: str) -> dict:
        """用户触发：为该笔记的所有知识点生成闪卡（联动入口）"""
        from app.core.exceptions import ValidationError

        # SELECT FOR UPDATE 锁定 note 行，防止并发重复生成
        uid = uuid.UUID(user_id)
        locked = await db.execute(
            select(Note)
            .where(Note.id == uuid.UUID(note_id), Note.user_id == uid)
            .with_for_update()
        )
        note = locked.scalar_one_or_none()
        if not note:
            raise NotFoundError("笔记")
        if note.status != "done":
            raise ValidationError("笔记还在处理中，请稍后再试")
        if note.flashcards_generated:
            return {"created": 0, "knowledge_points": 0, "skipped": True}

        result = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.user_id == uid,
                KnowledgePoint.note_id == note.id,
            )
        )
        kps = result.scalars().all()

        if not kps:
            raise ValidationError("该笔记暂无可用知识点")

        from app.llm.client import llm_client
        from app.llm.prompts.note_prompts import FLASHCARD_GENERATE_PROMPT, SYSTEM_NOTE
        import json

        created_count = 0
        for kp in kps:

            try:
                raw = await llm_client.generate(
                    FLASHCARD_GENERATE_PROMPT.format(
                        name=kp.name,
                        content=kp.content or "",
                        key_formula=kp.key_formula or "无",
                        bloom_level=kp.bloom_level,
                    ),
                    system=SYSTEM_NOTE,
                )
                cards_data = _parse_json_array(raw)
                for card in cards_data:
                    flashcard = Flashcard(
                        user_id=uuid.UUID(user_id),
                        knowledge_point_id=kp.id,
                        card_type=card.get("card_type", "concept"),
                        front=card.get("front", ""),
                        back=card.get("back", ""),
                    )
                    db.add(flashcard)
                    created_count += 1
            except Exception as e:
                logger.warning(f"Failed to generate flashcards for KP {kp.id}: {e}")

        note.flashcards_generated = True
        await db.commit()

        return {"created": created_count, "knowledge_points": len(kps)}

    async def _get_note(self, db: AsyncSession, note_id: str, user_id: str, *, with_kps: bool = False) -> Note:
        query = select(Note).where(Note.id == uuid.UUID(note_id))
        if with_kps:
            query = query.options(selectinload(Note.knowledge_points))
        result = await db.execute(query)
        note = result.scalar_one_or_none()
        if not note:
            raise NotFoundError("笔记")
        if str(note.user_id) != user_id:
            raise PermissionDeniedError()
        return note


def _extract_pdf_text(file_path: str, max_pages: int = 5) -> str:
    """提取PDF前N页文字"""
    try:
        import pypdf
        text_parts = []
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for i, page in enumerate(reader.pages[:max_pages]):
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        logger.warning("pypdf not installed, PDF text extraction skipped")
        return ""
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
        return ""


def _parse_json_array(text: str) -> list:
    import json
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        result = json.loads(text)
        return result if isinstance(result, list) else []
    except Exception:
        return []


note_service = NoteService()
