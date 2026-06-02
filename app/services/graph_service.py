"""学习内核 P1 · 知识图谱算法（纯逻辑 + DB 查询）。

边语义：(from_kp, to_kp) 表示 from 是 to 的先修——学 to 之前应先掌握 from。
纯算法部分零 DB 依赖，便于 TDD。理论：M8(KST 先修结构) / M7(ZPD 前沿)。
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


def _adj(edges: list[tuple]) -> dict:
    """邻接表：from -> {to, ...}（后继=依赖它的下游知识点）。"""
    g: dict = defaultdict(set)
    for a, b in edges:
        g[a].add(b)
    return g


def _reachable(start, adj: dict) -> set:
    """从 start 沿后继可达的全部节点（不含 start 自身，除非成环）。"""
    seen: set = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def would_create_cycle(edges: list[tuple], new_from, new_to) -> bool:
    """加入边 new_from->new_to 是否成环：自环，或 new_to 已能到达 new_from。"""
    if new_from == new_to:
        return True
    return new_from in _reachable(new_to, _adj(edges))


def _prereqs(node, edges: list[tuple]) -> list:
    """node 的直接先修（所有指向 node 的 from）。"""
    return [a for (a, b) in edges if b == node]


def downstream_count(node, edges: list[tuple]) -> int:
    """node 沿先修后继可达的下游节点数 = 先修杠杆（P3 G-P3-1）。

    下游越多 → 该点越是地基，先学它解锁的后续越多。纯函数，复用 _reachable。
    """
    return len(_reachable(node, _adj(edges)))


def learnable_frontier(mastery: dict, edges: list[tuple], *, threshold: float = 0.6) -> list:
    """可学习前沿：自身未掌握(<threshold) 且 所有直接先修均已掌握(>=threshold)。

    无先修的未掌握节点也算前沿（无地基依赖）。掌握度缺省按 0。
    """
    nodes = set(mastery) | {x for e in edges for x in e}
    out = []
    for n in nodes:
        if mastery.get(n, 0.0) >= threshold:
            continue
        if all(mastery.get(p, 0.0) >= threshold for p in _prereqs(n, edges)):
            out.append(n)
    return out


def root_cause(node, mastery: dict, edges: list[tuple], *, threshold: float = 0.6) -> str:
    """从 node 沿先修边向下回溯，找最底层"未掌握"的先修；都掌握则返回 node 自身。

    多个薄弱先修时，沿掌握度最低的分支继续向下（最该补的地基）。
    """
    visited: set = set()
    cur = node
    while True:
        if cur in visited:
            return cur  # 防御：异常环
        visited.add(cur)
        weak = [p for p in _prereqs(cur, edges) if mastery.get(p, 0.0) < threshold]
        if not weak:
            return cur
        cur = min(weak, key=lambda p: mastery.get(p, 0.0))


def mastery_value(p_mastery: float | None, mastery_status: str | None) -> float:
    """统一掌握度取值：优先 p_mastery（P0 校准概率）；为空时按 mastery_status 兜底映射。

    兼容 P0 前存量 KP（无 p_mastery）。映射：mastered→0.9 / reviewing→0.6 / learning→0.3 / new→0.0。
    """
    if p_mastery is not None:
        return float(p_mastery)
    return {"mastered": 0.9, "reviewing": 0.6, "learning": 0.3, "new": 0.0}.get(
        mastery_status or "new", 0.0
    )


# ============ DB 建边（生成即建边，P1-2）============

async def add_edges(db, user_id, edges_with_conf: list[dict]) -> int:
    """落库先修边。edges_with_conf: [{from_kp_id, to_kp_id, confidence, source}]。

    防护：跳过自环 / 会成环的边 / 重复边（已存在 + 本批已加）。返回成功加入数。
    不在此 commit（交调用方事务）。fail-safe：单条异常跳过。
    """
    from sqlalchemy import select
    from app.models.prerequisite_edge import PrerequisiteEdge

    rows = await db.execute(
        select(PrerequisiteEdge.from_kp_id, PrerequisiteEdge.to_kp_id).where(
            PrerequisiteEdge.user_id == user_id
        )
    )
    existing = [(str(a), str(b)) for a, b in rows.all()]
    seen = set(existing)
    added = 0
    for e in edges_with_conf:
        f, t = str(e["from_kp_id"]), str(e["to_kp_id"])
        if f == t or (f, t) in seen:
            continue
        if would_create_cycle(existing, f, t):
            logger.info("prereq edge skipped (cycle): %s->%s", f, t)
            continue
        try:
            db.add(PrerequisiteEdge(
                user_id=user_id,
                from_kp_id=uuid.UUID(f),
                to_kp_id=uuid.UUID(t),
                confidence=float(e.get("confidence", 0.7)),
                source=e.get("source", "llm"),
            ))
            existing.append((f, t))
            seen.add((f, t))
            added += 1
        except Exception:  # noqa: BLE001
            logger.exception("add prereq edge failed %s->%s", f, t)
    return added


async def build_edges_for_kps(db, user_id, kps: list) -> int:
    """对一批新建 KP 调 LLM 推断先修边并落库。失败静默返回 0（不阻断建 KP）。"""
    if not kps or len(kps) < 2:
        return 0
    try:
        import json
        from app.llm.client import llm_client
        from app.llm.prompts.prerequisite_prompts import (
            SYSTEM_PREREQUISITE, INFER_PREREQUISITES_PROMPT,
        )

        kp_list = "\n".join(f"{i}. {kp.name}" for i, kp in enumerate(kps))
        raw = await llm_client.generate(
            INFER_PREREQUISITES_PROMPT.format(kp_list=kp_list),
            system=SYSTEM_PREREQUISITE,
            user_id=str(user_id),
            endpoint="infer_prerequisites",
        )
        txt = raw.strip().replace("```json", "").replace("```", "")
        data = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        idx_to_id = {i: kp.id for i, kp in enumerate(kps)}
        edges = []
        for e in data.get("edges", []):
            fi, ti = e.get("from"), e.get("to")
            if fi in idx_to_id and ti in idx_to_id and fi != ti:
                edges.append({
                    "from_kp_id": idx_to_id[fi],
                    "to_kp_id": idx_to_id[ti],
                    "confidence": e.get("confidence", 0.7),
                    "source": "llm",
                })
        return await add_edges(db, user_id, edges)
    except Exception:  # noqa: BLE001
        logger.exception("build_edges_for_kps failed user=%s", user_id)
        return 0
