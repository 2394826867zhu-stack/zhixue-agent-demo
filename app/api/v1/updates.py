"""Expo Updates Manifest 端点（OTA 推送）"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import json
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/updates", tags=["updates"])


@router.get("", summary="Expo Updates Manifest")
async def get_manifest(
    user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Expo 客户端每次启动时调用此端点拉取 manifest，决定是否下载新的 OTA 更新包。
    返回格式遵循 Expo Updates Protocol v0.
    """
    # 当前应用版本
    version = "1.0.0"

    # 这里应该从数据库查询最新的可用版本
    # 目前硬编码最新的 OTA 包信息
    return {
        "runtimeVersion": version,
        "id": "139618eb-db11-46da-979e-2f5050d56803",  # Update group ID from EAS
        "createdAt": "2026-06-23T11:05:00.000Z",
        "isEmbedded": False,
        "launchAsset": {
            "key": "bundle-1",
            "contentType": "application/javascript",
            "url": "https://u.expo.dev/45e82f50-354e-4d7d-a475-7edb3dc0c653/android/019ef42a-09d7-7a10-b9d6-04c8010c6423/bundle.js"
        },
        "assets": [
            {
                "key": f"asset-{i}",
                "contentType": "application/octet-stream",
                "url": f"https://u.expo.dev/45e82f50-354e-4d7d-a475-7edb3dc0c653/android/019ef42a-09d7-7a10-b9d6-04c8010c6423/assets/{i}"
            }
            for i in range(30)  # 占位：实际资源从 EAS CDN 提供
        ],
        "metadata": {
            "branchName": "preview",
            "commitHash": "e88d1da7f3ad0936392718247cb86dcc88cf9a38",
            "runtimeVersion": version
        }
    }
