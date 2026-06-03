"""审计 L5 · 文件下载 owner 隔离回归：他人无法下载（IDOR 防护）。

GET /v1/files/{filename} 此前仅校验登录、不校验归属——任何登录用户知道他人随机
文件名即可下载。迁移 050 加 file_uploads 归属表后，有归属记录的文件仅 owner 可下。
"""
import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.file_upload import FileUpload


async def _auth(client: AsyncClient, email: str) -> str:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_file_download_owner_isolation(client: AsyncClient, db: AsyncSession):
    token_a = await _auth(client, "filea@zhiyao.ai")
    token_b = await _auth(client, "fileb@zhiyao.ai")
    user_a = (await db.execute(select(User).where(User.email == "filea@zhiyao.ai"))).scalar_one()

    filename = f"{uuid.uuid4().hex}.png"
    os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
    fp = os.path.join(settings.LOCAL_UPLOAD_DIR, filename)
    with open(fp, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n_audit_test_")
    db.add(FileUpload(user_id=user_a.id, stored_filename=filename,
                      original_name="x.png", file_type="image"))
    await db.commit()

    try:
        # owner A 可下载
        ra = await client.get(f"/v1/files/{filename}", headers={"Authorization": f"Bearer {token_a}"})
        assert ra.status_code == 200, ra.text
        # 他人 B 被拒（404，不泄漏文件存在性）—— 修复前会 200（IDOR）
        rb = await client.get(f"/v1/files/{filename}", headers={"Authorization": f"Bearer {token_b}"})
        assert rb.status_code == 404
    finally:
        os.remove(fp)
