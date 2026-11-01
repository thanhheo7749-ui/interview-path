"""Deterministic responses for demo and tests when an AI slot is fake. Never used with a real vendor."""
import json
import re

from app.ai.config import get_config
from app.ai.providers import fake

_fixture: list[dict] = []
_FIRST_CONTEXT_ITEM = re.compile(r"<context>\n\[([nc]\d+)\] (.*?)(?=\n\[[nc]\d+\] |\n</context>)", re.DOTALL)
_DOCUMENT = re.compile(r"<document>\n(.*)\n</document>", re.DOTALL)


def load_extraction_fixture(items: list[dict]) -> None:
    """Items carry the extraction fields. An item is emitted when its quote appears in the chunk."""
    _fixture.clear()
    _fixture.extend(items)


def _extract(_system, messages, _schema) -> str:
    match = _DOCUMENT.search(messages[-1]["content"])
    chunk = match.group(1) if match else ""
    if _fixture:
        return json.dumps({"nodes": [i for i in _fixture if i["quote"] in chunk], "edges": []}, ensure_ascii=False)
    first_line = next((line.strip(" #") for line in chunk.splitlines() if line.strip(" #")), "")
    if not first_line:
        return json.dumps({"nodes": [], "edges": []})
    node = {"ref": first_line[:80], "type": "policy", "title": first_line[:80], "body": chunk[:200], "quote": first_line,
            "fact_kind": "none", "fact_value": "", "fact_unit": "", "scope_text": "", "effective_date": ""}
    return json.dumps({"nodes": [node], "edges": []}, ensure_ascii=False)


def _conflict(_system, _messages, _schema) -> str:
    return json.dumps({"same_topic": True, "same_scope": True})


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
    if config.slot("reasoning").provider == "fake":
        fake.register("copilot_answer", _copilot)
