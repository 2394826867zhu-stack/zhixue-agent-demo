"""导出 FastAPI OpenAPI schema → contracts/openapi.json（确定性排序）。

SDD Phase 0 · Code-first / schema 权威：
- Pydantic 模型是接口规格的权威源；本脚本把 app.openapi() 冻结入库。
- contracts/openapi.json 的 diff 在 PR 中当"规格变更"审查。
- 前端 codegen（Phase 1）以此文件为唯一输入。

确定性：sort_keys=True + 固定 indent，保证同一份代码多次生成零 diff，
使 tests/contract/test_openapi_committed.py 的一致性闸门可靠。

用法：
    python tools/gen_openapi.py            # 写盘
    python tools/gen_openapi.py --check    # 只比对，不写盘；陈旧则非零退出
"""
import argparse
import json
import sys
from pathlib import Path

from app.main import app

OUT = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"


def render() -> str:
    schema = app.openapi()
    return json.dumps(schema, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只比对不写盘，陈旧则退出码 1")
    args = parser.parse_args()

    rendered = render()
    if args.check:
        if not OUT.exists():
            print(f"[stale] {OUT} 不存在，请先运行 python tools/gen_openapi.py", file=sys.stderr)
            return 1
        current = OUT.read_text(encoding="utf-8")
        if current != rendered:
            print(f"[stale] {OUT} 与代码不一致，请运行 python tools/gen_openapi.py 重新生成", file=sys.stderr)
            return 1
        print(f"[ok] {OUT} 与代码一致")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    schema = json.loads(rendered)
    print(f"wrote {OUT} — {len(schema.get('paths', {}))} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
