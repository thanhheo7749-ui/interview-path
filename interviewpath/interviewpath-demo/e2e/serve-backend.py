"""Starts the API with a fixed fake extraction, so uploaded fixture documents yield known facts. Test use only.

It also gives the interview analysis a fixed answer that cites the fake microphone's transcript. The shared fake
analysis only quotes words it finds in a requirement, and the fake speech-to-text always returns "fake transcript",
so without this no answer would ever count as evidence and the board would only hold empty analyses.
"""
import json
import os
import re
import sys

import uvicorn

from app.ai.providers import fake
from app.brain import fake_demo
from app.main import app  # create_app() installs the shared fake responders, so ours are registered after this import

FAKE_QUOTE = "fake transcript"

fixture_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "extraction.json")
with open(fixture_path, encoding="utf-8") as handle:
    fixture = json.load(handle)
fake_demo.load_extraction_fixture(fixture["nodes"], fixture["edges"])


def _items(content: str, section: str) -> list[int]:
    found = re.search(rf"<{section}>\n(.*?)\n</{section}>", content, re.DOTALL)
    return [int(match) for match in re.findall(r"^- id=(\d+):", found.group(1) if found else "", re.MULTILINE)]


def _analysis_with_quotes(_system, messages, _schema) -> str:
    content = messages[-1]["content"]
    return json.dumps({
        "requirements": [{"requirement_id": i, "status": "evidence", "quote": FAKE_QUOTE, "position": 1}
                         for i in _items(content, "requirements")],
        "claims": [{"claim_id": i, "status": "explained", "quote": FAKE_QUOTE, "position": 1}
                   for i in _items(content, "claims")],
        "culture_notes": [],
        "suggestion": "Review the quoted answers before deciding.",
    })


UNCHECKED_MARKER = "UNCHECKEDCANARY"


def _classifier_down_for_marker(_system, messages, _schema) -> str:
    """The demo classifier never flags anything. A statement with the marker gets an answer that is not valid output,
    which is what a failing classifier looks like: the guard then records the text as "unchecked"."""
    # A retry appends a message, so look at all of them.
    if any(UNCHECKED_MARKER in message["content"] for message in messages):
        return "the classifier is down"
    return json.dumps({"flagged": False, "category": "age", "reason": ""})


fake.register("session_analysis", _analysis_with_quotes)
fake.register("discrimination_check", _classifier_down_for_marker)
uvicorn.run(app, port=int(sys.argv[1]))
