# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

from uuid import uuid4
from typing import Any


def new_trace_id() -> str:
    return str(uuid4())


def build_interview_result(
    ai_text: str,
    analysis: dict[str, Any],
    usage: dict[str, Any],
    trace_id: str | None = None,
) -> dict[str, Any]:
    return {
        "content": ai_text,
        "analysis": analysis,
        "usage": usage,
        "trace_id": trace_id or new_trace_id(),
    }
