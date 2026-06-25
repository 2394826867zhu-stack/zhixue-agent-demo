"""学科两层分类法 + 领域模板（项目创建体系 v3 · INC-B）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §6
- 两层分类：8 大类 > 细分 + 自定义（subject 存 "{category} > {subject}"）。
- 大类参与框架形状决策（D8）：大类 → 领域结构骨架，注入 F1 生成器（INC-C）。
- subject 仍只是数据标签；大类定结构、goal_type 定覆盖。
- 兼容存量自由字符串：parse_category 读时按关键词推断，**无需一次性数据迁移**
  （读时推断即 spec §6.4 的"渐进映射"，比批量 SQL UPDATE 更稳、覆盖所有变体）。

纯逻辑，无 DB / 无 IO。
"""
from __future__ import annotations

# ── 大类常量 ──
CAT_LANGUAGE = "语言文学"
CAT_STEM = "数理科学"
CAT_CS = "计算机与工程"
CAT_HUMANITIES = "文史哲社"
CAT_LIFE = "生命科学"
CAT_BUSINESS = "商科经济"
CAT_ARTS = "艺术设计"
CAT_CUSTOM = "自定义"

ALL_CATEGORIES = [
    CAT_LANGUAGE, CAT_STEM, CAT_CS, CAT_HUMANITIES,
    CAT_LIFE, CAT_BUSINESS, CAT_ARTS, CAT_CUSTOM,
]

# ── 大类 → 细分预置（spec §6.1）──
CATEGORY_SUBJECTS: dict[str, list[str]] = {
    CAT_LANGUAGE: ["汉语/语文", "英语", "日语", "韩语", "法语/德语/西语", "其他语言"],
    CAT_STEM: ["数学", "物理", "化学", "统计与概率"],
    CAT_CS: ["计算机科学", "软件工程", "人工智能/机器学习", "数据科学", "其他工程"],
    CAT_HUMANITIES: ["历史", "地理", "政治/道法", "哲学", "社会学/法学"],
    CAT_LIFE: ["生物", "医学/护理/药学"],
    CAT_BUSINESS: ["经济学", "金融/会计", "管理学/市场营销"],
    CAT_ARTS: ["音乐", "美术/设计/建筑"],
}

# ── 大类 → 领域结构骨架（注入 F1 system prompt，spec §6.2）──
# 与 live project_framework.py 的示例保持一致（语言/理科/编程）。
DOMAIN_TEMPLATES: dict[str, str] = {
    CAT_LANGUAGE: "语音 → 词汇 → 语法 → 听说读写（按 CEFR 等级维度递进）",
    CAT_STEM: "概念 → 定理/公式 → 推导 → 应用与解题",
    CAT_CS: "语法/概念 → 数据结构/范式 → 工程实践 → 项目实战",
    CAT_HUMANITIES: "时代/脉络 → 事件/人物 → 史料/论证 → 评析与观点",
    CAT_LIFE: "结构/系统 → 机制/过程 → 调控/相互作用 → 临床/应用",
    CAT_BUSINESS: "概念/原理 → 模型/方法 → 案例分析 → 实务应用",
    CAT_ARTS: "基础/元素 → 技法/原理 → 风格/流派 → 创作实践",
}
# 自定义/未知大类 → 通用骨架（不崩）
GENERIC_TEMPLATE = "概念 → 原理/方法 → 应用实践"

# ── 存量自由字符串 → 大类 的关键词推断（兼容旧 27 项 flat SUBJECTS + 常见自由输入）──
# 顺序敏感：先 STEM（"考研数学"→数学），再 CS / LANGUAGE …
_KEYWORD_CATEGORY: list[tuple[tuple[str, ...], str]] = [
    (("数学", "高等数学", "线性代数", "概率", "统计", "微积分", "物理", "化学"), CAT_STEM),
    (("计算机", "编程", "java", "python", "c++", "数据结构", "算法", "操作系统",
      "计算机网络", "数据库", "机器学习", "人工智能", "深度学习", "数据科学", "软件"), CAT_CS),
    (("语文", "汉语", "英语", "日语", "韩语", "法语", "德语", "西语", "西班牙",
      "雅思", "托福", "四六级", "考研英语", "大学英语", "jlpt", "topik", "cefr"), CAT_LANGUAGE),
    (("历史", "地理", "政治", "道法", "哲学", "社会", "法学", "法律"), CAT_HUMANITIES),
    (("生物", "医学", "护理", "药学"), CAT_LIFE),
    (("经济", "金融", "会计", "管理", "市场营销", "商科"), CAT_BUSINESS),
    (("音乐", "美术", "设计", "建筑", "绘画", "艺术"), CAT_ARTS),
]

_CUSTOM_MAX = 30  # 自定义细分 ≤30 字（spec §6.3）


def parse_category(subject: str | None) -> str:
    """从 subject 字符串解析大类。

    - 新格式 "数理科学 > 数学" → 取 ">" 前的合法大类
    - 存量自由字符串 "数学" / "Python" → 关键词推断
    - 无法判定 / 空 → 自定义
    """
    if not subject or not subject.strip():
        return CAT_CUSTOM
    s = subject.strip()
    if ">" in s:
        head = s.split(">", 1)[0].strip()
        if head in ALL_CATEGORIES:
            return head
        # ">" 前不是合法大类 → 落关键词兜底
    low = s.lower()
    for keywords, cat in _KEYWORD_CATEGORY:
        if any(k in low for k in keywords):
            return cat
    return CAT_CUSTOM


def domain_template_for(subject: str | None) -> str:
    """大类 → 注入 F1 的结构骨架；自定义/未知 → 通用骨架。"""
    return DOMAIN_TEMPLATES.get(parse_category(subject), GENERIC_TEMPLATE)


def to_canonical(category: str | None, subject: str | None) -> str:
    """组装两层存储格式 "{category} > {subject}"。非法大类→自定义；自定义细分 ≤30 字。"""
    cat = (category or CAT_CUSTOM).strip()
    if cat not in ALL_CATEGORIES:
        cat = CAT_CUSTOM
    sub = (subject or "").strip()[:_CUSTOM_MAX]
    return f"{cat} > {sub}" if sub else cat


def _best_subject(category: str, raw: str) -> str:
    """在大类的细分预置里找最贴近的；找不到用原话（截断）。"""
    low = raw.lower()
    for entry in CATEGORY_SUBJECTS.get(category, []):
        for piece in entry.replace("/", " ").split():
            p = piece.lower()
            if p in low or low in p:
                return entry
    return raw[:_CUSTOM_MAX]


def map_free_text(text: str | None) -> str | None:
    """自由文本（NL 提取/用户输入）→ 规范 "{大类} > {细分}"。

    INC-I NL 提取复用（LLM 优先精确映射；本函数是确定性兜底/规范化）。
    无法判定 → "自定义 > <原话截断>"；空 → None。
    """
    if not text or not text.strip():
        return None
    raw = text.strip()
    # 已是规范格式直接返回
    if ">" in raw and raw.split(">", 1)[0].strip() in ALL_CATEGORIES:
        return raw
    cat = parse_category(raw)
    if cat == CAT_CUSTOM:
        return to_canonical(CAT_CUSTOM, raw)
    return to_canonical(cat, _best_subject(cat, raw))
