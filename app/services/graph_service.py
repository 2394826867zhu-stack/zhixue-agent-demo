"""学习内核 P1 · 知识图谱算法（纯逻辑 + DB 查询）。

边语义：(from_kp, to_kp) 表示 from 是 to 的先修——学 to 之前应先掌握 from。
纯算法部分零 DB 依赖，便于 TDD。理论：M8(KST 先修结构) / M7(ZPD 前沿)。
"""
from __future__ import annotations

from collections import defaultdict


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
