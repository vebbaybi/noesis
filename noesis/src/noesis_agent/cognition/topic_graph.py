from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

import networkx as nx

from noesis_agent.shared.noesislogger import NoesisLogger


@dataclass
class TopicNode:
    title: str
    last_seen: float = field(default_factory=lambda: time.time())
    mentions: int = 1
    sentiment: float | None = None


class TopicGraph:
    """Tracks discussion threads as a graph to preserve continuity."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.logger = NoesisLogger("noesis.cognition.topic_graph").logger

    def _ensure_node(self, topic: str) -> None:
        if topic not in self.graph:
            self.graph.add_node(topic, data=TopicNode(title=topic))

    def add_transition(self, from_topic: str | None, to_topic: str) -> None:
        self._ensure_node(to_topic)
        self.graph.nodes[to_topic]["data"].last_seen = time.time()
        self.graph.nodes[to_topic]["data"].mentions += 1

        if from_topic:
            self._ensure_node(from_topic)
            if self.graph.has_edge(from_topic, to_topic):
                self.graph[from_topic][to_topic]["weight"] += 1
            else:
                self.graph.add_edge(from_topic, to_topic, weight=1)

    def hottest_topics(self, limit: int = 5) -> list[str]:
        scored = []
        now = time.time()
        for node, data in self.graph.nodes(data="data"):
            freshness = max(0.1, now - data.last_seen)
            score = data.mentions / freshness
            scored.append((score, node))
        scored.sort(reverse=True)
        return [n for _, n in scored[:limit]]

    def unresolved_threads(self, limit: int = 3) -> list[str]:
        # Heuristic: nodes with outgoing edges but low revisit count
        candidates = []
        for node, data in self.graph.nodes(data="data"):
            out_degree = self.graph.out_degree(node)
            in_degree = self.graph.in_degree(node)
            novelty = max(1, data.mentions - in_degree)
            candidates.append((out_degree * novelty, node))
        candidates.sort(reverse=True)
        return [n for _, n in candidates[:limit]]


__all__ = ["TopicGraph", "TopicNode"]
