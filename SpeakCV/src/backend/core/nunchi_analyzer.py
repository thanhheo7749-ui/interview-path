# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

"""
Nunchi Analyzer - Attitude & Intent Detection Module
Analyzes candidate responses for intent (evasion, reverse questions) and confidence level.
"""

import re
from typing import Dict


def analyze_candidate_response(transcript: str) -> Dict[str, str]:
    """
    Analyze candidate's response to detect intent and confidence level.

    Args:
        transcript: The candidate's spoken/typed response (English)

    Returns:
        Dictionary with 'intent' and 'confidence_level' keys

    Example:
        >>> analyze_candidate_response("Um, I don't know, can we skip this?")
        {'intent': 'skipping', 'confidence_level': 'Low Confidence / Nervous'}
    """
    transcript_lower = transcript.lower().strip()

    # --- Intent Detection ---
    intent = "answering"  # Default

    # Pattern 1: Evasion/Skipping
    skip_patterns = [
        r"\bi don'?t know\b",
        r"\bno idea\b",
        r"\bskip\b",
        r"\bnext question\b",
        r"\bpass\b",
        r"\bcan we move on\b",
        r"\blet'?s move on\b",
        r"\bi'?m not sure\b",
        r"\bno clue\b"
    ]

    for pattern in skip_patterns:
        if re.search(pattern, transcript_lower):
            intent = "skipping"
            break

    # Pattern 2: Reverse Question (asking interviewer)
    if intent == "answering":  # Only check if not already skipping
        reverse_patterns = [
            r"\bwhat do you think\b",
            r"\bwhat'?s your opinion\b",
            r"\bwhat stack\b",
            r"\bwhat would you\b",
            r"\bhow would you\b",
            r"\bwhat framework do you use\b",
            r"\bcan i ask you\b",
            r"\bmay i ask\b"
        ]

        for pattern in reverse_patterns:
            if re.search(pattern, transcript_lower):
                intent = "asking_reverse_question"
                break

    # --- Confidence Level Detection ---
    # Count English filler words
    filler_words = [
        r"\bum+\b",           # um, umm, ummm
        r"\buh+\b",           # uh, uhh
        r"\blike\b",          # like
        r"\byou know\b",      # you know
        r"\bkinda\b",         # kinda
        r"\bsorta\b",         # sorta
        r"\bbasically\b",     # basically (when overused)
        r"\bactually\b",      # actually (when overused)
        r"\bi mean\b",        # i mean
        r"\bwell\b",          # well (at start)
        r"\bso\b"             # so (when repeated)
    ]

    filler_count = 0
    for pattern in filler_words:
        matches = re.findall(pattern, transcript_lower)
        filler_count += len(matches)

    # Determine confidence level
    if filler_count > 3:
        confidence_level = "Low Confidence / Nervous"
    else:
        confidence_level = "Confident"

    return {
        "intent": intent,
        "confidence_level": confidence_level,
        "filler_count": filler_count  # Extra metadata for debugging
    }


def get_interviewer_guidance(analysis: Dict[str, str]) -> str:
    """
    Generate guidance for the interviewer based on analysis.

    Args:
        analysis: Output from analyze_candidate_response()

    Returns:
        String with interviewer guidance
    """
    intent = analysis.get("intent", "answering")
    confidence = analysis.get("confidence_level", "Confident")

    guidance = []

    if intent == "skipping":
        guidance.append("Candidate is avoiding the question. Move to next topic without explaining.")
    elif intent == "asking_reverse_question":
        guidance.append("Candidate is deflecting. Politely decline and redirect.")

    if confidence == "Low Confidence / Nervous":
        guidance.append("Candidate seems nervous. Use encouraging tone.")

    return " ".join(guidance) if guidance else "Proceed normally."


# Example usage and testing
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "I have 5 years of experience with React and Redux.",
        "Um, well, I think, like, you know, React is good.",
        "I don't know, can we skip this question?",
        "What do you think is the best state management library?",
        "Um, I don't know, what stack do you use?"
    ]

    print("=== Nunchi Analyzer Test Cases ===\n")
    for i, test in enumerate(test_cases, 1):
        result = analyze_candidate_response(test)
        print(f"Test {i}: {test}")
        print(f"  Intent: {result['intent']}")
        print(f"  Confidence: {result['confidence_level']}")
        print(f"  Filler Count: {result['filler_count']}")
        print(f"  Guidance: {get_interviewer_guidance(result)}")
        print()
