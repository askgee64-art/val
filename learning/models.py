"""Data models for Learning System & Founder Teaching — Prompt Spec §14, §15."""

from __future__ import annotations

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class TopicItem(BaseModel):
    topic_id: str
    title: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)
    mastery_score: float = 0.0  # Measured 0.0 to 100.0
    status: str = "pending"     # pending | learning | practicing | mastered | needs_review


class Curriculum(BaseModel):
    subject: str
    topics: list[TopicItem]
    rubric: dict[str, Any] = Field(default_factory=dict)


class LearningObjectiveCreate(BaseModel):
    subject: str
    goal: str = Field(..., description="e.g. Learn calculus well enough to teach me")
    agent_name: str | None = None


class LearningObjectiveOut(BaseModel):
    objective_id: UUID
    org_id: UUID
    agent_id: UUID | None
    agent_name: str
    subject: str
    goal: str
    status: str
    progress_score: float
    current_topic: str | None
    detected_weaknesses: list[str]
    teaching_readiness: float
    created_at: str
    updated_at: str


class FounderTeachingInput(BaseModel):
    statement: str = Field(..., min_length=5, description="What the founder is teaching VAL")
    domain_or_topic: str | None = None
    scope: str = "company"  # company | project | agent | general
