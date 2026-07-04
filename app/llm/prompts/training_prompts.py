SYSTEM_TRAINING = (
    "你是一位专业的学科教师，擅长根据布鲁姆分类法设计高质量的练习题和批改答案。"
    "输出必须是合法的JSON，不要添加任何额外说明。"
)

# 生成题目：根据知识点内容和bloom_level生成题目
QUESTION_GENERATE_PROMPT = """根据以下知识点，生成{count}道练习题。

知识点名称：{name}
知识点内容：{content}
关键公式：{key_formula}
布鲁姆层级：{bloom_level}

题型对照：
- remember/understand → fill_blank（填空/名词解释）
- apply/analyze → calculation（计算/推导）
- evaluate/create → essay（开放论述/费曼输出）

输出JSON数组，每个元素包含：
{{
  "question_type": "fill_blank|calculation|essay",
  "question_text": "题目正文（清晰完整）",
  "reference_answer": "参考答案（详细，包含步骤或要点）"
}}

要求：
1. 题目难度匹配bloom_level
2. fill_blank题目有明确的填写目标
3. calculation题目提供完整解题过程作为参考答案
4. essay题目答案包含评分要点（3-5个）
"""

# 组卷强制题型的格式规则（QA 走查实锤：choice 无格式约束 → LLM 出选择题不带选项，
# 前端 parseChoiceOptions 解析失败只能回退文本框）。question_text 是纯文本，选项必须嵌在题干。
_TYPE_FORMAT_RULES = {
    "choice": "题干末尾必须包含且仅包含四个选项，每个选项独占一行，格式严格为「A. 内容」「B. 内容」「C. 内容」「D. 内容」；reference_answer 以正确选项字母开头（如「B。因为…」）",
    "true_false": "题干为一个可判断对错的陈述句（不加问号）；reference_answer 以「正确」或「错误」开头再给一句理由",
    "fill_blank": "题干用「______」标注填空位置，有明确唯一的填写目标",
    "short_answer": "题目要求简要说明概念/原因，reference_answer 给出要点式答案",
    "proof": "题目要求证明一个命题，reference_answer 给出完整证明步骤",
    "calculation": "题目为计算/推导题，reference_answer 提供完整解题过程",
    "essay": "开放论述题，reference_answer 包含 3-5 个评分要点",
    "programming": "编程题给出明确的输入输出要求，reference_answer 给出参考代码 + 思路",
}


def forced_type_clause(qtype: str) -> str:
    """组卷「强制题型」附加指令：题型 + 该题型的输出格式规则。"""
    rule = _TYPE_FORMAT_RULES.get(qtype, "")
    tail = f"格式要求：{rule}" if rule else ""
    return f"\n\n【强制题型】请生成一道 {qtype} 题。{tail}"


# AI评分：根据参考答案评判用户答案
ANSWER_GRADE_PROMPT = """请评判以下学生答案，给出评分和反馈。

题目：{question_text}
参考答案：{reference_answer}
学生答案：{user_answer}
题型：{question_type}
布鲁姆层级：{bloom_level}

评分标准：
- fill_blank：关键词覆盖率 + 概念准确性
- calculation：解题思路 + 步骤完整性 + 最终结果
- essay：逻辑结构 + 要点覆盖 + 表达清晰度

输出JSON：
{{
  "score": 0-100的整数,
  "feedback": "具体反馈（指出正确点和不足，给出改进建议，100字以内）",
  "is_wrong": true/false（分数<60则为true）,
  "error_reason": "careless|concept|method|null"
}}

error_reason 含义（is_wrong=true 时必填）：
- careless：粗心（答案接近正确，计算/笔误失分）
- concept：概念不清（基础理解有漏洞）
- method：方法不会（思路错或不会用）
答对（is_wrong=false）时 error_reason 填 null。
"""


# v0.34 P1-5 · 错题孪生题生成（不是改数字，是变情境）
TWIN_QUESTION_PROMPT = """学生在下面这道题上答错了。请生成一道**同型异质**的孪生题，让学生再练一次。

原题：{original_question}
正确答案：{reference_answer}
学生答案：{user_answer}
错误原因：{error_reason}

要求：
1. 考察同一个知识点 + 同一种解题方法
2. **不要只改数字** — 要换情境/换问法/换变量（比如原题问"小明买苹果"，孪生题改为"工厂生产零件"）
3. 难度持平，不要变难也不要变简单
4. 如果原题是 fill_blank，孪生也是 fill_blank
5. 题目正文 ≤200 字，参考答案含解题步骤

输出 JSON（不要 ```json 包裹）：
{{
  "question_type": "<同原题>",
  "question_text": "孪生题正文",
  "reference_answer": "参考答案 + 解题步骤"
}}
"""
