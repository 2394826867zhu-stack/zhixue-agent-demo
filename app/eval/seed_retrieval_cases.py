"""阶段 B 检索评测的合成种子集（用于跑基线，不含真实用户隐私数据）。

DOCS：入库的知识内容（official 层）；CASES：query → 应召回的 doc_id。
"""
import uuid

_IDS = {
    "deriv": uuid.UUID("e0000000-0000-0000-0000-000000000001"),
    "integ": uuid.UUID("e0000000-0000-0000-0000-000000000002"),
    "newton": uuid.UUID("e0000000-0000-0000-0000-000000000003"),
    "photo": uuid.UUID("e0000000-0000-0000-0000-000000000004"),
    "quad": uuid.UUID("e0000000-0000-0000-0000-000000000005"),
    "cell": uuid.UUID("e0000000-0000-0000-0000-000000000006"),
}

DOCS = [
    {"doc_id": _IDS["deriv"], "content": "导数是函数在某一点的瞬时变化率，几何意义是该点切线的斜率。"},
    {"doc_id": _IDS["integ"], "content": "定积分表示曲线与坐标轴围成区域的面积，是导数的逆运算。"},
    {"doc_id": _IDS["newton"], "content": "牛顿第二定律：物体加速度与所受合外力成正比、与质量成反比，公式 F=ma。"},
    {"doc_id": _IDS["photo"], "content": "光合作用是绿色植物利用光能，把二氧化碳和水转化为有机物并释放氧气的过程。"},
    {"doc_id": _IDS["quad"], "content": "二次函数 y=ax²+bx+c 的图像是抛物线，顶点横坐标为 x=-b/(2a)。"},
    {"doc_id": _IDS["cell"], "content": "细胞是生物体结构和功能的基本单位，分为原核细胞和真核细胞。"},
]

CASES = [
    {"id": "c_deriv", "query": "瞬时变化率和切线斜率是什么意思", "relevant": [str(_IDS["deriv"])]},
    {"id": "c_integ", "query": "曲线和坐标轴围成的面积怎么求", "relevant": [str(_IDS["integ"])]},
    {"id": "c_newton", "query": "加速度跟力和质量是什么关系", "relevant": [str(_IDS["newton"])]},
    {"id": "c_photo", "query": "植物是怎么产生氧气的", "relevant": [str(_IDS["photo"])]},
    {"id": "c_quad", "query": "抛物线的顶点坐标公式", "relevant": [str(_IDS["quad"])]},
]
