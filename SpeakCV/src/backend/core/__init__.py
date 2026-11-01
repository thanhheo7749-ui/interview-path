# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

"""
Core module for AI Interview Prep Coach
Contains Nunchi Analyzer
"""

from .nunchi_analyzer import analyze_candidate_response, get_interviewer_guidance

__all__ = [
    "analyze_candidate_response",
    "get_interviewer_guidance",
]
