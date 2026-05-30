"""阶段 B 检索评测的合成种子集（无真实隐私数据）。

设计为**有区分度**：含三组易混主题群（求导四兄弟 / 牛顿三定律 / 复习算法），
query 精确指向群内特定一个 doc——纯向量易在排序上出错，从而暴露检索短板，
为阶段 C（BM25/混合/rerank）提供可量化的提升空间。

DOCS：入库知识内容（official 层）；CASES：query → 应召回的 doc_id。
"""
import uuid


def _u(n: int) -> uuid.UUID:
    return uuid.UUID(f"e0000000-0000-0000-0000-{n:012d}")


_IDS = {
    # 独立主题
    "photo": _u(4), "quad": _u(5), "cell": _u(6),
    # 易混群 A：求导四兄弟
    "deriv": _u(1), "partial": _u(11), "direction": _u(12), "implicit": _u(13),
    # 易混群 B：牛顿三定律
    "newton2": _u(3), "newton1": _u(21), "newton3": _u(22),
    # 易混群 C：复习算法
    "fsrs": _u(31), "review": _u(32),
    # 易混群 D：精确编号（BM25 经典战场——语义几乎相同，靠字面 token 区分）
    "sm2": _u(41), "sm15": _u(42), "sm17": _u(43),
}

DOCS = [
    {"doc_id": _IDS["photo"], "content": "光合作用是绿色植物利用光能，把二氧化碳和水转化为有机物并释放氧气的过程。"},
    {"doc_id": _IDS["quad"], "content": "二次函数 y=ax²+bx+c 的图像是抛物线，顶点横坐标为 x=-b/(2a)。"},
    {"doc_id": _IDS["cell"], "content": "细胞是生物体结构和功能的基本单位，分为原核细胞和真核细胞。"},
    # 群 A 求导
    {"doc_id": _IDS["deriv"], "content": "导数是一元函数在某一点的瞬时变化率，几何意义是该点切线的斜率。"},
    {"doc_id": _IDS["partial"], "content": "偏导数是多元函数对其中一个自变量求导，其余自变量保持不变。"},
    {"doc_id": _IDS["direction"], "content": "方向导数表示多元函数沿某一指定方向的变化率。"},
    {"doc_id": _IDS["implicit"], "content": "隐函数求导是对方程两边同时关于 x 求导，并把 y 视为 x 的函数。"},
    # 群 B 牛顿
    {"doc_id": _IDS["newton2"], "content": "牛顿第二定律：物体加速度与所受合外力成正比、与质量成反比，公式 F=ma。"},
    {"doc_id": _IDS["newton1"], "content": "牛顿第一定律即惯性定律：物体不受外力时保持静止或匀速直线运动状态。"},
    {"doc_id": _IDS["newton3"], "content": "牛顿第三定律：两个物体间的作用力与反作用力大小相等、方向相反、作用在不同物体上。"},
    # 群 C 复习
    {"doc_id": _IDS["fsrs"], "content": "FSRS 是基于记忆稳定性与可提取性的间隔重复调度算法，比传统 SM-2 更精准地安排复习时间。"},
    {"doc_id": _IDS["review"], "content": "及时复习能对抗艾宾浩斯遗忘曲线，应在记忆临近遗忘的时刻安排复习以巩固。"},
    # 群 D 精确编号（语义几乎一致，靠 SM-x 编号区分）
    {"doc_id": _IDS["sm2"], "content": "SM-2 算法根据用户对卡片的回忆质量评分来调整下一次复习的间隔时长。"},
    {"doc_id": _IDS["sm15"], "content": "SM-15 是 SuperMemo 的改进算法，引入了更精细的记忆遗忘曲线建模。"},
    {"doc_id": _IDS["sm17"], "content": "SM-17 是 SuperMemo 目前较新的间隔重复算法，基于两成分记忆模型。"},
]

CASES = [
    # 独立主题（语义清晰，纯向量应满分）
    {"id": "c_photo", "query": "植物是怎么产生氧气的", "relevant": [str(_IDS["photo"])]},
    {"id": "c_quad", "query": "抛物线的顶点坐标公式", "relevant": [str(_IDS["quad"])]},
    # 群 A：精确指向，考验排序（纯向量易把"导数"排在"偏/方向导数"前）
    {"id": "c_partial", "query": "多元函数对一个变量求导别的变量当常数", "relevant": [str(_IDS["partial"])]},
    {"id": "c_direction", "query": "函数沿某个指定方向的变化率", "relevant": [str(_IDS["direction"])]},
    {"id": "c_implicit", "query": "方程两边同时求导把 y 看成 x 的函数", "relevant": [str(_IDS["implicit"])]},
    # 群 B：易混三定律
    {"id": "c_newton1", "query": "惯性定律说的是什么", "relevant": [str(_IDS["newton1"])]},
    {"id": "c_newton3", "query": "作用力与反作用力大小相等方向相反", "relevant": [str(_IDS["newton3"])]},
    # 群 C：精确术语（纯向量易混 FSRS 与一般复习）
    {"id": "c_fsrs", "query": "FSRS 间隔重复调度算法", "relevant": [str(_IDS["fsrs"])]},
    # 群 D：精确编号区分（BM25 强 / 纯向量弱的典型场景）
    {"id": "c_sm15", "query": "SM-15 算法的特点", "relevant": [str(_IDS["sm15"])]},
    {"id": "c_sm17", "query": "SM-17 用的什么记忆模型", "relevant": [str(_IDS["sm17"])]},
]
