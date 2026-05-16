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
  "is_wrong": true/false（分数<60则为true）
}}
"""
