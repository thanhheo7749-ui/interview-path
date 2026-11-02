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


_FACT = re.compile(r'<fact id="([^"]+)" kind="\w+" status="(\w+)">\nlabel: (.*)\nquote: (.*)\n</fact>')
_LANGUAGE = re.compile(r"<language>(\w+)</language>")
_CLEAR = ("evidence", "met", "explained")


def _candidate_brief(_system, messages, _schema) -> str:
    """One strength per clear fact, one point to clarify per unclear one, and a question for each of those."""
    content = messages[-1]["content"]
    language = (_LANGUAGE.search(content) or [None, "en"])[1]
    strengths, clarify, questions = [], [], []
    for ident, status, label, _quote in _FACT.findall(content):
        if status in _CLEAR:
            strengths.append({"evidence_id": ident, "summary": f"[Demo AI] ({language}) {label}", "quote": ""})
        else:
            clarify.append({"evidence_id": ident, "summary": f"[Demo AI] ({language}) {label}", "quote": ""})
            questions.append({"evidence_id": ident, "question": f"[Demo AI] ({language}) {label}?"})
    return json.dumps({"strengths": strengths, "to_clarify": clarify, "questions": questions}, ensure_ascii=False)


_JD_CONTEXT_ITEM = re.compile(r"^\[(\d+)\] (.*)$", re.MULTILINE)
_JD_DRAFT = re.compile(r"<draft>\n(.*?)\n</draft>", re.DOTALL)
_JD_REQUEST = re.compile(r"<request>\n(.*?)\n</request>", re.DOTALL)
_SALARY_WORDS = ("salary", "lương", "luong", "연봉")


def _jd_generate(_system, messages, _schema) -> str:
    context = messages[-1]["content"].split("</context>")[0]
    lines = []
    for index, match in enumerate(_JD_CONTEXT_ITEM.finditer(context), 1):
        text = match.group(2)
        lines.append({"id": f"l{index}", "en": f"[Demo AI] {text}", "vi": f"[Demo AI] {text}",
                      "ko": f"[Demo AI] {text}", "source_node_ids": [int(match.group(1))],
                      "is_requirement": False, "must_have": False})
    return json.dumps({"lines": lines}, ensure_ascii=False)


def _jd_assistant(_system, messages, _schema) -> str:
    prompt = messages[-1]["content"]
    draft = _JD_DRAFT.search(prompt)
    request = _JD_REQUEST.search(prompt)
    asked = (request.group(1) if request else "").casefold()
    proposals = []
    if any(word in asked for word in _SALARY_WORDS):
        text = "[Demo AI] Salary to be confirmed by HR"
        proposals.append({"en": text, "vi": text, "ko": text, "reason": "No salary in the knowledge graph."})
    return json.dumps({"lines": json.loads(draft.group(1)) if draft else [], "summary": "Demo AI revision",
                       "proposals": proposals}, ensure_ascii=False)


_CHANNEL_DRAFT = re.compile(r"<draft>\n(.*?)\n</draft>", re.DOTALL)


def _channel_content(_system, messages, _schema) -> str:
    draft = _CHANNEL_DRAFT.search(messages[-1]["content"])
    lines = [row[2:].strip() for row in (draft.group(1) if draft else "").splitlines() if row.startswith("- ")]
    return json.dumps({"body": "[Demo AI] " + " ".join(lines) + "\n\n{link}"}, ensure_ascii=False)


_FEEDBACK_ITEM = re.compile(r'<item ref="(\w+)" section="(\w+)">\nlabel: (.*)\nquote: (.*)\n</item>')
_FEEDBACK_LEARNING = re.compile(r"^- id=(\d+): ", re.MULTILINE)


def _rejection_feedback(_system, messages, _schema) -> str:
    """One neutral sentence, one point from the first verified quote, and one from the first gap."""
    content = messages[-1]["content"]
    language = (_LANGUAGE.search(content) or [None, "en"])[1]
    items = _FEEDBACK_ITEM.findall(content)
    good = [item for item in items if item[1] == "went_well"][:1]
    gaps = [item for item in items if item[1] == "to_build"][:1]
    learning = content.split("<learning>")[1] if "<learning>" in content else ""
    return json.dumps({
        "went_well": [{"ref": ref, "text": f"[Demo AI] {label}", "quote": quote} for ref, _, label, quote in good],
        "to_build": [{"ref": ref, "text": f"[Demo AI] {label}", "quote": ""} for ref, _, label, _ in gaps],
        "learning_ids": [int(found) for found in _FEEDBACK_LEARNING.findall(learning)],
        "message": f"[Demo AI] ({language}) Thank you for the time you gave us.",
    }, ensure_ascii=False)


def _same_topic_no(_system, _messages, _schema) -> str:
    return json.dumps({"same_topic": False})


def install() -> None:
    config = get_config()
    if config.slot("bulk").provider == "fake":
        fake.register("kb_extract", _extract)
        fake.register("kb_conflict_check", _conflict)
        fake.register("discrimination_check", _not_discriminating)
        fake.register("lint_conflict_check", _same_topic_no)
        fake.register("channel_content", _channel_content)
        fake.register("rejection_feedback", _rejection_feedback)
    if config.slot("reasoning").provider == "fake":
        fake.register("copilot_answer", _copilot)
        fake.register("candidate_brief", _candidate_brief)
        fake.register("jd_generate", _jd_generate)
        fake.register("jd_assistant", _jd_assistant)
