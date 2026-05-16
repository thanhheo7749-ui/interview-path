# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from sqlalchemy.orm import Session

from app.database import sql_models


PRIORITY_TYPES = ["principle", "rubric", "red_flag", "follow_up_strategy", "question_pattern", "domain_knowledge"]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def build_query_terms(jd_text: str, mode: str, user_text: str) -> list[str]:
    corpus = _normalize(f"{jd_text} {mode} {user_text}")
    terms = [t for t in re.findall(r"[a-zA-Z0-9_\-\.]{3,}", corpus) if not t.isdigit()]
    seen = set()
    ordered = []
    for t in terms:
        if t in seen:
            continue
        seen.add(t)
        ordered.append(t)
    return ordered[:40]


def get_active_brain_version(db: Session):
    return db.query(sql_models.AIBrainVersion).filter(sql_models.AIBrainVersion.status == "active").first()


def _node_match_score(node: sql_models.AIBrainNode, terms: Iterable[str]) -> float:
    label = _normalize(node.label or "")
    content = _normalize(node.content or "")
    tags = " ".join((node.tags or [])) if isinstance(node.tags, list) else str(node.tags or "")
    tags_n = _normalize(tags)
    score = 0.0
    for term in terms:
        if term in label:
            score += 3
        if term in tags_n:
            score += 2
        if term in content:
            score += 1
    score += float(node.weight or 0.0) * 0.5
    if node.node_type in PRIORITY_TYPES:
        score += (len(PRIORITY_TYPES) - PRIORITY_TYPES.index(node.node_type)) * 0.1
    return score


def retrieve_subgraph_context(db: Session, jd_text: str, mode: str, user_text: str, max_chars: int = 3200) -> dict:
    version = get_active_brain_version(db)
    if not version:
        return {"context": "", "node_count": 0, "edge_count": 0, "version": None}

    terms = build_query_terms(jd_text, mode, user_text)
    nodes = db.query(sql_models.AIBrainNode).filter(
        sql_models.AIBrainNode.version_id == version.id,
        sql_models.AIBrainNode.active == True,
    ).all()

    if not nodes:
        return {"context": "", "node_count": 0, "edge_count": 0, "version": version.version}

    scored = []
    for n in nodes:
        s = _node_match_score(n, terms)
        if s > 0:
            scored.append((n, s))

    if not scored:
        return {"context": "", "node_count": 0, "edge_count": 0, "version": version.version}

    scored.sort(key=lambda x: x[1], reverse=True)
    seed_nodes = [n for n, _ in scored[:20]]
    seed_keys = {n.node_key for n in seed_nodes}

    edges = db.query(sql_models.AIBrainEdge).filter(sql_models.AIBrainEdge.version_id == version.id).all()
    neighbors = set(seed_keys)
    adjacency = defaultdict(set)
    selected_edges = []

    for e in edges:
        adjacency[e.source_node_key].add(e.target_node_key)
        adjacency[e.target_node_key].add(e.source_node_key)
        if e.source_node_key in seed_keys or e.target_node_key in seed_keys:
            selected_edges.append(e)
            neighbors.add(e.source_node_key)
            neighbors.add(e.target_node_key)

    node_map = {n.node_key: n for n in nodes}
    selected_nodes = [node_map[k] for k in neighbors if k in node_map]

    # rank selected nodes for prompt assembly
    ranked = sorted(selected_nodes, key=lambda n: _node_match_score(n, terms), reverse=True)

    lines = ["[BRAIN CONTEXT - RETRIEVED SUBGRAPH]"]
    seen_lines = set()
    for n in ranked:
        line = f"[{n.node_type}] {n.content or n.label or n.node_key}"
        if line in seen_lines:
            continue
        if len("\n".join(lines)) + len(line) + 1 > max_chars:
            break
        seen_lines.add(line)
        lines.append(line)

    return {
        "context": "\n".join(lines) if len(lines) > 1 else "",
        "node_count": len(ranked),
        "edge_count": len(selected_edges),
        "version": version.version,
    }
