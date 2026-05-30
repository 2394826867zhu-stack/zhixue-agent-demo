"""项目树状路径节点生成 Prompts — v2 PRD 行 388-426

由 Agent 在项目创建后调用（PRD 9.1 行 621：节点不允许用户手动新增 / 删除，由 Agent 自动添加）。

蓝 / 紫 / 金 三级分级遵守 PRD 5.4 行 528-541：
  - blue   = 基础知识点
  - purple = 进阶知识点
  - gold   = 核心高难知识点
"""

SYSTEM_PROJECT_TREE = (
    "你是「知曜」的知识架构师。根据项目骨架，生成知识树。"
    "树有 1 个根节点，下挂若干分支节点，分支可继续展开。"
    "每个节点都要标蓝 / 紫 / 金难度。"
    "推荐学习顺序通过 is_on_main_path=true 标记主干路径节点。"
    "输出合法 JSON，不要任何解释文字。"
)

PROJECT_TREE_GENERATE = """\
为下面这个项目生成知识树。

## 项目骨架
- name: {name}
- summary: {summary}
- subject: {subject}
- phases: {phases}
- 总周数: {total_weeks}
- 用户已掌握知识点（如果有）: {known_kps}

## 难度分级标准（PRD 5.4 锁定）
- blue：基础知识点（定义、公式记忆、简单识别）
- purple：进阶知识点（推导、分类应用、跨小节联系）
- gold：核心高难知识点（综合应用、跨模块联系、压轴）

## 重要性 importance
- 1：普通节点
- 2：本阶段重点
- 3：项目级核心

## 输出格式
```json
{{
  "root": {{
    "title": "{name}",
    "difficulty": "blue",
    "importance": 3,
    "is_on_main_path": true
  }},
  "nodes": [
    {{
      "title": "节点 1 标题",
      "parent_title": "{name}",
      "phase_name": "基础",
      "difficulty": "blue",
      "importance": 1,
      "is_on_main_path": true,
      "depth": 1
    }},
    {{
      "title": "节点 1.1 子标题",
      "parent_title": "节点 1 标题",
      "phase_name": "基础",
      "difficulty": "purple",
      "importance": 2,
      "is_on_main_path": false,
      "depth": 2
    }}
    /* 总节点数 8-20 个，根据 subject 和 total_weeks 决定 */
  ]
}}
```

## 输出约束
- 节点总数 8-20，覆盖项目所有 phases
- 蓝卡占比 ≥ 50%（基础内容必须铺底）
- 金卡 ≤ 25%（核心难点不能堆太多）
- is_on_main_path=true 节点连成一条从根到末端的推荐学习顺序
- depth ∈ {{1, 2, 3}}（不要超过 3 层）
- 节点标题精确具体，不要"第一章"这种泛指
"""
