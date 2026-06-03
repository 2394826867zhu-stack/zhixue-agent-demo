"""Golden 快照安全网（计划 0.3）。

`scripts/capture_golden.py` 抓的 golden 同时被前端 vendor 当 jest 契约样本。
本测试是**后端侧的字段裁剪/漂移闸门**，纯静态校验（不依赖数据库）：

1. 每个 golden 结构完整（name/method/path/openapi_path/openapi_ref/status/response）。
2. `openapi_ref` 必须是冻结契约 `contracts/openapi.json` 里真实存在的组件
   —— 保证前端能据此解析到对应生成的 zod schema（前后端同源的连接点）。
3. golden 的 `response` 必须能被该路由当前的 `response_model` 重新校验通过
   —— 后端改 schema 裁掉/改名字段后，旧 golden 立即变红，逼迫重抓（= 抓出契约漂移）。

→ 后端跑 pytest 即守住 golden 不腐化；前端跑 jest 用同一组 golden 锁住生成类型。
"""
import json
from pathlib import Path

import pytest

from app.main import app
from tools.gen_openapi import render

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
GOLDEN_FILES = sorted(GOLDEN_DIR.glob("*.json"))

REQUIRED_KEYS = {"name", "method", "path", "openapi_path", "openapi_ref", "status", "response"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_golden_dir_not_empty():
    assert GOLDEN_FILES, (
        f"{GOLDEN_DIR} 下无 golden，请运行 python scripts/capture_golden.py 生成。"
    )


@pytest.mark.parametrize("golden_path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_golden_structure(golden_path: Path):
    g = _load(golden_path)
    assert REQUIRED_KEYS <= set(g), f"{golden_path.name} 缺字段：{REQUIRED_KEYS - set(g)}"
    assert g["status"] == 200
    assert g["response"].get("code") == 200
    assert "data" in g["response"]


@pytest.mark.parametrize("golden_path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_golden_ref_in_committed_contract(golden_path: Path):
    """golden 声明的 openapi_ref 必须存在于冻结契约的 components.schemas。"""
    g = _load(golden_path)
    contract = json.loads(render())
    components = contract.get("components", {}).get("schemas", {})
    assert g["openapi_ref"] in components, (
        f"{golden_path.name} 的 openapi_ref={g['openapi_ref']} 不在 contracts/openapi.json；"
        "契约已变？请 python tools/gen_openapi.py 重新冻结后重抓 golden。"
    )


def _route_response_model(method: str, path_template: str):
    from fastapi.routing import APIRoute
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path_template and method.upper() in route.methods:
            return route.response_model
    return None


@pytest.mark.parametrize("golden_path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_golden_revalidates_against_response_model(golden_path: Path):
    """字段裁剪安全网：旧 golden 必须仍能被当前 response_model 校验通过。

    后端改 Pydantic schema（删字段/改 nullable/改类型）后，旧 golden 校验失败
    → 测试红 → 必须重抓 golden（也即必须同步前端契约），杜绝静默漂移。
    """
    g = _load(golden_path)
    model = _route_response_model(g["method"], g["openapi_path"])
    assert model is not None, (
        f"{golden_path.name}: 找不到路由 {g['method']} {g['openapi_path']} 的 response_model"
    )
    # 校验完整 envelope；失败即 golden 与当前契约漂移。
    model.model_validate(g["response"])
