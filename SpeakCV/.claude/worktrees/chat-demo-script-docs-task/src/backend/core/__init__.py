# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

"""
Core module for AI Interview Prep Coach
Contains Knowledge Graph and Nunchi Analyzer
"""

from .knowledge_graph import get_next_topic, get_knowledge_graph, KnowledgeGraph
from .nunchi_analyzer import analyze_candidate_response, get_interviewer_guidance

__all__ = [
    "get_next_topic",
    "get_knowledge_graph",
    "KnowledgeGraph",
    "analyze_candidate_response",
    "get_interviewer_guidance",
]
