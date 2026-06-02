"""契约一致性闸门：contracts/openapi.json 必须与当前代码生成结果一致。

SDD Code-first：openapi.json 是冻结入库的 L1 契约。改了 Pydantic schema /
路由后必须 `python tools/gen_openapi.py` 重新生成并提交，否则前端 codegen
会基于陈旧契约生成类型。CI 与本地 pre-commit 都跑此测试。

纯生成+比对，不依赖数据库。
"""
from tools.gen_openapi import render, OUT


def test_committed_openapi_is_current():
    assert OUT.exists(), (
        f"{OUT} 不存在，请运行 python tools/gen_openapi.py 生成并提交。"
    )
    committed = OUT.read_text(encoding="utf-8")
    assert committed == render(), (
        "contracts/openapi.json 与当前代码不一致（schema/路由已改但未重新生成）。\n"
        "请运行 python tools/gen_openapi.py 重新生成并提交。"
    )
