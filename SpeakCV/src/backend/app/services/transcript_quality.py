# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

import re


def score_transcript_quality(text: str, lang: str) -> dict:
    normalized = (text or "").strip()
    words = re.findall(r"[a-zA-ZÀ-ỹ']+", normalized)
    too_short = len(words) < 4
    confidence = 0.25 if too_short else 0.85
    if lang == "en" and too_short:
        confidence = 0.2
    return {
        "transcript_confidence": confidence,
        "low_quality_flag": confidence < 0.65,
        "word_count": len(words),
        "quality_reason": "too_short" if too_short else "clear_enough",
    }
