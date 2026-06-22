# SSE 连接池生命周期重构（P0-4 完整修复设计）— 2026-06-23

> 状态：**设计稿，待项目主审 + 压测验证后实施**。本批次已落地"外科止血"（见下），完整重构因
> 爆破半径大 + 需真实负载验证，单独成项推进，不在自驱循环里盲改。

## 背景

`app/services/agent_service.py::run()` 是 SSE 异步生成器，接收请求级 `Depends(get_db)` 会话，
全程贯穿多轮 LLM（describe_image / call_with_tools / stream_response）。SQLAlchemy 异步会话在
首次 execute 时从连接池签出连接、直到 commit/rollback 才归还。若任一读/写事务跨越 LLM await 未结清，
该连接被占满整轮对话。pool_size=10 + max_overflow=20 = 30 连接，**~31 并发对话即耗尽全站连接池**，
登录/列表等无关请求集体阻塞超时。组卷 `compose_quiz` 同理（已在本批修复）。

## 本批已落地（外科止血，低风险）

- **P0-5 compose_quiz**：先 commit 会话释放连接 → N 次 LLM 出题循环期间零连接占用 → 末尾一次性写题。
  （`training_service.py`，含测试 `test_compose_quiz_connpool.py`）
- **P0-4 SSE 最长窗口**：`run()` 在进入 `stream_response`（整段流式回答，数十秒，最长持有窗口）前
  显式 `db.commit()` 释放连接。工具轮写入已各自 commit；此 commit 结清残留只读事务。
  这覆盖了**单次对话最长的连接持有窗口**，但不是全量修复。

## 完整修复设计（待实施）

目标：`run()` 全生命周期内，**任何 LLM await 期间都不持有 DB 连接**。

### 方案 A（推荐）：run() 自管短会话，弃用请求级长连接
- 路由 `agent_chat` 不再把 `Depends(get_db)` 会话传进 `run()`；改传 `async_session_factory`。
- `run()` 内每个"DB 阶段"用 `async with async_session_factory() as s:` 开短会话：
  - 阶段1 上下文加载（load_user_context / studyspace / rag_search / record_retrieval / history upsert）
  - 阶段2 每次 `dispatch_tool` 一个短会话（工具内部已 commit，包一层 `async with` 即用即还）
  - 阶段3 stream 后的收尾写入（timeline / history / agent_state）
- LLM 调用全部在 `async with` 块**之外** → await 期间无连接。
- 改造面：`load_user_context` / `rag_service.search` / `record_retrieval` / `dispatch_tool` /
  `agent_state_service` / `agent_history_service` 均接收 session 入参，需确认都能在短会话内自洽
  （目前它们都接 `db` 参数，改为接 factory 开的短 session 即可，签名不变）。

### 方案 B（折中）：保留请求会话，但在每个 LLM await 前后 commit/expunge
- 风险：易漏点，且请求会话仍占着 get_db 的生命周期连接（FastAPI 依赖未释放）。不推荐。

## 验收闸（实施时必过）

1. **压测复现 + 验证**：k6/自定义 SSE 脚本，从 10→50 VU 阶梯并发 `/agent/chat`，
   断言：① 连接池不耗尽（监控 `pg_stat_activity` / pool checkedout）；
   ② 无关接口（登录/列表）P95 不退化 >2×。修复前应能复现耗尽，修复后通过。
2. **回归**：现有 agent/training 全套 pytest 绿（含 `db=None` 的 unit 流）。
3. **SSE 契约不变**：thinking/delta/done/error 事件序列与 sources 字段不变。

## 不做什么（禁表面修复）

- ❌ 仅调大 pool_size/max_overflow —— band-aid，不解决"连接被长占"根因，只把耗尽阈值后移。
