"""Curriculum Generator — Decomposes complex subjects into structured pedagogy.

Prompt Spec §14:
  Transforms "Learn calculus so you can teach me" into structured curriculum
  with measurable mastery milestones.
"""

from __future__ import annotations

from typing import Any
from learning.models import Curriculum, TopicItem


class CurriculumGenerator:
    """Generates rigorous topic breakdown and practice rubrics."""

    def generate(self, subject: str, goal: str) -> Curriculum:
        lowered = subject.lower()

        if "calculus" in lowered:
            topics = [
                TopicItem(
                    topic_id="calc_01",
                    title="Limits and Continuity",
                    description="Formal epsilon-delta definition, one-sided limits, squeeze theorem, continuity.",
                    prerequisites=[],
                    status="learning",
                ),
                TopicItem(
                    topic_id="calc_02",
                    title="Derivatives and Differentiation Rules",
                    description="Definition of derivative, power rule, product rule, quotient rule, chain rule.",
                    prerequisites=["calc_01"],
                ),
                TopicItem(
                    topic_id="calc_03",
                    title="Applications of Derivatives",
                    description="Mean Value Theorem, optimization, curve sketching, related rates, L'Hopital's rule.",
                    prerequisites=["calc_02"],
                ),
                TopicItem(
                    topic_id="calc_04",
                    title="Definite and Indefinite Integrals",
                    description="Riemann sums, Fundamental Theorem of Calculus, u-substitution, area under curve.",
                    prerequisites=["calc_03"],
                ),
                TopicItem(
                    topic_id="calc_05",
                    title="Advanced Integration Techniques & Improper Integrals",
                    description="Integration by parts, partial fractions, trigonometric substitution, improper integrals.",
                    prerequisites=["calc_04"],
                ),
            ]
            rubric = {
                "passing_mastery_threshold": 80.0,
                "practice_problems_per_topic": 5,
                "requires_proof_explanation": True,
            }
        elif "python" in lowered or "code" in lowered or "software" in lowered:
            topics = [
                TopicItem(
                    topic_id="py_01",
                    title="Idiomatic Syntax and Type Annotations",
                    description="Modern Python 3.12+ features, typing module, dataclasses, pattern matching.",
                    status="learning",
                ),
                TopicItem(
                    topic_id="py_02",
                    title="Asynchronous Programming & Concurrency",
                    description="Asyncio event loops, coroutines, tasks, greenlets, threadpools.",
                    prerequisites=["py_01"],
                ),
                TopicItem(
                    topic_id="py_03",
                    title="Software Architecture & Clean Design",
                    description="Dependency inversion, domain-driven design, repository pattern, error handling.",
                    prerequisites=["py_02"],
                ),
                TopicItem(
                    topic_id="py_04",
                    title="Testing & Verification Strategies",
                    description="Unit testing, pytest fixtures, property testing, mocking, security fuzzing.",
                    prerequisites=["py_03"],
                ),
            ]
            rubric = {"passing_mastery_threshold": 85.0}
        else:
            # Generic domain curriculum
            topics = [
                TopicItem(
                    topic_id="gen_01",
                    title=f"Fundamentals of {subject}",
                    description=f"Core definitions, terminology, and foundational theorems of {subject}.",
                    status="learning",
                ),
                TopicItem(
                    topic_id="gen_02",
                    title=f"Intermediate Methods in {subject}",
                    description=f"Practical problem solving, case studies, and application techniques in {subject}.",
                    prerequisites=["gen_01"],
                ),
                TopicItem(
                    topic_id="gen_03",
                    title=f"Advanced Synthesis & Teaching Preparation",
                    description=f"Socratic explanation generation, pedagogical drills, and concept clarification for {subject}.",
                    prerequisites=["gen_02"],
                ),
            ]
            rubric = {"passing_mastery_threshold": 75.0}

        return Curriculum(subject=subject, topics=topics, rubric=rubric)


_generator: CurriculumGenerator | None = None


def get_curriculum_generator() -> CurriculumGenerator:
    global _generator
    if _generator is None:
        _generator = CurriculumGenerator()
    return _generator
