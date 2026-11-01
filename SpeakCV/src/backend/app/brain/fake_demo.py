"""Deterministic responses for demo and tests when an AI slot is fake. Never used with a real vendor."""
import json
import re

from app.ai.config import get_config
from app.ai.providers import fake
from app.brain.text import MIN_QUOTE_CHARS

_fixture: list[dict] = []
_fixture_edges: list[dict] = []
_FIRST_CONTEXT_ITEM = re.compile(r"<context>\n\[([nc]\d+)\] (.*?)(?=\n\[[nc]\d+\] |\n</context>)", re.DOTALL)
_DOCUMENT = re.compile(r"<document>\n(.*)\n</document>", re.DOTALL)


def load_extraction_fixture(items: list[dict], edges: list[dict] | None = None) -> None:
    """Items carry the extraction fields. An item is emitted when its quote appears in the chunk.

    Edges are emitted the same way. The pipeline drops and counts an edge whose ends do not resolve."""
    _fixture.clear()
    _fixture.extend(items)
    _fixture_edges.clear()
    _fixture_edges.extend(edges or [])


def _extract(_system, messages, _schema) -> str:
    match = _DOCUMENT.search(messages[-1]["content"])
    chunk = match.group(1) if match else ""
    if _fixture:
        return json.dumps(
            {
                "nodes": [i for i in _fixture if i["quote"] in chunk],
                "edges": [e for e in _fixture_edges if e["quote"] in chunk],
            },
            ensure_ascii=False,
        )
    lines = [line.strip(" #") for line in chunk.splitlines() if line.strip(" #")]
    if not lines:
        return json.dumps({"nodes": [], "edges": []})
    first_line = lines[0]
    # A short heading alone would fail the quote gate.
    quote = next((line for line in lines if len(line) >= MIN_QUOTE_CHARS), first_line)
    node = {"ref": first_line[:80], "type": "policy", "title": first_line[:80], "body": chunk[:200], "quote": quote,
            "fact_kind": "none", "fact_value": "", "fact_unit": "", "scope_text": "", "effective_date": ""}
    return json.dumps({"nodes": [node], "edges": []}, ensure_ascii=False)


def _conflict(_system, _messages, _schema) -> str:
    # Pairs whose values code can read and match never get here, so the demo treats the rest as different.
    return json.dumps({"same_topic": True, "same_scope": True, "same_value": False})


def _not_discriminating(_system, _messages, _schema) -> str:
    # The rules in app.bridges.discrimination still fire; the demo classifier never adds a flag of its own.
    return json.dumps({"flagged": False, "category": "age", "reason": ""})


def _copilot(_system, messages, _schema) -> str:
    match = _FIRST_CONTEXT_ITEM.search(messages[0]["content"])
    if not match:
        return json.dumps({"can_answer": False, "answer": "", "citation_ids": []})
    return json.dumps(
        {"can_answer": True, "answer": f"[Demo AI] {match.group(2)}", "citation_ids": [match.group(1)]},
        ensure_ascii=False,
    )


def install() -> None:
    config = get_config()
    if config.slot("bulk").provider == "fake":
        fake.register("kb_extract", _extract)
        fake.register("kb_conflict_check", _conflict)
        fake.register("discrimination_check", _not_discriminating)
    if config.slot("reasoning").provider == "fake":
        fake.register("copilot_answer", _copilot)
