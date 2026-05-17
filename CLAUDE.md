@../SPEC.md

# 后端开发规范（Claude Code 专用）

## 身份
我是知曜·智学Agent **后端 Agent**，只负责 `zhiyao-backend/` 目录，不修改任何前端文件。

## 新会话启动清单
1. 读根目录 `SPEC.md` → Section 0 了解冲刺状态，Section 3 了解前端挂起的 API 需求
2. 运行 `git log --oneline -5` 确认最新提交
3. 告知用户：当前状态 + 建议下一步

## 技术栈
- FastAPI + Python 3.11
- PostgreSQL 16 + pgvector（异步 SQLAlchemy 2.x）
- Redis 7（缓存 + Celery broker）
- Celery（异步任务：笔记生成、AI排序）
- Alembic（数据库迁移，每个模块独立迁移文件）
- Claude claude-opus-4-7（主 LLM）/ GPT-4o（备用）

## 项目结构
```
app/
  api/v1/        # 路由层（薄，只做请求/响应转换）
  services/      # 业务逻辑（所有 LLM 调用在这里）
  models/        # SQLAlchemy ORM 模型
  schemas/       # Pydantic 请求/响应 Schema
  llm/prompts/   # 提示词（独立文件，便于调优）
  tasks/         # Celery 异步任务
  core/          # database / redis / security / exceptions
```

## 开发规则
- 新端点必须：写在对应 `api/v1/xxx.py` → 服务逻辑写在 `services/xxx_service.py` → Schema 写在 `schemas/xxx.py`
- 涉及数据库变更 → 生成 Alembic 迁移文件，不手动改表
- 新端点上线后 → 在根目录 `SPEC.md` 对应位置更新（方法/路径/描述/请求体/响应体）
- 统一响应格式：`{"code": 200, "message": "success", "data": ...}`
- 错误通过 `AppError(code, message, http_status)` 抛出

## 迁移链（勿乱序）
001(users) → 002(notes/kp/flashcards) → 003(fsrs_state) → 004(training) → 005(retry字段) → 006(tasks/pomodoro) → 007(guidance) → 008(下一个)
