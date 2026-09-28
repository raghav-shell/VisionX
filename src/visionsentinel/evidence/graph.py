"""Lightweight evidence graph (nodes/edges) without a graph database."""

from __future__ import annotations

from typing import Any

from ..contracts import EvidenceGraph, GraphEdge, GraphNode


class GraphBuilder:
    def __init__(self, max_nodes: int = 5000) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[tuple[str, str, str], GraphEdge] = {}
        self.max_nodes = max_nodes
        self.truncated = False

    def node(self, id: str, type: str, label: str, **attrs: Any) -> str:
        if id not in self._nodes:
            if len(self._nodes) >= self.max_nodes:
                self.truncated = True
                return id
            self._nodes[id] = GraphNode(id=id, type=type, label=label, attrs=attrs)  # type: ignore[arg-type]
        elif attrs:
            self._nodes[id].attrs.update(attrs)
        return id

    def edge(self, source: str, target: str, type: str, **attrs: Any) -> None:
        if source not in self._nodes or target not in self._nodes:
            return
        key = (source, target, type)
        if key not in self._edges:
            self._edges[key] = GraphEdge(source=source, target=target, type=type, attrs=attrs)  # type: ignore[arg-type]

    def build(self) -> EvidenceGraph:
        return EvidenceGraph(nodes=list(self._nodes.values()), edges=list(self._edges.values()))


def neighbourhood(graph: EvidenceGraph, start: str, depth: int = 3) -> EvidenceGraph:
    """Sub-graph within ``depth`` undirected hops of ``start`` (for a finding's evidence chain)."""
    adj: dict[str, list[GraphEdge]] = {}
    for e in graph.edges:
        adj.setdefault(e.source, []).append(e)
        adj.setdefault(e.target, []).append(e)
    seen = {start}
    frontier = {start}
    edges: dict[tuple[str, str, str], GraphEdge] = {}
    for _ in range(depth):
        nxt: set[str] = set()
        for n in frontier:
            for e in adj.get(n, []):
                edges[(e.source, e.target, e.type)] = e
                other = e.target if e.source == n else e.source
                if other not in seen:
                    seen.add(other)
                    nxt.add(other)
        frontier = nxt
    nodes = [n for n in graph.nodes if n.id in seen]
    return EvidenceGraph(nodes=nodes, edges=list(edges.values()))
