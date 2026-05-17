# 知曜内置 AI Agent 架构设计

> **For agentic workers:** Use superpowers:writing-plans to implement this spec task-by-task.

**Goal:** 将产品内置 AI 从「prompt-in/text-out 聊天机器人」升级为具备真实执行能力的 Agent，通过 DeepSeek function calling 驱动 ReAct 循环，让用户可以用自然语言完成学习规划、知识库管理、备考安排等操作。

**Architecture:** 新增 5 个文件（agent 路由、服务、工具层、上下文加载器、提示词），零改动现有代码。对话历史存 Redis（TTL 24h），不新建数据库表。工具调用轮使用 stream=False，最终回答轮使用 stream=True（SSE）。

**Tech Stack:** FastAPI + DeepSeek API (OpenAI-compatible, tools parameter) + Redis + 现有所有 service

---

## 1. 文件结构

| 文件 | 职责 |
|------|------|
| `app/api/v1/agent.py` | 路由：`POST /v1/agent/chat`，SSE 流式响应 |
| `app/services/agent_service.py` | ReAct 主循环，最多 5 轮工具调用，管理 Redis 对话历史 |
| `app/services/agent_tools.py` | 8 个工具的具体实现，内部调用现有 service |
| `app/services/agent_context.py` | 用户上下文加载器，为 system prompt 提供实时数据 |
| `app/llm/prompts/agent.py` | System Prompt 模板，四块结构 |
| `app/schemas/agent.py` | AgentChatRequest / AgentChatResponse schema |

现有文件改动：
- `app/api/v1/__init__.py`：注册 agent router

---

## 2. API 规格

```
POST /v1/agent/chat
Authorization: Bearer <token>
Content-Type: application/json
Accept: text/event-stream

请求体：
{
  "message": "帮我安排本周数学复习",
  "session_id": "optional-uuid"   // 不传则服务端生成新会话
}

SSE 响应格式：
data: {"delta": "根据你当前的学习状态"}
data: {"delta": "，数学还有 12 个知识点未掌握"}
data: {"done": true, "session_id": "xxx-uuid", "tools_called": ["diagnose_learning", "plan_study_schedule"]}
```

- `session_id` 前端保存，下轮对话带上实现多轮上下文
- `tools_called` 供前端展示「管家做了什么」
- 工具执行期间可推送中间状态：`data: {"thinking": "正在分析你的知识库…"}`

---

## 3. System Prompt 结构（四块）

```python
BLOCK_1_IDENTITY = """
你是「知曜」，专属学习管家。
服务对象：中国中高考/大学学生。
性格：温暖、简洁、务实，不废话，不说教。
语言：始终使用中文回复。
"""

BLOCK_2_USER_PROFILE = """
## 当前用户档案
姓名：{username}
年级：{grade}
主攻科目：{subjects}
连续学习：{streak_days} 天
今日任务：{done_tasks}/{total_tasks} 项已完成
近期考试：{upcoming_exam_name}（还有 {days_remaining} 天）
最需关注：{weakest_subject}（{learning_count} 个知识点待掌握）
"""

BLOCK_3_RULES = """
## 工作规则
1. 需要数据时先调工具，不凭猜测回答
2. 分析 + 规划类任务：先调 diagnose_learning，再调 plan_study_schedule
3. 执行写操作后，简洁告知用户做了什么（不要列清单，用自然语言）
4. 只处理学习相关请求；其他话题礼貌拒绝并引回学习
5. 回复保持简洁，重点突出，避免冗长
"""

BLOCK_4_CHECKIN = """
## 今日签到
{checkin_summary}
"""  # 有当日 check-in 时才注入
```

---

## 4. ReAct 循环逻辑

```python
MAX_TOOL_ROUNDS = 5

async def run(db, user_id, message, session_id) -> AsyncGenerator[str, None]:
    # 1. 加载上下文 + 历史
    context = await load_user_context(db, user_id)
    system = build_system_prompt(context)
    history = await load_history(session_id)   # Redis
    history.append({"role": "user", "content": message})

    # 2. 工具调用轮（stream=False）
    for round_num in range(MAX_TOOL_ROUNDS):
        response = await deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system}] + history,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            stream=False,
        )
        choice = response.choices[0]

        if choice.finish_reason == "tool_calls":
            tool_call = choice.message.tool_calls[0]
            yield f'data: {{"thinking": "正在执行：{tool_call.function.name}…"}}\n\n'
            
            try:
                result = await dispatch_tool(db, user_id, tool_call)
            except Exception as e:
                result = {"error": str(e)}   # 错误作为 tool result 返回，让 LLM 自行处理
            
            history.append(choice.message)
            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        else:
            break   # LLM 决定直接回答，退出工具循环

    # 3. 最终回答轮（stream=True）
    stream = await deepseek.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": system}] + history,
        stream=True,
    )
    
    full_reply = ""
    tools_called = [msg["tool_call_id"] ... ]  # 从 history 中提取
    
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        full_reply += delta
        yield f'data: {{"delta": "{delta}"}}\n\n'
    
    yield f'data: {{"done": true, "session_id": "{session_id}", "tools_called": {tools_called}}}\n\n'
    
    # 4. 持久化对话历史到 Redis
    history.append({"role": "assistant", "content": full_reply})
    await save_history(session_id, history)   # TTL 24h
```

**保护机制：**
- 5 轮工具调用后强制进入最终回答轮，不报错
- 工具执行异常 → 错误信息作为 tool result，LLM 自行决策
- Redis 不可用 → history 降级为空列表（单轮对话，不中断服务）

---

## 5. 8 个工具完整定义

### Tool 1: `get_full_context`
```json
{
  "name": "get_full_context",
  "description": "加载用户当前学习快照：KP 各掌握度数量、今日任务列表、近期考试、连续学习天数。需要整体了解用户状态时调用。",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```
实现：聚合 kp_service + task_service + exam_service 查询，返回压缩 JSON。

---

### Tool 2: `diagnose_learning`
```json
{
  "name": "diagnose_learning",
  "description": "分析用户学科弱点，返回每科的掌握情况、训练成绩、错题数量、最薄弱章节。用于制定计划前的诊断。",
  "parameters": {
    "type": "object",
    "properties": {
      "subject": {
        "type": "string",
        "description": "指定学科（如'数学'）。不传则分析全部学科。"
      }
    },
    "required": []
  }
}
```
实现：KP mastery 统计 + training_service 历史均分 + mistake_service 统计，返回结构化报告。

---

### Tool 3: `plan_study_schedule`
```json
{
  "name": "plan_study_schedule",
  "description": "根据用户弱点和考试压力批量创建学习任务，形成未来 N 天的复习计划。",
  "parameters": {
    "type": "object",
    "properties": {
      "subjects": {
        "type": "array",
        "items": {"type": "string"},
        "description": "需要规划的学科列表，如 ['数学', '物理']"
      },
      "days_ahead": {
        "type": "integer",
        "description": "规划天数，默认 7",
        "default": 7
      },
      "goal": {
        "type": "string",
        "description": "备考目标描述，如'备战期末考试'，用于任务优先级排序"
      }
    },
    "required": ["subjects"]
  }
}
```
实现：调 diagnose_learning 获取弱点 → 按弱点权重 + 考试紧迫度排序 → batch create tasks，返回已创建任务列表 + 每项安排理由。

---

### Tool 4: `manage_knowledge_points`
```json
{
  "name": "manage_knowledge_points",
  "description": "知识点的查询、批量更新掌握状态、创建新知识点。",
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["list", "update_mastery", "create"],
        "description": "list=查询, update_mastery=批量更新掌握度, create=创建新知识点"
      },
      "filters": {
        "type": "object",
        "description": "list 时的筛选条件",
        "properties": {
          "subject": {"type": "string"},
          "mastery_status": {"type": "string", "enum": ["learning", "reviewing", "mastered"]},
          "search": {"type": "string"}
        }
      },
      "updates": {
        "type": "object",
        "description": "update_mastery 时使用",
        "properties": {
          "kp_ids": {"type": "array", "items": {"type": "string"}},
          "new_mastery_status": {"type": "string", "enum": ["learning", "reviewing", "mastered"]}
        }
      },
      "new_kps": {
        "type": "array",
        "description": "create 时使用",
        "items": {
          "type": "object",
          "properties": {
            "title": {"type": "string"},
            "subject": {"type": "string"},
            "content": {"type": "string"},
            "mastery_status": {"type": "string", "enum": ["learning", "reviewing", "mastered"]}
          }
        }
      }
    },
    "required": ["action"]
  }
}
```
实现：调 kp_service 对应方法，返回受影响 KP 列表。

---

### Tool 5: `manage_tasks`
```json
{
  "name": "manage_tasks",
  "description": "任务的查询、创建、批量创建、完成标记。",
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["list_today", "create", "batch_create", "mark_done"],
        "description": "list_today=今日任务, create=创建单个, batch_create=批量创建, mark_done=标记完成"
      },
      "task_data": {
        "type": "object",
        "description": "create 时使用",
        "properties": {
          "title": {"type": "string"},
          "subject": {"type": "string"},
          "estimated_minutes": {"type": "integer"},
          "due_date": {"type": "string", "description": "YYYY-MM-DD"},
          "priority": {"type": "integer", "description": "1-5，5最高"}
        }
      },
      "tasks": {
        "type": "array",
        "description": "batch_create 时使用，结构同 task_data",
        "items": {"type": "object"}
      },
      "task_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "mark_done 时使用"
      }
    },
    "required": ["action"]
  }
}
```
实现：调 task_service 对应方法，返回任务列表或操作确认。

---

### Tool 6: `start_training`
```json
{
  "name": "start_training",
  "description": "为用户发起一次训练练习，自动选取最弱的知识点出题。",
  "parameters": {
    "type": "object",
    "properties": {
      "subject": {
        "type": "string",
        "description": "训练学科，如'数学'"
      },
      "bloom_levels": {
        "type": "array",
        "items": {"type": "integer"},
        "description": "布鲁姆层级列表，默认 [2,3,4]（理解/应用/分析）",
        "default": [2, 3, 4]
      },
      "question_count": {
        "type": "integer",
        "description": "题目数量，默认 5",
        "default": 5
      }
    },
    "required": ["subject"]
  }
}
```
实现：按 subject 筛选 mastery_status=learning 的 KP → 调 training_service.generate_questions，返回 session_id + 题目列表。

---

### Tool 7: `manage_exams`
```json
{
  "name": "manage_exams",
  "description": "考试的查询、创建和倒计时查看。",
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["list", "create", "countdown"],
        "description": "list=考试列表, create=创建考试, countdown=倒计时聚合"
      },
      "exam_data": {
        "type": "object",
        "description": "create 时使用",
        "properties": {
          "name": {"type": "string"},
          "subject": {"type": "string"},
          "exam_date": {"type": "string", "description": "YYYY-MM-DD"},
          "notes": {"type": "string"}
        }
      }
    },
    "required": ["action"]
  }
}
```
实现：调 exam_service 对应方法，返回考试列表（含 days_remaining）或创建确认。

---

### Tool 8: `generate_note`
```json
{
  "name": "generate_note",
  "description": "触发 AI 笔记生成任务，异步执行，用户可在笔记页查看结果。",
  "parameters": {
    "type": "object",
    "properties": {
      "topic": {
        "type": "string",
        "description": "笔记主题，如'导数的定义与计算方法'"
      },
      "subject": {
        "type": "string",
        "description": "所属学科，如'数学'"
      }
    },
    "required": ["topic", "subject"]
  }
}
```
实现：调 note_service.generate（触发 Celery 任务），返回 task_id + 提示语。

---

## 6. 用户上下文加载（agent_context.py）

每次请求从数据库实时拉取，约 2-3 次 DB 查询，注入 system prompt BLOCK 2：

```python
async def load_user_context(db, user_id) -> AgentContext:
    user = await get_user(db, user_id)
    today_tasks = await get_today_tasks(db, user_id)
    upcoming_exam = await get_nearest_exam(db, user_id)
    kp_stats = await get_kp_counts_by_mastery(db, user_id)   # 按掌握度聚合
    streak = await get_streak(db, user_id)
    checkin_today = await get_today_checkin(db, user_id)      # 可选
    
    return AgentContext(
        username=user.username,
        grade=user.grade,
        subjects=user.learning_profile.get("subjects", []),
        streak_days=streak,
        done_tasks=len([t for t in today_tasks if t.status == "done"]),
        total_tasks=len(today_tasks),
        upcoming_exam_name=upcoming_exam.name if upcoming_exam else None,
        days_remaining=upcoming_exam.days_remaining if upcoming_exam else None,
        weakest_subject=kp_stats.weakest_subject,
        learning_count=kp_stats.learning_count,
        checkin_summary=checkin_today.ai_summary if checkin_today else None,
    )
```

---

## 7. Redis 对话历史

```
Key:   agent_session:{session_id}
Value: JSON 序列化的 messages[] 列表
TTL:   86400 秒（24小时）

messages 格式（OpenAI-compatible）：
[
  {"role": "user", "content": "帮我安排本周复习"},
  {"role": "assistant", "content": null, "tool_calls": [...]},
  {"role": "tool", "tool_call_id": "xxx", "content": "{...}"},
  {"role": "assistant", "content": "好的，我为你安排了..."}
]
```

最大保留 20 条消息（超出时从头截断保留最新），防止 context 超限。

---

## 8. SPEC.md 更新内容

新增 Section 2.15：

```
### 2.15 Agent 模块 /v1/agent

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | /agent/chat | 发送消息，SSE 流式响应 | ✅ |

AgentChatRequest: { message: string, session_id?: string }
AgentChatResponse (SSE):
  data: {"delta": "..."} | {"thinking": "..."} | {"done": true, "session_id": "...", "tools_called": [...]}
```

---

## 9. 验收标准

- [ ] `POST /v1/agent/chat` 返回 `text/event-stream`
- [ ] 「帮我安排本周数学复习」→ 触发 diagnose_learning + plan_study_schedule，数据库实际创建任务
- [ ] 「把数学二次函数标成已掌握」→ 触发 manage_knowledge_points，DB 实际更新
- [ ] 「出5道物理题考我」→ 触发 start_training，返回 session_id
- [ ] 工具调用失败时不 500，LLM 给出降级回复
- [ ] 多轮对话：第二条消息能读到第一轮的上下文
- [ ] 5 轮工具调用上限正常触发，不死循环
