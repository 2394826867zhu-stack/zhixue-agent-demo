"""学习内核 P1 · 先修关系推断提示词。"""

SYSTEM_PREREQUISITE = (
    "你是教学设计专家，分析知识点之间的先修（前置）关系。"
    "先修 = 学 B 之前必须先掌握 A。只输出强因果关系。只输出 JSON，不要 ``` 包裹。"
)

INFER_PREREQUISITES_PROMPT = """以下是同一批新学的知识点（带序号）：

{kp_list}

请分析它们之间的先修关系，JSON 输出：
{{
  "edges": [
    {{"from": 序号, "to": 序号, "confidence": 0.7-1.0, "reason": "简述"}}
  ]
}}
要求：from 是 to 的先修；只保留 confidence≥0.7 的强关系；edges 数不超过知识点数的 1.5 倍；不得自环。"""
