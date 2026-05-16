# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

"""
Knowledge Graph Module - In-Memory Graph for Adaptive Interview Flow
Uses NetworkX to model prerequisite relationships between technical concepts.
"""

import networkx as nx
from typing import Optional, List


class KnowledgeGraph:
    """
    In-memory knowledge graph for tracking technical concept prerequisites.
    Supports adaptive interview flow based on candidate performance.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._build_frontend_graph()

    def _build_frontend_graph(self):
        """
        Build a knowledge graph for Frontend Developer role.
        Edges represent prerequisite relationships (parent -> child).
        """
        # Define nodes with their levels
        concepts = [
            # Foundation (Level 1)
            "JavaScript Fundamentals",
            "HTML & CSS",

            # Intermediate (Level 2)
            "React Basics",
            "Component Lifecycle",
            "ES6+ Features",

            # Advanced (Level 3)
            "React Hooks",
            "State Management",
            "Performance Optimization",

            # Expert (Level 4)
            "Redux/Context API",
            "Server-Side Rendering",
            "Micro-frontends"
        ]

        # Add all nodes
        self.graph.add_nodes_from(concepts)

        # Define prerequisite relationships (prerequisite -> dependent)
        edges = [
            # Foundation prerequisites
            ("JavaScript Fundamentals", "React Basics"),
            ("JavaScript Fundamentals", "ES6+ Features"),
            ("HTML & CSS", "React Basics"),

            # Intermediate prerequisites
            ("React Basics", "Component Lifecycle"),
            ("React Basics", "React Hooks"),
            ("ES6+ Features", "React Hooks"),
            ("Component Lifecycle", "React Hooks"),

            # Advanced prerequisites
            ("React Hooks", "State Management"),
            ("React Basics", "State Management"),
            ("State Management", "Redux/Context API"),
            ("React Hooks", "Performance Optimization"),

            # Expert prerequisites
            ("State Management", "Server-Side Rendering"),
            ("Performance Optimization", "Server-Side Rendering"),
            ("Redux/Context API", "Micro-frontends"),
            ("Server-Side Rendering", "Micro-frontends")
        ]

        self.graph.add_edges_from(edges)

    def get_next_topic(self, current_topic: str, candidate_passed: bool) -> str:
        """
        Determine the next interview topic based on candidate performance.

        Args:
            current_topic: The topic just evaluated
            candidate_passed: True if candidate answered well, False otherwise

        Returns:
            Next topic to ask about (str)
        """
        # Handle case where current_topic is not in graph
        if current_topic not in self.graph.nodes:
            # Default to foundation topic
            return "JavaScript Fundamentals"

        if candidate_passed:
            # Move to more advanced topic (child nodes)
            successors = list(self.graph.successors(current_topic))
            if successors:
                # Return the first child (can be randomized later)
                return successors[0]
            else:
                # Already at leaf node, stay at current level or suggest mastery
                return current_topic
        else:
            # Move to foundational topic (parent nodes)
            predecessors = list(self.graph.predecessors(current_topic))
            if predecessors:
                # Return the first prerequisite
                return predecessors[0]
            else:
                # Already at root, stay at current topic
                return current_topic

    def get_all_topics(self) -> List[str]:
        """Return all available topics in the graph."""
        return list(self.graph.nodes)

    def get_foundation_topics(self) -> List[str]:
        """Return topics with no prerequisites (entry points)."""
        return [node for node in self.graph.nodes if self.graph.in_degree(node) == 0]

    def visualize_path(self, start_topic: str, end_topic: str) -> Optional[List[str]]:
        """
        Find the learning path between two topics.

        Args:
            start_topic: Starting concept
            end_topic: Target concept

        Returns:
            List of topics in order, or None if no path exists
        """
        try:
            return nx.shortest_path(self.graph, start_topic, end_topic)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None


# Global singleton instance
_kg_instance = None

def get_knowledge_graph() -> KnowledgeGraph:
    """Get or create the global knowledge graph instance."""
    global _kg_instance
    if _kg_instance is None:
        _kg_instance = KnowledgeGraph()
    return _kg_instance


# Convenience function for direct use
def get_next_topic(current_topic: str, candidate_passed: bool) -> str:
    """
    Convenience wrapper for getting next topic.

    Args:
        current_topic: Current interview topic
        candidate_passed: Whether candidate passed this topic

    Returns:
        Next topic to evaluate
    """
    kg = get_knowledge_graph()
    return kg.get_next_topic(current_topic, candidate_passed)
