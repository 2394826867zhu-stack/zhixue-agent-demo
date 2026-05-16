# 智学Agent · 后端服务

## 快速启动

### 1. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY 和 JWT_SECRET_KEY
```

### 2. 启动基础设施（PostgreSQL + Redis）
```bash
cd docker
docker compose up db redis -d
```

### 3. 初始化数据库
```bash
pip install -r requirements.txt
alembic upgrade head
```

### 4. 启动开发服务器
```bash
uvicorn app.main:app --reload --port 8000
```

访问 API 文档：http://localhost:8000/docs

---

## 模块开发进度

| 模块 | 状态 |
|------|------|
| Auth（注册/登录/JWT） | ✅ 完成 |
| Notes（笔记三件套） | 🔲 待开发 |
| Vocabulary（词汇库） | 🔲 待开发 |
| Mistakes（错题系统） | 🔲 待开发 |
| Quiz（自动出题） | 🔲 待开发 |
| Progress（进度/周报） | 🔲 待开发 |
| Guidance（引导答疑） | 🔲 待开发 |

## 运行测试
```bash
pytest tests/ -v
```

## 数据库迁移
```bash
# 新建迁移
alembic revision --autogenerate -m "描述"
# 执行迁移
alembic upgrade head
# 回滚
alembic downgrade -1
```
