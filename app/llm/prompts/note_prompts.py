SYSTEM_NOTE = """你是一位专业的学科知识整理专家，服务于中国初高中生和大学生。
你的任务是将知识内容整理为结构化的学习材料，帮助学生高效学习。
输出必须是中文。格式严格遵守用户要求。"""

# ── Step 1：内容提取 ──────────────────────────────────────────

EXTRACT_FROM_AI = """
用户想学习以下主题：
{topic}

请生成这个知识点的完整结构化内容，以JSON格式输出：

{{
  "title": "知识点标题",
  "subject": "学科（math/physics/chemistry/biology/history/chinese/english/politics/geography/other）",
  "core_content": "核心知识内容（详细描述，含原理、定义、公式）",
  "examples": ["例题或例子1", "例题或例子2"],
  "key_formulas": ["核心公式1", "核心公式2"],
  "difficulty_points": [
    {{"name": "难点名称", "reason": "为什么是难点"}}
  ],
  "knowledge_points": [
    {{
      "name": "知识点名称",
      "content": "该知识点的定义和要点",
      "key_formula": "核心公式（无则为空字符串）",
      "bloom_level": "remember/understand/apply/analyze"
    }}
  ]
}}

knowledge_points提取要求：
- 数量：3-8个
- 粒度：每个知识点是一个独立可测试的概念/公式/规律
- bloom_level根据认知复杂度判断：公式定义→remember，理解原理→understand，解题应用→apply，综合分析→analyze
"""

EXTRACT_FROM_CONTENT = """
以下是学生提供的学习材料内容：
{content}

请分析并以JSON格式输出结构化知识：

{{
  "title": "根据内容推断的标题",
  "subject": "学科（math/physics/chemistry/biology/history/chinese/english/politics/geography/other）",
  "core_content": "核心知识内容汇总",
  "key_formulas": ["核心公式1"],
  "difficulty_points": [
    {{"name": "难点名称", "reason": "为什么是难点"}}
  ],
  "knowledge_points": [
    {{
      "name": "知识点名称",
      "content": "该知识点的定义和要点",
      "key_formula": "核心公式（无则为空字符串）",
      "bloom_level": "remember/understand/apply/analyze"
    }}
  ]
}}

要求同上，知识点3-8个，粒度适中。
"""

# ── Step 2：三件套生成 ────────────────────────────────────────

FULL_VERSION_PROMPT = """
基于以下知识内容，生成【精读版笔记】。

知识内容：
{core_content}

要求：
- 格式：Markdown
- 结构：
  ## 核心概念
  ## 原理与推导
  ## 典型例题（含完整解析）
  ## 常见误区
  ## 知识联系

- 深度：适合初次学习，包含完整推导过程和例子
- 长度：800-2000字
"""

EXAM_VERSION_PROMPT = """
基于以下知识内容，生成【应试版笔记】。

知识内容：
{core_content}
核心公式：{key_formulas}

要求：
- 格式：Markdown
- 结构：
  ⭐ 必考考点（3-5条，直接背）
  📝 核心公式/结论
  ⚠️ 易错点
  🔑 答题关键词

- 风格：极度精炼，去除所有推导过程，只留结论
- 长度：精读版的30%-40%
- 目标：学生考前5分钟快速扫一遍能直接上考场
"""

GRAPH_MERMAID_PROMPT = """
基于以下知识点列表，生成【知识图谱】的Mermaid代码。

知识点：
{knowledge_points_names}
标题：{title}

要求：
- 格式：mindmap语法
- 根节点：知识点主题
- 二级节点：主要分类（3-5个）
- 三级节点：具体知识原子
- 总节点数：8-15个
- 只输出Mermaid代码，不要任何解释

示例格式：
mindmap
  root((主题))
    分类A
      知识点1
      知识点2
    分类B
      知识点3
"""

# ── 闪卡生成 ─────────────────────────────────────────────────

FLASHCARD_GENERATE_PROMPT = """
为以下知识点生成学习闪卡，以JSON数组输出：

知识点名称：{name}
知识点内容：{content}
核心公式：{key_formula}
布鲁姆层次：{bloom_level}

生成2-3张闪卡，覆盖不同角度，JSON格式：
[
  {{
    "card_type": "concept/formula/application",
    "front": "问题（简洁，一句话）",
    "back": "答案（简洁，核心要点）"
  }}
]

card_type说明：
- concept：概念定义类（"什么是X？"）
- formula：公式记忆类（"X的计算公式是？"）
- application：应用判断类（"什么情况下使用X？"）

要求：
- front必须是学生能独立作答的问题
- back简洁，不超过100字
- 不同card_type各出一张
"""
