"""阶段 B 种子集一致性元测试：防止标注引用不存在的 doc_id。"""
from app.eval.seed_retrieval_cases import DOCS, CASES


def test_seed_cases_reference_existing_docs():
    doc_ids = {str(d["doc_id"]) for d in DOCS}
    for c in CASES:
        for rel in c["relevant"]:
            assert rel in doc_ids, f"case {c['id']} 的 relevant {rel} 不在 DOCS 中"


def test_seed_doc_ids_unique():
    ids = [str(d["doc_id"]) for d in DOCS]
    assert len(ids) == len(set(ids)), "DOCS 存在重复 doc_id"


def test_seed_has_confusable_groups():
    # 至少覆盖易混群（求导/牛顿/复习），保证评估集有区分度
    assert len(DOCS) >= 12
    assert len(CASES) >= 8
