# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

import re


def score_speaking_signals(text: str, audio_meta: dict | None = None) -> dict:
    audio_meta = audio_meta or {}
    words = re.findall(r"[a-zA-ZÀ-ỹ']+", text or "")
    fillers = [w for w in words if w.lower() in {"um", "uh", "like", "well", "so"}]
    filler_rate = round(len(fillers) / max(len(words), 1), 3)
    clarity_score = round(max(0.1, 1 - filler_rate), 3)
    return {
        "filler_rate": filler_rate,
        "clarity_score": clarity_score,
        "speaking_signal": "hesitant" if filler_rate > 0.15 else "clear",
        "pause_hint": audio_meta.get("pause_ratio"),
    }
