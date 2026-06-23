"""Expo Updates Protocol v0 manifest schema。

注意：此端点**不**走统一 Envelope 包裹——Expo 客户端按 Expo Updates Protocol
规定的固定 manifest 形状解析，外层不能套 {code,message,data}。但仍声明
response_model 让 OpenAPI 契约诚实（SDD 契约闸要求，避免空 {} → codegen any）。
"""
from pydantic import BaseModel


class ManifestAsset(BaseModel):
    key: str
    contentType: str
    url: str


class ManifestMetadata(BaseModel):
    branchName: str
    commitHash: str
    runtimeVersion: str


class ExpoManifestOut(BaseModel):
    runtimeVersion: str
    id: str
    createdAt: str
    isEmbedded: bool
    launchAsset: ManifestAsset
    assets: list[ManifestAsset]
    metadata: ManifestMetadata
