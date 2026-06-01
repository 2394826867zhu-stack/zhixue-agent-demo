from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class KBFileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID | None
    original_name: str
    file_type: str
    file_size_bytes: int
    processing_status: str  # pending / processing / done / failed
    chunk_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBFileListItem(BaseModel):
    id: uuid.UUID
    original_name: str
    file_type: str
    file_size_bytes: int
    processing_status: str
    chunk_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
