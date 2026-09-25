"""Founder Teaching Mode — Prompt Spec §15 & Document 11.

Allows the Founder to personally teach VAL operational principles, company vision,
preferences, and directives. Stores them as high-authority knowledge items
with explicit provenance and asks proactive clarifying questions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from val.audit.logger import get_audit_logger
from val.core.model_router import get_model_router
from val.db.models import KnowledgeItem, utcnow
from val.models.enums import ActorType


@dataclass
class TeachingResult:
    knowledge_id: str
    classified_topic: str
    scope: str
    stored_statement: str
    clarifying_questions: list[str]
    provenance: dict[str, Any]


class FounderTeachingService:
    def __init__(self) -> None:
        self._router = get_model_router()
        self._audit = get_audit_logger()

    async def teach(
        self,
        session: AsyncSession,
        *,
        statement: str,
        org_id: str,
        founder_user_id: str,
        domain_or_topic: str | None = None,
        scope: str = "company",
    ) -> TeachingResult:
        """Process, classify, store, and attach provenance to Founder teaching input."""
        # 1. Classification & Clarification extraction
        classified_topic = domain_or_topic or self._classify_topic(statement)

        # 2. Formulate clarifying questions if necessary
        clarifying_questions = self._generate_clarifying_questions(statement, classified_topic)

        # 3. Provenance metadata (clearly distinguishes Founder knowledge from web/scraped knowledge)
        provenance = {
            "source_type": "founder_teaching",
            "authoritative": True,
            "teacher_user_id": founder_user_id,
            "taught_at": utcnow().isoformat(),
            "scope": scope,
            "priority": "highest",
            "verified_by_founder": True,
        }

        # 4. Save to Knowledge Base
        knowledge_id = str(uuid4())
        item = KnowledgeItem(
            knowledge_id=knowledge_id,
            org_id=org_id,
            title=f"Founder Directive: {classified_topic}",
            content=statement,
            source_type="founder_teaching",
            provenance=provenance,
            quality_score=1.0,  # 1.0 = maximum authority
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(item)
        await session.flush()

        # 5. Immutable Audit
        await self._audit.log(
            session,
            org_id=org_id,
            actor_type=ActorType.USER,
            actor_id=founder_user_id,
            action="founder.taught_knowledge",
            resource_type="knowledge_item",
            resource_id=knowledge_id,
            details={
                "topic": classified_topic,
                "scope": scope,
                "statement_snippet": statement[:120],
                "clarifying_questions_count": len(clarifying_questions),
            },
        )

        return TeachingResult(
            knowledge_id=knowledge_id,
            classified_topic=classified_topic,
            scope=scope,
            stored_statement=statement,
            clarifying_questions=clarifying_questions,
            provenance=provenance,
        )

    def _classify_topic(self, statement: str) -> str:
        lowered = statement.lower()
        if any(w in lowered for w in ["operate", "company", "culture", "workflow", "policy"]):
            return "Company Operating Principles"
        elif any(w in lowered for w in ["finance", "money", "budget", "pricing", "cost"]):
            return "Financial Policy & Limits"
        elif any(w in lowered for w in ["product", "feature", "ui", "customer"]):
            return "Product Vision & Standards"
        elif any(w in lowered for w in ["code", "architecture", "security", "deploy"]):
            return "Engineering Standards & Architecture"
        return "General Strategic Guidance"

    def _generate_clarifying_questions(self, statement: str, topic: str) -> list[str]:
        questions = []
        lowered = statement.lower()
        if "always" in lowered or "never" in lowered:
            questions.append("Are there any emergency exceptions where this rule should be overridden?")
        if "customer" in lowered and "tier" not in lowered:
            questions.append("Does this rule apply uniformly across all plan tiers (standard vs enterprise)?")
        if not questions:
            questions.append("Should this directive be enforced across all specialized agents or VAL Core only?")
        return questions


_founder_teaching_service: FounderTeachingService | None = None


def get_founder_teaching_service() -> FounderTeachingService:
    global _founder_teaching_service
    if _founder_teaching_service is None:
        _founder_teaching_service = FounderTeachingService()
    return _founder_teaching_service
